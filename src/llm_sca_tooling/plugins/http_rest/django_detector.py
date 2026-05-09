"""Django URL-pattern detector."""

from __future__ import annotations

import re

from llm_sca_tooling.plugins.http_rest.url_normalizer import normalize_url_pattern


def detect_django_routes(text: str, file_path: str) -> list[dict]:
    routes = []
    if "urlpatterns" not in text and "path(" not in text:
        return routes
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
