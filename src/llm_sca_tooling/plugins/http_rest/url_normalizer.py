"""HTTP URL and route-pattern normalization."""

from __future__ import annotations

import re
from urllib.parse import urlsplit


def normalize_url_pattern(value: str) -> str:
    raw = value.strip().strip("'\"")
    if not raw:
        return "/"
    if "://" in raw:
        parsed = urlsplit(raw)
        raw = parsed.path or "/"
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    raw = re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", raw)
    raw = re.sub(r":([A-Za-z_][\w]*)", r"{\1}", raw)
    raw = re.sub(r"\$\{([^}]+)\}", r"{\1}", raw)
    raw = re.sub(r"//+", "/", raw)
    if not raw.startswith("/"):
        raw = "/" + raw
    if len(raw) > 1:
        raw = raw.rstrip("/")
    return raw or "/"


def pattern_shape(value: str) -> str:
    return re.sub(r"\{[^}/]+\}", "{}", normalize_url_pattern(value))


def match_patterns(left: str, right: str) -> str | None:
    left_norm = normalize_url_pattern(left)
    right_norm = normalize_url_pattern(right)
    if left_norm == right_norm:
        return "parser"
    if pattern_shape(left_norm) == pattern_shape(right_norm):
        return "analyser"
    left_parts = left_norm.strip("/").split("/") if left_norm != "/" else []
    right_parts = right_norm.strip("/").split("/") if right_norm != "/" else []
    if len(left_parts) == len(right_parts) and all(
        _segment_matches(a, b) for a, b in zip(left_parts, right_parts, strict=False)
    ):
        return "analyser"
    if left_norm.startswith(right_norm) or right_norm.startswith(left_norm):
        return "heuristic"
    return None


def _segment_matches(left: str, right: str) -> bool:
    return (
        left == right
        or left.startswith("{")
        and left.endswith("}")
        or right.startswith("{")
        and right.endswith("}")
    )
