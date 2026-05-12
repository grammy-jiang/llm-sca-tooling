"""Stage 4: Clause-to-code grounding.

Three strategies are tried in priority order:

1. **symbol_match** — clause contains at least one backtick-delimited code
   symbol; grounded to those symbols and their inferred file paths.
2. **service_spec** — clause is a table row describing an external service
   cost constraint (e.g. ``Service: X; Cost: Free ...``).  The service is
   confirmed free-tier by the presence of source files that use it; heuristic
   confidence.
3. **policy_principle** — clause is a design-principle or responsibility-
   boundary statement (non-autonomy, agent/package split, explicit-config
   policy).  These cannot be verified by symbol matching; heuristic confidence
   is assigned based on architectural evidence.
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

# Design-principle / responsibility-boundary clauses (no code symbols)
_POLICY_PRINCIPLE_PATTERN = re.compile(
    r"(?i)"
    r"("
    r"must\s+not\s+autonomously"
    r"|agent\s+decides"
    r"|must\s+apply\s+a\s+threshold"
    r"|explicit\s+input\s+parameter"
    r"|responsibility\s*:.*(?:non.deterministic|deterministic|judgment|execution)"
    r")",
    re.DOTALL,
)


def ground_clause(clause: Clause | HarnessPolicyClause) -> ClauseGrounding:
    """Stage 4: symbol_match → service_spec → policy_principle → ungrounded."""
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

    # Strategy 2: service_spec — external-service cost table rows
    if _SERVICE_SPEC_PATTERN.search(clause.text):
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="service_spec",
            confidence="heuristic",
        )

    # Strategy 3: policy_principle — design-principle / responsibility clauses
    if _POLICY_PRINCIPLE_PATTERN.search(clause.text):
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="policy_principle",
            confidence="heuristic",
        )

    return ClauseGrounding(
        clause_id=clause.clause_id,
        grounding_method="ungrounded",
        confidence="unknown",
        ungrounded_reason="no_target_candidates",
    )
