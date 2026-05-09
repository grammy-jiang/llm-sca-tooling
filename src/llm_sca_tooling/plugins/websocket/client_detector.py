"""TypeScript socket.io client detector."""

from __future__ import annotations

import re

from llm_sca_tooling.plugins.capability import ConfidenceLevel
from llm_sca_tooling.plugins.websocket.namespace_resolver import normalize_namespace


def detect_client_events(text: str, file_path: str) -> list[dict]:
    namespace = "/"
    ns_match = re.search(r"\bio\(\s*['\"]([^'\"]+)['\"]", text)
    if ns_match:
        namespace = normalize_namespace(ns_match.group(1))
    events = []
    for match in re.finditer(r"\bsocket\.(on|emit)\(\s*([`'\"])(.+?)\2", text, re.S):
        raw = match.group(3)
        dynamic = "${" in raw
        events.append({"event": raw, "namespace": namespace, "handler": f"socket.{match.group(1)}:{raw}", "file_path": file_path, "line": text.count("\n", 0, match.start()) + 1, "role": "client", "confidence": ConfidenceLevel.HEURISTIC if dynamic else ConfidenceLevel.ANALYSER})
    return events
