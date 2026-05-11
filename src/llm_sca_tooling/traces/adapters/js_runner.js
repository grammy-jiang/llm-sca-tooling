#!/usr/bin/env node
'use strict';
/**
 * Node.js trace runner for llm_sca_tooling.
 *
 * Usage: node js_runner.js <contract.json> <events.jsonl> <meta.json>
 *
 * Reads a trace contract, instruments module loads via Module._load hooks,
 * executes the target command, and writes TraceEvent-compatible JSON lines.
 */

const fs = require('fs');
const path = require('path');
const Module = require('module');

const contractPath = process.argv[2];
const eventsPath = process.argv[3];
const metaPath = process.argv[4];

if (!contractPath || !eventsPath || !metaPath) {
  process.stderr.write('Usage: js_runner.js <contract.json> <events.jsonl> <meta.json>\n');
  process.exit(1);
}

let contract;
try {
  contract = JSON.parse(fs.readFileSync(contractPath, 'utf8'));
} catch (err) {
  process.stderr.write('Failed to parse contract: ' + err.message + '\n');
  process.exit(1);
}

const scopeFilter = contract.scope_filter || {};
const includeModules = scopeFilter.include_modules || [];
const includeFunctions = scopeFilter.include_functions || [];
const maxDepth = typeof scopeFilter.max_call_depth === 'number' ? scopeFilter.max_call_depth : 10;
const maxBytes = typeof contract.max_raw_trace_bytes === 'number' ? contract.max_raw_trace_bytes : 1000000;

let eventCount = 0;
let bytesWritten = 0;
let truncated = false;
let exitCode = 0;
const startMs = Date.now();

const eventsStream = fs.createWriteStream(eventsPath, { flags: 'w', encoding: 'utf8' });

function nowNs() {
  return (Date.now() - startMs) * 1000000;
}

function writeEvent(evt) {
  if (truncated) return;
  const line = JSON.stringify(evt) + '\n';
  if (bytesWritten + line.length > maxBytes) {
    truncated = true;
    return;
  }
  eventsStream.write(line);
  bytesWritten += line.length;
  eventCount++;
}

function isInScope(name) {
  if (includeModules.length === 0 && includeFunctions.length === 0) return false;
  for (const m of includeModules) {
    if (name.includes(m)) return true;
  }
  for (const f of includeFunctions) {
    if (name.includes(f)) return true;
  }
  return false;
}

// Instrument Module._load to capture require/import events
const origLoad = Module._load;
Module._load = function instrumentedLoad(request, parent, isMain) {
  const result = origLoad.apply(this, arguments);
  if (isInScope(request)) {
    writeEvent({
      event_id: 'trace-event:js-' + eventCount,
      event_type: 'call',
      module: request,
      function: '<module_load>',
      file_path: request,
      line_number: 0,
      depth: 0,
      arg_type_hints: {},
      return_type_hash: null,
      exception_type: null,
      exception_message_redacted: true,
      ts_ns: nowNs(),
      redaction_applied: true,
    });
  }
  return result;
};

function writeMeta() {
  eventsStream.end();
  const meta = {
    event_count: eventCount,
    truncated: truncated,
    truncation_reason: truncated ? 'max_bytes_exceeded' : null,
    exit_code: exitCode,
    diagnostics: [],
  };
  try {
    fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2), 'utf8');
  } catch (err) {
    process.stderr.write('Failed to write meta: ' + err.message + '\n');
  }
}

// Execute the target command
const workingDir = contract.working_dir || process.cwd();
const targetCommand = (contract.command || '').trim();
const targetArgs = contract.args || [];

try {
  process.chdir(workingDir);
} catch (err) {
  process.stderr.write('chdir failed: ' + err.message + '\n');
}

// Try to execute via child_process to capture actual execution
try {
  const { spawnSync } = require('child_process');
  const parts = targetCommand.split(/\s+/).filter(Boolean);
  const bin = parts[0];
  const args = parts.slice(1).concat(targetArgs);
  const timeoutMs = (contract.timeout_seconds || 30) * 1000;

  const result = spawnSync(bin, args, {
    cwd: workingDir,
    timeout: timeoutMs,
    stdio: 'pipe',
    encoding: 'buffer',
  });

  exitCode = result.status != null ? result.status : 0;

  if (result.error) {
    writeEvent({
      event_id: 'trace-event:js-' + eventCount,
      event_type: 'exception',
      module: '',
      function: '<main>',
      file_path: '',
      line_number: 0,
      depth: 0,
      arg_type_hints: {},
      return_type_hash: null,
      exception_type: result.error.code || 'SpawnError',
      exception_message_redacted: true,
      ts_ns: nowNs(),
      redaction_applied: true,
    });
    exitCode = 1;
  }
} catch (err) {
  exitCode = 1;
  writeEvent({
    event_id: 'trace-event:js-' + eventCount,
    event_type: 'exception',
    module: '',
    function: '<main>',
    file_path: '',
    line_number: 0,
    depth: 0,
    arg_type_hints: {},
    return_type_hash: null,
    exception_type: err.constructor ? err.constructor.name : 'Error',
    exception_message_redacted: true,
    ts_ns: nowNs(),
    redaction_applied: true,
  });
}

writeMeta();
process.exit(exitCode);
