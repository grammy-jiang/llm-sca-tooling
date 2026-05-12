"""Stage 4: Clause-to-code grounding.

Strategies are tried in priority order:

1. **symbol_match** — clause contains at least one backtick-delimited code
   symbol; grounded to those symbols and their inferred file paths.
1b. **backtick_reference** — clause has a backtick expression that didn't
   resolve to a clean symbol (e.g. `store-*`, type annotations, paths).
2. **service_spec** — clause is a table row describing an external service
   cost constraint (e.g. ``Service: X; Cost: Free ...``).
2b. **scope_definition** — capability scope matrix rows and phase-assignment
   records (✅, P0–P5 tags, Post-v1, scaffold annotations).
2c. **structured_record** — semi-colon-separated key/value table rows from
   architectural artefacts (decision log, revision history, tier descriptions,
   comparison tables).  Their presence in the spec IS the evidence.
3. **policy_principle** — design-principle / responsibility-boundary statements.
4. **ungrounded** — fallback when none of the above apply.
"""

from __future__ import annotations

import re

from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseGrounding,
    HarnessPolicyClause,
)

# Service/cost table rows: "Service: X; Cost: Free..." or "free-tier"
_SERVICE_SPEC_PATTERN = re.compile(
    r"(?i)(cost\s*:\s*free|free.tier)",
)

# Backtick code reference: clause has backtick-delimited content that looks like
# a code expression, path, or command, even if the symbol pattern didn't extract
# a clean identifier (e.g. `store-*`, `_schema_version: str`, `core/`, `https://`).
_BACKTICK_CODE_PATTERN = re.compile(r"`[A-Za-z_/]")

# Capability scope matrix rows: contain ✅ markers, phase tags (P0–P5), or
# explicit Post-v1 / scaffold / v1 scope annotations.  These rows define
# architectural scope and are satisfied by their presence in the spec.
# Use \b word boundary so [P3] tags in backtick-delimited text also match.
_SCOPE_DEFINITION_PATTERN = re.compile(
    r"(?:✅|(?:Post-v1|scaffold|v1)\s*(?:Phase)?|\bP[0-5](?:\+[0-9])?\b|"
    r"(?:Phase|Capability|Feature)\s*:\s*\w)",
    re.IGNORECASE,
)

# Structured architectural record rows: semi-colon-separated key:value pairs
# from decision logs, revision history, comparison tables, tier descriptions,
# etc.  Pattern: at least two "word(s): value" groups separated by ";".
_STRUCTURED_RECORD_PATTERN = re.compile(
    r"\w[\w *()]*:\s*\S.*;\s*\w[\w *()]*:\s*\S",
)

# Design-principle / responsibility-boundary clauses (no code symbols)
_POLICY_PRINCIPLE_PATTERN = re.compile(
    r"(?i)"
    r"("
    r"must\s+not\s+autonomously"
    r"|agent\s+decides"
    r"|must\s+apply\s+a\s+threshold"
    r"|explicit\s+input\s+parameter"
    r"|responsibility\s*:.*(?:non.deterministic|deterministic|judgment|execution)"
    # Architectural verbs that are specific to design-principle statements
    r"|(?:must|shall|should)\s+(?:coordinate|orchestrat|preserv|conform|enforce\w*|not\s+interpret)"
    r"|(?:stage|gate|tier)\s+\d"
    r"|(?:non-autonomy|agent.package\s+split|capability.tier)"
    r")",
    re.DOTALL,
)


def ground_clause(clause: Clause | HarnessPolicyClause) -> ClauseGrounding:
    """Stage 4: ground a clause to a grounding method.

    Priority: symbol_match → backtick_reference → service_spec →
    scope_definition → policy_principle → structured_record → ungrounded.
    """
    # Strategy 1: symbol match
    if clause.target_candidates:
        symbol_ids = [f"symbol:{t}" for t in clause.target_candidates]
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="symbol_match",
            symbol_node_ids=symbol_ids,
            file_node_ids=[
                f"file:{t.replace('.', '/')}.py" for t in clause.target_candidates
            ],
            confidence="heuristic",
        )

    # Strategy 1b: backtick code reference — clause mentions a code expression
    # that the strict symbol pattern couldn't capture (e.g. `store-*`, type
    # annotations, paths with trailing slash, URL schemes).
    if _BACKTICK_CODE_PATTERN.search(clause.text):
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="backtick_reference",
            confidence="heuristic",
        )

    # Strategy 2: service_spec — external-service cost table rows
    if _SERVICE_SPEC_PATTERN.search(clause.text):
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="service_spec",
            confidence="heuristic",
        )

    # Strategy 2b: scope_definition — capability scope matrix rows and phase
    # assignment records.  These define what is in/out of scope; their presence
    # in the spec IS the evidence of compliance.
    if _SCOPE_DEFINITION_PATTERN.search(clause.text):
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="scope_definition",
            confidence="heuristic",
        )

    # Strategy 3: policy_principle — design-principle / responsibility clauses
    if _POLICY_PRINCIPLE_PATTERN.search(clause.text):
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="policy_principle",
            confidence="heuristic",
        )

    # Strategy 2c: structured_record — semi-colon-separated key/value rows
    # from decision logs, revision history, comparison tables, tier tables, etc.
    if _STRUCTURED_RECORD_PATTERN.search(clause.text):
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="structured_record",
            confidence="heuristic",
        )

    return ClauseGrounding(
        clause_id=clause.clause_id,
        grounding_method="ungrounded",
        confidence="unknown",
        ungrounded_reason="no_target_candidates",
    )
