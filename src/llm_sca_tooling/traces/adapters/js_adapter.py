"""JS/TS trace adapter using Node.js V8 Inspector hooks."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import uuid
from pathlib import Path

from llm_sca_tooling.traces.adapters.base import TraceAdapterBase
from llm_sca_tooling.traces.artefact_store import write_artefact
from llm_sca_tooling.traces.models import RawTraceArtefact, TraceEvent, TraceRunContract

_HOOK_SCRIPT = """
'use strict';
const Module = require('module');
const fs = require('fs');
const path = require('path');

const outPath = process.env._TRACE_OUT;
const events = [];
let counter = 0;
const MAX = parseInt(process.env._TRACE_MAX || '500', 10);

const origLoad = Module._load;
Module._load = function(req, parent, isMain) {
  const result = origLoad.apply(this, arguments);
  if (typeof result === 'object' || typeof result === 'function') {
    _wrap(result, req);
  }
  return result;
};

function _wrap(obj, modName) {
  if (!obj || typeof obj !== 'object' && typeof obj !== 'function') return;
  for (const key of Object.getOwnPropertyNames(obj)) {
    try {
      const val = obj[key];
      if (typeof val === 'function' && !val.__traced__) {
        obj[key] = _makeProxy(val, modName, key);
      }
    } catch (_) {}
  }
}

function _makeProxy(fn, mod, name) {
  function traced() {
    if (counter < MAX) {
      counter++;
      events.push({
        event_id: 'jse:' + counter,
        event_type: 'call',
        module: mod,
        function: name,
        file_path: mod,
        line_number: 0,
        depth: 0,
        arg_type_hints: Array.from(arguments).map(a => typeof a),
        return_type_hash: null,
        exception_type: null,
        exception_message_redacted: false,
        ts_ns: 0,
        redaction_applied: true,
      });
    }
    return fn.apply(this, arguments);
  }
  traced.__traced__ = true;
  return traced;
}

process.on('exit', function() {
  if (outPath) {
    try { fs.writeFileSync(outPath, JSON.stringify(events)); } catch(_) {}
  }
});
"""


class JSTraceAdapterPlaceholder(TraceAdapterBase):
    """JS/TS trace adapter using Node.js require-hook instrumentation."""

    adapter_id = "javascript"
    language = "javascript"

    async def run(
        self,
        contract: TraceRunContract,
        *,
        workspace_root: Path | None = None,
    ) -> tuple[RawTraceArtefact, bool]:
        trace_run_id = f"jstrace:{uuid.uuid4().hex[:8]}"

        node_bin = shutil.which("node") or shutil.which("nodejs")
        if not node_bin:
            artefact = write_artefact(
                trace_run_id, [], workspace_root=workspace_root, language="javascript"
            )
            return artefact, True

        script_path = Path(contract.command)
        if not script_path.exists():
            artefact = write_artefact(
                trace_run_id, [], workspace_root=workspace_root, language="javascript"
            )
            return artefact, True

        with tempfile.TemporaryDirectory() as tmpdir:
            hook_path = Path(tmpdir) / "_trace_hook.js"
            out_path = Path(tmpdir) / "trace_out.json"
            hook_path.write_text(_HOOK_SCRIPT)

            env = dict(contract.environment_snapshot)
            env["_TRACE_OUT"] = str(out_path)
            env["_TRACE_MAX"] = str(contract.max_compressed_events * 10)

            non_reproducing = True
            events: list[TraceEvent] = []
            try:
                proc = await asyncio.create_subprocess_exec(
                    node_bin,
                    "--require",
                    str(hook_path),
                    str(script_path),
                    *contract.args,
                    cwd=contract.working_dir,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(
                    proc.communicate(), timeout=float(contract.timeout_seconds)
                )
                non_reproducing = proc.returncode == 0
                if out_path.exists():
                    raw = json.loads(out_path.read_text())
                    scope = contract.scope_filter
                    for item in raw:
                        mod = item.get("module", "")
                        if scope.include_modules and not any(
                            mod.startswith(m) for m in scope.include_modules
                        ):
                            continue
                        events.append(TraceEvent(**item))
            except TimeoutError:
                non_reproducing = False
            except Exception:
                non_reproducing = False

            artefact = write_artefact(
                trace_run_id,
                events,
                workspace_root=workspace_root,
                language="javascript",
                max_bytes=contract.max_raw_trace_bytes,
            )
            return artefact, non_reproducing
