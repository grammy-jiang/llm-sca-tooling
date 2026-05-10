"""Interface-compatibility checker."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.models import (
    ConfidenceLevel,
    DiffRecord,
    InterfaceChangeImpact,
    InterfaceCompatibilityResult,
)


def check_interface_compatibility(
    diff: DiffRecord,
    *,
    interface_records: list[dict[str, Any]] | None = None,
    consumer_links: dict[str, list[str]] | None = None,
    candidate_links: dict[str, list[str]] | None = None,
    interface_type: str | None = None,
) -> InterfaceCompatibilityResult:
    """Detect breaking interface changes from diff and Phase 7 plugin records.

    ``interface_records`` is a list of dicts with at least ``operation``,
    ``change`` (one of ``removed``, ``renamed``, ``required_param_added``,
    ``return_type_changed``, ``optional_param_added``), and optionally
    ``generated_source``.
    """
    records = interface_records or []
    consumers = consumer_links or {}
    candidates = candidate_links or {}
    breaking: list[dict[str, Any]] = []
    candidate: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    affected: set[str] = set()
    operations: list[str] = []

    for rec in records:
        op = str(rec.get("operation", "")).strip()
        change = str(rec.get("change", "")).strip()
        if not op or not change:
            continue
        operations.append(op)
        impact = _classify_change(change, str(rec.get("interface_type", "") or ""))
        for c in consumers.get(op, []):
            affected.add(c)
        if impact in (
            InterfaceChangeImpact.BREAKING,
            InterfaceChangeImpact.CONFIRMED_BREAKING,
        ):
            breaking.append({"operation": op, "change": change, "impact": impact.value})
        elif impact == InterfaceChangeImpact.CANDIDATE:
            candidate.append(
                {"operation": op, "change": change, "impact": impact.value}
            )
        if rec.get("generated_source"):
            generated.append(
                {
                    "operation": op,
                    "source_contract": rec["generated_source"],
                }
            )
        for cand in candidates.get(op, []):
            candidate.append({"operation": op, "consumer": cand, "impact": "candidate"})

    inferred_type = interface_type or _infer_type(diff)
    confidence = ConfidenceLevel.ANALYSER if records else ConfidenceLevel.HEURISTIC
    diagnostics: list[dict[str, Any]] = []
    if not records:
        diagnostics.append({"code": "no_interface_records"})

    return InterfaceCompatibilityResult(
        diff_id=diff.diff_id,
        interface_type=inferred_type,
        changed_operations=operations,
        affected_consumers=sorted(affected),
        breaking_changes=breaking,
        candidate_changes=candidate,
        generated_file_impact=generated,
        confidence=confidence,
        diagnostics=diagnostics,
    )


def _classify_change(change: str, interface_type: str) -> InterfaceChangeImpact:
    change = change.lower()
    if change in {"removed", "renamed", "required_param_added"}:
        return InterfaceChangeImpact.BREAKING
    if change == "return_type_changed":
        return (
            InterfaceChangeImpact.BREAKING
            if interface_type in {"http", "grpc", "protobuf"}
            else InterfaceChangeImpact.CANDIDATE
        )
    if change == "optional_param_added":
        return InterfaceChangeImpact.COMPATIBLE
    return InterfaceChangeImpact.CANDIDATE


def _infer_type(diff: DiffRecord) -> str:
    files = diff.changed_files
    if any(f.endswith(".proto") for f in files):
        return "protobuf"
    if any("openapi" in f.lower() for f in files):
        return "http"
    if any("/routes/" in f or "/api/" in f for f in files):
        return "http"
    return "unknown"
