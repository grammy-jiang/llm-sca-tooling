"""Python socket.io server event detector."""

from __future__ import annotations

import ast
import re

from llm_sca_tooling.plugins.capability import ConfidenceLevel
from llm_sca_tooling.plugins.websocket.namespace_resolver import normalize_namespace


def detect_server_events(text: str, file_path: str) -> list[dict]:
    events = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree:
        for item in ast.walk(tree):
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in item.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "on"
                ):
                    event = _string_arg(decorator)
                    if event:
                        namespace = "/"
                        for keyword in decorator.keywords:
                            if (
                                keyword.arg == "namespace"
                                and isinstance(keyword.value, ast.Constant)
                                and isinstance(keyword.value.value, str)
                            ):
                                namespace = keyword.value.value
                        events.append(
                            {
                                "event": event,
                                "namespace": normalize_namespace(namespace),
                                "handler": item.name,
                                "file_path": file_path,
                                "line": item.lineno,
                                "role": "server",
                                "confidence": ConfidenceLevel.PARSER,
                            }
                        )
    for match in re.finditer(r"\bemit\(\s*['\"]([^'\"]+)['\"]", text):
        events.append(
            {
                "event": match.group(1),
                "namespace": "/",
                "handler": f"emit:{match.group(1)}",
                "file_path": file_path,
                "line": text.count("\n", 0, match.start()) + 1,
                "role": "server_emit",
                "confidence": ConfidenceLevel.ANALYSER,
            }
        )
    return events


def _string_arg(call: ast.Call) -> str | None:
    if (
        call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    ):
        return call.args[0].value
    return None
