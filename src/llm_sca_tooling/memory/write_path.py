"""Five-gate write-path validation pipeline."""

from __future__ import annotations

import re

from llm_sca_tooling.memory.models import (
    MemoryOptInPolicy,
    TrajectoryRecord,
    WritePathResult,
)
from llm_sca_tooling.memory.policy import MemoryDisabledError, check_memory_enabled

# Simplified secret pattern — real implementation uses detect-secrets patterns
_SECRET_PATTERN = re.compile(
    r"(?:password|secret|token|api_key|credential)\s*[:=]\s*\S+",
    re.IGNORECASE,
)

_FORBIDDEN_SNIPPET_TYPES = {"raw_prompt", "full_trace", "full_source", "command_output"}


def validate_and_write(
    record: TrajectoryRecord,
    policy: MemoryOptInPolicy,
) -> WritePathResult:
    result = WritePathResult(trajectory_id=record.trajectory_id)
    gates_passed: list[str] = []
    gate_failures: list[str] = []

    # Gate 1: opt-in check
    try:
        check_memory_enabled(policy, record.repo_id)
        gates_passed.append("opt_in_check")
    except MemoryDisabledError as exc:
        gate_failures.append(f"opt_in_check:{exc}")
        return result.model_copy(
            update={"gate_failures": gate_failures, "written": False}
        )

    # Gate 2: required fields
    missing = [f for f in ("source_run_id", "repo_id") if not getattr(record, f, None)]
    if missing:
        gate_failures.append(f"required_fields:{missing}")
        return result.model_copy(
            update={"gate_failures": gate_failures, "written": False}
        )
    gates_passed.append("required_fields")

    # Gate 3: data classification
    if record.retention_class not in {
        "ephemeral",
        "workspace_local",
        "long_term",
        "archived",
    }:
        gate_failures.append(
            f"data_classification:invalid_retention_class:{record.retention_class}"
        )
        return result.model_copy(
            update={"gate_failures": gate_failures, "written": False}
        )
    gates_passed.append("data_classification")

    # Gate 4: secret scan
    secret_found = False
    if policy.secret_scan_required:
        record_text = record.model_dump_json()
        if _SECRET_PATTERN.search(record_text):
            secret_found = True
            gate_failures.append("secret_scan:secret_detected")
            return result.model_copy(
                update={
                    "gates_passed": gates_passed,
                    "gate_failures": gate_failures,
                    "secret_detected": True,
                    "written": False,
                }
            )
    gates_passed.append("secret_scan")

    # Gate 5: forbidden snippet types
    forbidden = [
        sid for sid in record.bounded_snippet_ids if sid in _FORBIDDEN_SNIPPET_TYPES
    ]
    if forbidden:
        gate_failures.append(f"snippet_type_check:forbidden:{forbidden}")
        return result.model_copy(
            update={"gate_failures": gate_failures, "written": False}
        )
    gates_passed.append("snippet_type_check")

    # Contradiction check (non-blocking)
    contradiction = False
    contradiction_detail = None
    if not record.graph_snapshot_id:
        contradiction = True
        contradiction_detail = "missing_graph_snapshot_id"

    return result.model_copy(
        update={
            "gates_passed": gates_passed,
            "gate_failures": gate_failures,
            "secret_detected": secret_found,
            "contradiction_detected": contradiction,
            "contradiction_detail": contradiction_detail,
            "review_state_set": "unreviewed",
            "written": True,
        }
    )
