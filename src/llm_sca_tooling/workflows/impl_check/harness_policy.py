"""Stage 1: Harness-policy clause detection."""

from __future__ import annotations

import re

from llm_sca_tooling.workflows.impl_check.models import Clause, HarnessPolicyClause

_HARNESS_KEYWORDS = re.compile(
    r"\b(HC[1-6]|hard constraint|AGENTS\.md|harness|gate|permission|policy|overlay|verification)\b",
    re.IGNORECASE,
)


def is_harness_policy_clause(clause: Clause) -> bool:
    return bool(_HARNESS_KEYWORDS.search(clause.text))


def to_harness_policy_clause(
    clause: Clause,
    policy_source: str = "AGENTS.md",
    enforcement_mechanism: str = "gate",
    checked_by_tool: str = "",
    harness_stage_required: str = "",
) -> HarnessPolicyClause:
    base = clause.model_dump()
    extra_keys = {
        "policy_source",
        "enforcement_mechanism",
        "checked_by_tool",
        "harness_stage_required",
    }
    base = {k: v for k, v in base.items() if k not in extra_keys}
    base["harness_policy_flag"] = True
    return HarnessPolicyClause(
        **base,
        policy_source=policy_source,
        enforcement_mechanism=enforcement_mechanism,
        checked_by_tool=checked_by_tool,
        harness_stage_required=harness_stage_required,
    )


def detect_and_upgrade_harness_policy_clauses(
    clauses: list[Clause],
) -> list[Clause]:
    result: list[Clause] = []
    for clause in clauses:
        if is_harness_policy_clause(clause) and not isinstance(
            clause, HarnessPolicyClause
        ):
            result.append(to_harness_policy_clause(clause))
        else:
            result.append(clause)
    return result
