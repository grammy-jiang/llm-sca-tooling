"""Stage 1: Clause extraction from Markdown spec text."""

from __future__ import annotations

import hashlib
import re

from llm_sca_tooling.impl_check.models import Clause, HarnessPolicyClause, SpecDocument

_OBLIGATION_KEYWORDS = re.compile(
    r"\b(must|shall|should|must not|is required to|is forbidden to)\b",
    re.IGNORECASE,
)
_HARNESS_POLICY_PATTERNS = re.compile(
    r"\b(AGENTS\.md|hard constraint|HC[1-6]|pre-commit|governance|detect-secrets"
    r"|permission|scope boundary|allowlist)\b",
    re.IGNORECASE,
)
_SYMBOL_PATTERN = re.compile(r"`([A-Za-z_][A-Za-z0-9_\.]+)`")


def _clause_id(doc_id: str, span: tuple[int, int]) -> str:
    raw = f"{doc_id}:{span[0]}:{span[1]}"
    return "clause:" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def extract_clauses(doc: SpecDocument, text: str) -> list[Clause | HarnessPolicyClause]:
    sentences = _split_sentences(text)
    clauses: list[Clause | HarnessPolicyClause] = []
    offset = 0
    for sentence in sentences:
        span_start = offset
        span_end = offset + len(sentence)
        offset = span_end + 1
        if not _OBLIGATION_KEYWORDS.search(sentence):
            continue
        targets = _SYMBOL_PATTERN.findall(sentence)
        cid = _clause_id(doc.doc_id, (span_start, span_end))
        is_policy = bool(_HARNESS_POLICY_PATTERNS.search(sentence))
        if is_policy:
            clauses.append(
                HarnessPolicyClause(
                    clause_id=cid,
                    doc_id=doc.doc_id,
                    text=sentence.strip(),
                    source_span=(span_start, span_end),
                    policy_source=doc.source_path,
                    enforcement_mechanism="governance-ci",
                    checked_by_tool="detect-secrets/bandit/mypy",
                    harness_stage_required="verify",
                    target_candidates=targets,
                )
            )
        else:
            compound = "and" in sentence.lower() and "," in sentence
            clauses.append(
                Clause(
                    clause_id=cid,
                    doc_id=doc.doc_id,
                    text=sentence.strip(),
                    source_span=(span_start, span_end),
                    target_candidates=targets,
                    atomic=not compound,
                    checkability=_infer_checkability(sentence),
                    risk_class=_infer_risk_class(sentence),
                )
            )
    return clauses


def _split_sentences(text: str) -> list[str]:
    # Split on line breaks and period-terminated sentences
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sentences: list[str] = []
    for line in lines:
        parts = re.split(r"(?<=[.!?])\s+", line)
        sentences.extend(parts)
    return sentences


def _infer_checkability(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("test", "pytest", "passes", "fails")):
        return "dynamic"
    if any(k in lower for k in ("performance", "latency", "throughput")):
        return "dynamic"
    if any(k in lower for k in ("security", "secret", "credential", "injection")):
        return "hybrid"
    return "static"


def _infer_risk_class(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("security", "secret", "credential", "injection")):
        return "security"
    if any(k in lower for k in ("compliance", "policy", "governance", "hc")):
        return "compliance"
    if any(k in lower for k in ("performance", "latency")):
        return "performance"
    return "correctness"
