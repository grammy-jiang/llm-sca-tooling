"""HTTP route URL normalization."""

from __future__ import annotations

import re
from urllib.parse import urlparse

__all__ = ["match_paths", "normalize_url_path"]


def normalize_url_path(raw: str) -> str:
    parsed = urlparse(raw.strip())
    path = parsed.path if parsed.scheme or parsed.netloc else raw.split("?", 1)[0]
    path = re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", path)
    path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
    path = re.sub(r"//+", "/", path)
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def match_paths(left: str, right: str) -> str | None:
    left_norm = normalize_url_path(left)
    right_norm = normalize_url_path(right)
    if left_norm == right_norm:
        return "parser"
    left_shape = re.sub(r"\{[^}]+\}", "{}", left_norm)
    right_shape = re.sub(r"\{[^}]+\}", "{}", right_norm)
    if left_shape == right_shape:
        return "analyser"
    if left_shape.startswith(right_shape) or right_shape.startswith(left_shape):
        return "heuristic"
    return None
