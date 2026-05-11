"""Fallback IDL parser for omniORB-style interfaces."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess

from llm_sca_tooling.plugins.capability import ConfidenceLevel

_log = logging.getLogger(__name__)


def parse_idl(text: str, *, idl_file_path: str | None = None) -> list[dict]:
    """Parse IDL text. Uses omniidl -p when available, falls back to regex tokenizer."""
    if idl_file_path and shutil.which("omniidl"):
        result = _parse_with_omniidl(idl_file_path)
        if result is not None:
            return result
    return _parse_with_regex(text)


def _parse_with_omniidl(idl_file_path: str) -> list[dict] | None:
    """Invoke omniidl -p to dump IDL AST. Returns None on any failure."""
    try:
        proc = subprocess.run(
            ["omniidl", "-p", "-bdumpAST", idl_file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parsed = _parse_omniidl_output(proc.stdout)
            if parsed:
                return parsed
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        _log.debug("omniidl -bdumpAST failed: %s", exc)

    # Fallback: try omniidl -p -bpython -nf
    try:
        proc = subprocess.run(
            ["omniidl", "-p", "-bpython", "-nf", idl_file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parsed = _parse_omniidl_python_output(proc.stdout)
            if parsed:
                return parsed
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        _log.debug("omniidl -bpython failed: %s", exc)

    return None


def _parse_omniidl_output(output: str) -> list[dict]:
    """Parse AST dump output from omniidl -bdumpAST."""
    interfaces = []
    current: dict | None = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Interface:") or "interface" in stripped.lower():
            parts = stripped.split()
            for i, part in enumerate(parts):
                if part.lower() in {"interface:", "interface"}:
                    name = parts[i + 1] if i + 1 < len(parts) else ""
                    name = name.strip(":")
                    if name:
                        if current is not None:
                            interfaces.append(current)
                        current = {
                            "name": name,
                            "methods": [],
                            "confidence": ConfidenceLevel.CONFIRMED,
                        }
                    break
        elif current is not None and "operation" in stripped.lower():
            parts = stripped.split()
            op_name = ""
            for i, part in enumerate(parts):
                if part.lower() in {"operation:", "operation"}:
                    op_name = parts[i + 1].strip(":") if i + 1 < len(parts) else ""
                    break
            if op_name:
                current["methods"].append(
                    {"name": op_name, "return_type": "void", "parameters": []}
                )
    if current is not None:
        interfaces.append(current)
    return interfaces


def _parse_omniidl_python_output(output: str) -> list[dict]:
    """Parse Python-style output from omniidl -bpython."""
    # Minimal parser: extract interface declarations from generated Python stubs
    interfaces = []
    for match in re.finditer(r"class\s+(\w+)\s*\(", output):
        name = match.group(1)
        if not name.startswith("_"):
            interfaces.append(
                {
                    "name": name,
                    "methods": [],
                    "confidence": ConfidenceLevel.CONFIRMED,
                }
            )
    return interfaces


def _parse_with_regex(text: str) -> list[dict]:
    """Regex-based IDL tokenizer (original implementation)."""
    interfaces = []
    for match in re.finditer(
        r"\binterface\s+([A-Za-z_][\w]*)\s*(?::\s*[A-Za-z_][\w:,\s]*)?\{(?P<body>.*?)\};",
        text,
        re.S,
    ):
        body = match.group("body")
        methods = []
        for op in re.finditer(
            r"(?:oneway\s+)?([A-Za-z_][\w:<>]*)\s+([A-Za-z_][\w]*)\s*\(([^)]*)\)", body
        ):
            params = []
            for param in [p.strip() for p in op.group(3).split(",") if p.strip()]:
                parts = param.split()
                if len(parts) >= 3 and parts[0] in {"in", "out", "inout"}:
                    params.append(
                        {"direction": parts[0], "type": parts[1], "name": parts[2]}
                    )
            methods.append(
                {"name": op.group(2), "return_type": op.group(1), "parameters": params}
            )
        interfaces.append(
            {
                "name": match.group(1),
                "methods": methods,
                "confidence": ConfidenceLevel.HEURISTIC,
            }
        )
    return interfaces
