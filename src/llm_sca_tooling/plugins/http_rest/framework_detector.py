"""Python web-framework route detectors."""

from __future__ import annotations

import ast
import re

from llm_sca_tooling.plugins.http_rest.url_normalizer import normalize_url_pattern

ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def detect_python_routes(text: str, file_path: str) -> list[dict]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    routes: list[dict] = []
    for item in ast.walk(tree):
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in item.decorator_list:
            route = _route_from_decorator(decorator)
            if route:
                route.update(
                    {"handler": item.name, "file_path": file_path, "line": item.lineno}
                )
                routes.append(route)
    routes.extend(_detect_django_regex(text, file_path))
    return routes


def _route_from_decorator(decorator: ast.AST) -> dict | None:
    if not isinstance(decorator, ast.Call) or not isinstance(
        decorator.func, ast.Attribute
    ):
        return None
    name = decorator.func.attr.lower()
    if name in ROUTE_METHODS:
        path = _first_string(decorator)
        if path:
            return {
                "framework": "fastapi",
                "method": name.upper(),
                "path": normalize_url_pattern(path),
                "confidence": "analyser",
            }
    if name == "route":
        path = _first_string(decorator)
        if not path:
            return None
        methods = ["GET"]
        for keyword in decorator.keywords:
            if keyword.arg == "methods" and isinstance(
                keyword.value, (ast.List, ast.Tuple)
            ):
                methods = [
                    item.value.upper()
                    for item in keyword.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ] or methods
        return {
            "framework": "flask",
            "method": methods[0],
            "path": normalize_url_pattern(path),
            "confidence": "analyser",
        }
    return None


def _first_string(call: ast.Call) -> str | None:
    if (
        call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    ):
        return call.args[0].value
    return None


def _detect_django_regex(text: str, file_path: str) -> list[dict]:
    routes = []
    for match in re.finditer(
        r"\bpath\(\s*['\"]([^'\"]+)['\"]\s*,\s*([A-Za-z_][\w.]*)", text
    ):
        routes.append(
            {
                "framework": "django",
                "method": "GET",
                "path": normalize_url_pattern(match.group(1)),
                "handler": match.group(2).split(".")[-1],
                "file_path": file_path,
                "line": text.count("\n", 0, match.start()) + 1,
                "confidence": "analyser",
            }
        )
    return routes
