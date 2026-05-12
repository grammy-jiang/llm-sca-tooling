"""Stage 1: Clause extraction from Markdown spec text.

Extracts three kinds of clauses:

1. **Normative** — sentences containing RFC-style obligation keywords
   (must / shall / should / must not / is required to / is forbidden to).
2. **Structural / table** — rows from Markdown pipe-delimited tables.
   Each data row is converted to a named-field clause so that descriptive
   architecture documents (tables of stages, modules, I/O contracts) are
   fully represented.
3. **Bullet** — Markdown list items that reference at least one code symbol
   (backtick-delimited identifier).  Generic prose bullets without a symbol
   reference are skipped to avoid noise.
"""

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
_SYMBOL_PATTERN = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_\.\-/]*[A-Za-z0-9_]|[A-Za-z_][A-Za-z0-9_]?)`"
)
_BULLET_PATTERN = re.compile(r"^(\s*[-*+]|\s*\d+\.)\s+(.+)$")
_TABLE_SEPARATOR = re.compile(r"^[-:]+$")


def _clause_id(doc_id: str, span: tuple[int, int]) -> str:
    raw = f"{doc_id}:{span[0]}:{span[1]}"
    return "clause:" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _make_clause(
    doc: SpecDocument,
    text: str,
    span: tuple[int, int],
    *,
    atomic: bool = True,
) -> Clause | HarnessPolicyClause:
    targets = _SYMBOL_PATTERN.findall(text)
    cid = _clause_id(doc.doc_id, span)
    if _HARNESS_POLICY_PATTERNS.search(text):
        return HarnessPolicyClause(
            clause_id=cid,
            doc_id=doc.doc_id,
            text=text.strip(),
            source_span=span,
            policy_source=doc.source_path,
            enforcement_mechanism="governance-ci",
            checked_by_tool="detect-secrets/bandit/mypy",
            harness_stage_required="verify",
            target_candidates=targets,
        )
    return Clause(
        clause_id=cid,
        doc_id=doc.doc_id,
        text=text.strip(),
        source_span=span,
        target_candidates=targets,
        atomic=atomic,
        checkability=_infer_checkability(text),
        risk_class=_infer_risk_class(text),
    )


def extract_clauses(doc: SpecDocument, text: str) -> list[Clause | HarnessPolicyClause]:
    """Extract all clauses from *text* using normative, table, and bullet strategies."""
    clauses: list[Clause | HarnessPolicyClause] = []
    clauses.extend(_extract_normative_clauses(doc, text))
    clauses.extend(_extract_table_clauses(doc, text))
    clauses.extend(_extract_bullet_clauses(doc, text))
    return clauses


# ---------------------------------------------------------------------------
# Strategy 1 — normative keyword sentences
# ---------------------------------------------------------------------------


def _extract_normative_clauses(
    doc: SpecDocument, text: str
) -> list[Clause | HarnessPolicyClause]:
    sentences = _split_sentences(text)
    clauses: list[Clause | HarnessPolicyClause] = []
    offset = 0
    for sentence in sentences:
        span_start = offset
        span_end = offset + len(sentence)
        offset = span_end + 1
        if not _OBLIGATION_KEYWORDS.search(sentence):
            continue
        compound = "and" in sentence.lower() and "," in sentence
        clauses.append(
            _make_clause(doc, sentence, (span_start, span_end), atomic=not compound)
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


# ---------------------------------------------------------------------------
# Strategy 2 — Markdown table rows
# ---------------------------------------------------------------------------


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(_TABLE_SEPARATOR.match(c) for c in cells if c)


def _extract_table_clauses(
    doc: SpecDocument, text: str
) -> list[Clause | HarnessPolicyClause]:
    """Convert each Markdown table data row into a structural clause.

    Format assumed::

        | Header A | Header B | ... |
        |----------|----------|-----|
        | value A  | value B  | ... |   <- becomes a clause

    Rows without a preceding separator are treated as header rows.
    Rows that contain only dashes (separators) are skipped.
    """
    clauses: list[Clause | HarnessPolicyClause] = []
    lines = text.splitlines()
    offset = 0
    header_cells: list[str] = []
    saw_separator = False

    for line in lines:
        line_start = offset
        line_end = offset + len(line)
        offset = line_end + 1

        stripped = line.strip()
        if not stripped.startswith("|"):
            header_cells = []
            saw_separator = False
            continue

        # Parse cells — drop leading/trailing empty strings from split on `|...|`
        raw_cells = stripped.split("|")
        cells = [
            c.strip()
            for c in raw_cells[1:-1]
            if raw_cells[0] == "" and raw_cells[-1] == ""
        ]
        if not cells:
            cells = [c.strip() for c in stripped.split("|") if c.strip()]

        if _is_separator_row(cells):
            saw_separator = True
            continue

        if not saw_separator:
            # This is a header row — capture for later annotation
            header_cells = cells
            continue

        # Data row — convert to clause text
        if header_cells and len(cells) == len(header_cells):
            pairs = [
                f"{h}: {v}"
                for h, v in zip(header_cells, cells, strict=True)
                if v and v not in ("-", "—", "")
            ]
            clause_text = "; ".join(pairs)
        else:
            clause_text = "; ".join(c for c in cells if c and c not in ("-", "—"))

        if not clause_text.strip():
            continue

        clauses.append(_make_clause(doc, clause_text, (line_start, line_end)))

    return clauses


# ---------------------------------------------------------------------------
# Strategy 3 — Markdown bullet items
# ---------------------------------------------------------------------------


def _extract_bullet_clauses(
    doc: SpecDocument, text: str
) -> list[Clause | HarnessPolicyClause]:
    """Extract Markdown bullet-list items that reference a code symbol.

    Only items that contain at least one backtick-delimited symbol are
    included — this filters out generic prose bullets while capturing
    component declarations such as::

        - `cmd_fetch.py` implements the fetch stage

    Items whose text already contains obligation keywords are skipped
    (they were already captured by the normative extractor).
    """
    clauses: list[Clause | HarnessPolicyClause] = []
    lines = text.splitlines()
    offset = 0

    for line in lines:
        line_start = offset
        line_end = offset + len(line)
        offset = line_end + 1

        m = _BULLET_PATTERN.match(line)
        if not m:
            continue

        clause_text = m.group(2).strip()
        if not clause_text or len(clause_text) < 5:
            continue

        # Already captured by normative extractor — skip to avoid duplicates
        if _OBLIGATION_KEYWORDS.search(clause_text):
            continue

        # Require at least one code symbol reference to avoid generic prose
        if not _SYMBOL_PATTERN.search(clause_text):
            continue

        clauses.append(_make_clause(doc, clause_text, (line_start, line_end)))

    return clauses


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
