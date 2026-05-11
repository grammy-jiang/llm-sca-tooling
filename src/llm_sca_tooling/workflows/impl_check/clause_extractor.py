"""Stage 1: Clause extraction from Markdown text.

Supports two extraction modes selected via the ``doc_style`` parameter:

* ``"rfc"`` — classic RFC-style: only lines with obligation keywords
  (must / shall / should / must not …) are extracted.  Suitable for
  specs, ADRs, and RFCs that use normative language.

* ``"architecture"`` — architecture-doc mode: also extracts bullet-list
  items and structural sentences that describe system behaviour using
  action verbs (provides, stores, exposes, implements, …) even when no
  RFC obligation keyword is present.  Suitable for design docs and
  phase-based architecture specs.

* ``"auto"`` (default) — runs RFC mode first; if the resulting clause
  density is below the sparsity threshold (< 1 clause per 50 lines for
  docs with more than 50 lines), automatically re-runs in architecture
  mode so that arch docs produce useful clause sets.
"""

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

# Architecture-mode: verbs commonly used in design docs to describe system
# behaviour without RFC obligation language.
_ARCH_BEHAVIORAL_VERBS = re.compile(
    r"\b(provides?|stores?|exposes?|implements?|includes?|returns?|supports?|"
    r"accepts?|validates?|generates?|builds?|queries|maintains?|wraps?|"
    r"computes?|tracks?|emits?|registers?|annotates?|classifies|routes?|"
    r"indexes|runs|executes?|creates?|updates?|injects?|manages?|assigns?|"
    r"raises?|connects?|binds?|detects?|parses?|loads?|ingests?|assembles?|"
    r"evaluates?|scores?|ranks?|collects?|verifies?|maps?|persists?|caches?|"
    r"dispatches?|serializes?|produces?|consumes?|initializes?|bootstraps?|"
    r"aggregates?|publishes?|subscribes?|streams?|snapshots?|indexes|indexes?)\b",
    re.IGNORECASE,
)

# Architecture-mode: a line is a bullet item if it starts with a list marker.
_BULLET_PREFIX = re.compile(r"^[\-\*\+•]\s+(.+)$")

# Architecture-mode: a Phase/Gap/Component section raises clause priority.
_ARCH_SECTION_PATTERN = re.compile(
    r"\b(phase\s+\d+|gap\s+\d+|component|module|service|subsystem)\b",
    re.IGNORECASE,
)

# Minimum meaningful clause text length (chars) for arch mode.
_MIN_ARCH_CLAUSE_LEN = 20

# Auto-detection: if doc has more than this many lines and RFC-mode yields
# fewer than 1 clause per _AUTO_SPARSITY_RATIO lines, switch to arch mode.
_AUTO_SPARSITY_MIN_LINES = 50
_AUTO_SPARSITY_RATIO = 50  # lines-per-clause threshold


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


def _build_clauses_from_line(
    doc_id: str,
    stripped: str,
    line_idx: int,
    section_stack: list[str],
) -> list[Clause]:
    """Convert a single RFC obligation line into one or more Clause objects."""
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
        sub_clauses: list[Clause] = [parent_clause]
        for part_idx, part in enumerate(parts):
            part_text = part.strip()
            if not part_text:
                continue
            sub_span = f"line:{line_idx + 1}:part:{part_idx}"
            sub_id = _stable_clause_id(doc_id, sub_span)
            sub_clauses.append(
                Clause(
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
            )
        return sub_clauses

    return [
        Clause(
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
    ]


def extract_clauses(
    doc_id: str, raw_text: str, doc_style: str = "auto"
) -> list[Clause]:
    """Extract clauses from Markdown text.

    Parameters
    ----------
    doc_id:
        Stable identifier for the source document.
    raw_text:
        Full Markdown source text.
    doc_style:
        ``"rfc"`` — only RFC obligation keywords (must/shall/should …).
        ``"architecture"`` — also extracts bullet items and structural
        sentences with behavioral action verbs.
        ``"auto"`` (default) — tries RFC mode; if the clause density is
        below the sparsity threshold the function re-runs in architecture
        mode automatically.
    """
    lines = raw_text.splitlines()
    rfc_clauses = _extract_rfc_clauses(doc_id, lines)

    if doc_style == "rfc":
        return rfc_clauses

    if doc_style == "architecture":
        return _merge_clauses(rfc_clauses, _extract_arch_clauses(doc_id, lines))

    # auto: switch to architecture mode when RFC yields sparse results.
    if len(lines) >= _AUTO_SPARSITY_MIN_LINES and len(rfc_clauses) < max(
        3, len(lines) // _AUTO_SPARSITY_RATIO
    ):
        return _merge_clauses(rfc_clauses, _extract_arch_clauses(doc_id, lines))

    return rfc_clauses


def _merge_clauses(rfc: list[Clause], arch: list[Clause]) -> list[Clause]:
    """Merge RFC and architecture clauses, deduplicating by clause_id."""
    seen: set[str] = set()
    result: list[Clause] = []
    for clause in rfc + arch:
        if clause.clause_id not in seen:
            seen.add(clause.clause_id)
            result.append(clause)
    return result


def _extract_rfc_clauses(doc_id: str, lines: list[str]) -> list[Clause]:
    """Extract clauses using RFC obligation-keyword heuristics."""
    clauses: list[Clause] = []
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

        clauses.extend(
            _build_clauses_from_line(doc_id, stripped, line_idx, section_stack)
        )

    return clauses


def _extract_arch_clauses(doc_id: str, lines: list[str]) -> list[Clause]:
    """Extract clauses from architecture-style Markdown.

    Captures bullet items and structural sentences that express system
    behaviour via action verbs or backtick symbol references, even when
    no RFC obligation keyword is present.
    """
    clauses: list[Clause] = []
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

        # Skip lines already captured by RFC mode.
        if _OBLIGATION_KEYWORDS.search(stripped):
            continue

        # Skip table separator rows and code fence markers.
        if re.match(r"^[\|\-\s:]+$", stripped) or stripped.startswith("```"):
            continue

        content = stripped
        bullet_match = _BULLET_PREFIX.match(stripped)
        if bullet_match:
            content = bullet_match.group(1)

        if len(content) < _MIN_ARCH_CLAUSE_LEN:
            continue

        has_behavioral_verb = bool(_ARCH_BEHAVIORAL_VERBS.search(content))
        has_symbol_ref = "`" in content

        # Include if it has a behavioral verb, a backtick symbol reference,
        # or both — this filters out pure prose without actionable content.
        if not (has_behavioral_verb or has_symbol_ref):
            continue

        scope = _infer_scope(section_stack)
        source_span = f"line:{line_idx + 1}"
        clause_id = _stable_clause_id(doc_id, f"arch:{source_span}")

        clauses.append(
            Clause(
                clause_id=clause_id,
                doc_id=doc_id,
                text=content,
                source_span=source_span,
                scope=scope,
                priority=_infer_priority(content),
                checkability=_infer_checkability(content),
                target_candidates=_extract_target_candidates(content),
                risk_class=_detect_risk_class(content),
                atomic=True,
                harness_policy_flag=False,
            )
        )

    return clauses
