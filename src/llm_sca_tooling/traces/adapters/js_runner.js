#!/usr/bin/env node
'use strict';
/**
 * Node.js trace runner for llm_sca_tooling.
 *
 * Usage: node js_runner.js <contract.json> <events.jsonl> <meta.json>
 *
 * Uses the V8 inspector Profiler domain (precise coverage) to capture
 * function-level call events rather than module-load hooks.
 *
 * adapter_id: node-inspector/v2
 * adapter_version: node-inspector/v2
 */

const inspector = require('inspector');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

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
  if (includeModules.length === 0 && includeFunctions.length === 0) return true;
  for (const m of includeModules) {
    if (name.includes(m)) return true;
  }
  for (const f of includeFunctions) {
    if (name.includes(f)) return true;
  }
  return false;
}

// -- V8 inspector: Profiler precise coverage --
const session = new inspector.Session();
session.connect();

// Enable Profiler domain
session.post('Profiler.enable', {}, () => {});
// Start precise coverage with call-count and detailed (per-function) mode
session.post('Profiler.startPreciseCoverage', { callCount: true, detailed: true }, () => {});

const workingDir = contract.working_dir || process.cwd();
const targetCommand = (contract.command || '').trim();
const targetArgs = contract.args || [];
const timeoutMs = (contract.timeout_seconds || 30) * 1000;

try {
  process.chdir(workingDir);
} catch (err) {
  process.stderr.write('chdir failed: ' + err.message + '\n');
}

// Execute the target command
try {
  const parts = targetCommand.split(/\s+/).filter(Boolean);
  const bin = parts[0];
  const args = parts.slice(1).concat(targetArgs);

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

// Collect precise coverage data from V8 inspector
session.post('Profiler.takePreciseCoverage', {}, (err, result) => {
  if (!err && result && result.result) {
    for (const scriptCoverage of result.result) {
      const scriptUrl = scriptCoverage.url || '';
      for (const funcCoverage of (scriptCoverage.functions || [])) {
        const funcName = funcCoverage.functionName || '<anonymous>';
        const callCount = funcCoverage.ranges && funcCoverage.ranges[0]
          ? (funcCoverage.ranges[0].count || 0)
          : 0;
        if (callCount === 0) continue;
        if (!isInScope(scriptUrl) && !isInScope(funcName)) continue;
        const startLine = funcCoverage.ranges && funcCoverage.ranges[0]
          ? (funcCoverage.ranges[0].startOffset || 0)
          : 0;
        writeEvent({
          event_id: 'trace-event:js-' + eventCount,
          event_type: 'call',
          module: scriptUrl,
          function: funcName,
          file_path: scriptUrl,
          line_number: startLine,
          depth: 0,
          arg_type_hints: {},
          return_type_hash: null,
          exception_type: null,
          exception_message_redacted: true,
          ts_ns: nowNs(),
          redaction_applied: true,
          call_count: callCount,
        });
      }
    }
  }
  session.post('Profiler.stopPreciseCoverage', {}, () => {});
  session.post('Profiler.disable', {}, () => {});
  session.disconnect();
  writeMeta();
  process.exit(exitCode);
});

function writeMeta() {
  eventsStream.end();
  const meta = {
    adapter_id: 'node-inspector/v2',
    adapter_version: 'node-inspector/v2',
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

