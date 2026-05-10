"""Patch-review trace reference helper."""

from __future__ import annotations

from llm_sca_tooling.schemas.base import JsonObject


def mismatch_with_trace_ref(mismatch: JsonObject, divergence_ref: str) -> JsonObject:
    payload = dict(mismatch)
    payload["trace_divergence_ref"] = divergence_ref
    return payload
