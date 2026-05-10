"""Stage 1: Clause extraction from Markdown text."""

from __future__ import annotations

import hashlib
import re

from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    Clause,
    RiskClass,
)

_OBLIGATION_KEYWORDS = re.compile(
    r"\b(must|shall|should|must not|is required to|are required to|must never|shall not)\b",
    re.IGNORECASE,
)
_STRONG_OBLIGATION = re.compile(
    r"\b(must|shall|must not|must never|shall not|is required to|are required to)\b",
    re.IGNORECASE,
)
_WEAK_OBLIGATION = re.compile(r"\b(should)\b", re.IGNORECASE)

_SECURITY_KEYWORDS = re.compile(
    r"\b(secret|password|auth|security|encrypt|token|credential|inject|xss|csrf)\b",
    re.IGNORECASE,
)
_COMPLIANCE_KEYWORDS = re.compile(
    r"\b(comply|compliance|regulation|policy|GDPR|HIPAA)\b", re.IGNORECASE
)
_PERF_KEYWORDS = re.compile(
    r"\b(latency|throughput|performance|fast|slow|timeout|response time)\b",
    re.IGNORECASE,
)
_DYNAMIC_KEYWORDS = re.compile(
    r"\b(runtime|at run[- ]time|during execution|dynamically|at startup|log|monitor)\b",
    re.IGNORECASE,
)
_STRUCTURAL_KEYWORDS = re.compile(
    r"\b(interface|schema|type|class|module|package|inherit|extend|implement)\b",
    re.IGNORECASE,
)
_SECTION_HEADER = re.compile(r"^(#{1,6})\s+(.*)")


def _stable_clause_id(doc_id: str, source_span: str) -> str:
    key = f"{doc_id}:{source_span}"
    return "clause:" + hashlib.sha256(key.encode()).hexdigest()[:24]


def _infer_scope(section_stack: list[str]) -> str:
    """Derive scope string from current Markdown section header stack."""
    return " > ".join(section_stack) if section_stack else "general"


def _infer_priority(text: str) -> str:
    """Derive priority from obligation keyword strength per KGACG spec."""
    if _STRONG_OBLIGATION.search(text):
        return "high"
    if _WEAK_OBLIGATION.search(text):
        return "normal"
    return "low"


def _infer_checkability(text: str) -> CheckabilityValue:
    if _DYNAMIC_KEYWORDS.search(text):
        return CheckabilityValue.DYNAMIC
    if _STRUCTURAL_KEYWORDS.search(text):
        return CheckabilityValue.STRUCTURAL
    return CheckabilityValue.STATIC


def _detect_risk_class(text: str) -> RiskClass:
    if _SECURITY_KEYWORDS.search(text):
        return RiskClass.SECURITY
    if _COMPLIANCE_KEYWORDS.search(text):
        return RiskClass.COMPLIANCE
    if _PERF_KEYWORDS.search(text):
        return RiskClass.PERFORMANCE
    return RiskClass.UNKNOWN


def _extract_target_candidates(text: str) -> list[str]:
    return re.findall(r"`([A-Za-z_][A-Za-z0-9_\.]*)`", text)


def extract_clauses(doc_id: str, raw_text: str) -> list[Clause]:
    """Extract clauses from Markdown text using obligation keyword heuristics."""
    clauses: list[Clause] = []
    lines = raw_text.splitlines()
    section_stack: list[str] = []

    for line_idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        header_match = _SECTION_HEADER.match(stripped)
        if header_match:
            depth = len(header_match.group(1))
            title = header_match.group(2).strip()
            section_stack = section_stack[: depth - 1] + [title]
            continue

        if not _OBLIGATION_KEYWORDS.search(stripped):
            continue

        scope = _infer_scope(section_stack)
        source_span = f"line:{line_idx + 1}"
        clause_id = _stable_clause_id(doc_id, source_span)

        parts = re.split(r"\s+and\s+", stripped, flags=re.IGNORECASE)
        compound = len(parts) >= 3 or (
            len(parts) == 2 and all(_OBLIGATION_KEYWORDS.search(p) for p in parts)
        )

        if compound:
            parent_clause = Clause(
                clause_id=clause_id,
                doc_id=doc_id,
                text=stripped,
                source_span=source_span,
                scope=scope,
                priority=_infer_priority(stripped),
                checkability=_infer_checkability(stripped),
                target_candidates=_extract_target_candidates(stripped),
                risk_class=_detect_risk_class(stripped),
                atomic=False,
                harness_policy_flag=False,
            )
            clauses.append(parent_clause)

            for part_idx, part in enumerate(parts):
                part_text = part.strip()
                if not part_text:
                    continue
                sub_span = f"line:{line_idx + 1}:part:{part_idx}"
                sub_id = _stable_clause_id(doc_id, sub_span)
                sub_clause = Clause(
                    clause_id=sub_id,
                    doc_id=doc_id,
                    text=part_text,
                    source_span=sub_span,
                    scope=scope,
                    priority=_infer_priority(part_text),
                    checkability=_infer_checkability(part_text),
                    target_candidates=_extract_target_candidates(part_text),
                    risk_class=_detect_risk_class(part_text),
                    parent_clause_id=clause_id,
                    atomic=True,
                    harness_policy_flag=False,
                )
                clauses.append(sub_clause)
        else:
            clause = Clause(
                clause_id=clause_id,
                doc_id=doc_id,
                text=stripped,
                source_span=source_span,
                scope=scope,
                priority=_infer_priority(stripped),
                checkability=_infer_checkability(stripped),
                target_candidates=_extract_target_candidates(stripped),
                risk_class=_detect_risk_class(stripped),
                atomic=True,
                harness_policy_flag=False,
            )
            clauses.append(clause)

    return clauses
