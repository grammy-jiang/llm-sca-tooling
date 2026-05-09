"""Fallback IDL parser for omniORB-style interfaces."""

from __future__ import annotations

import re

from llm_sca_tooling.plugins.capability import ConfidenceLevel


def parse_idl(text: str) -> list[dict]:
    interfaces = []
    for match in re.finditer(r"\binterface\s+([A-Za-z_][\w]*)\s*(?::\s*[A-Za-z_][\w:,\s]*)?\{(?P<body>.*?)\};", text, re.S):
        body = match.group("body")
        methods = []
        for op in re.finditer(r"(?:oneway\s+)?([A-Za-z_][\w:<>]*)\s+([A-Za-z_][\w]*)\s*\(([^)]*)\)", body):
            params = []
            for param in [p.strip() for p in op.group(3).split(",") if p.strip()]:
                parts = param.split()
                if len(parts) >= 3 and parts[0] in {"in", "out", "inout"}:
                    params.append({"direction": parts[0], "type": parts[1], "name": parts[2]})
            methods.append({"name": op.group(2), "return_type": op.group(1), "parameters": params})
        interfaces.append({"name": match.group(1), "methods": methods, "confidence": ConfidenceLevel.HEURISTIC})
    return interfaces
