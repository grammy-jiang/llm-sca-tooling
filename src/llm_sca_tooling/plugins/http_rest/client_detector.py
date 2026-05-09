"""JavaScript/TypeScript HTTP client detector."""

from __future__ import annotations

import re

from llm_sca_tooling.plugins.capability import ConfidenceLevel
from llm_sca_tooling.plugins.http_rest.url_normalizer import normalize_url_pattern


def detect_http_clients(text: str, file_path: str) -> list[dict]:
    clients = []
    patterns = [
        (r"\bfetch\(\s*([`'\"])(.+?)\1", "GET", "fetch"),
        (r"\baxios\.(get|delete|post|put|patch)\(\s*([`'\"])(.+?)\2", None, "axios"),
    ]
    for pattern, default_method, source in patterns:
        for match in re.finditer(pattern, text, re.S):
            if source == "axios":
                method = match.group(1).upper()
                raw = match.group(3)
            else:
                method = default_method or "GET"
                raw = match.group(2)
            dynamic = "${" in raw or "{" in raw and "}" not in raw
            clients.append({"method": method, "path": normalize_url_pattern(raw), "raw_url": raw, "file_path": file_path, "line": text.count("\n", 0, match.start()) + 1, "source": source, "confidence": ConfidenceLevel.HEURISTIC if dynamic else ConfidenceLevel.ANALYSER})
    return clients
