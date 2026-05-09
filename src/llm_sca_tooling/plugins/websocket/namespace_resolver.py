"""socket.io namespace normalization."""

from __future__ import annotations


def normalize_namespace(namespace: str | None) -> str:
    if not namespace:
        return "/"
    namespace = namespace.strip().strip("'\"")
    if not namespace.startswith("/"):
        namespace = "/" + namespace
    return namespace or "/"


def namespace_matches(left: str | None, right: str | None) -> bool:
    return normalize_namespace(left) == normalize_namespace(right)
