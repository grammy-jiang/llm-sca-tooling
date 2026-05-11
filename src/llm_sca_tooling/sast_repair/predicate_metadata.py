"""Predicate metadata extraction."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.models import AlertBinding, PredicateMetadata


def extract_predicate_metadata(binding: AlertBinding) -> PredicateMetadata:
    family = binding.rule_family
    if family == "injection":
        predicate = "untrusted input reaches command or query sink"
        negated = "input is validated or parameterized before the sink"
        guidance = "Use parameterized APIs or validate input before use."
    elif family == "nullderef":
        predicate = "nullable value is dereferenced without a guard"
        negated = "value is checked for null before dereference"
        guidance = "Add an explicit null/None guard before dereference."
    else:
        predicate = "rule predicate fired"
        negated = None
        guidance = "Follow analyser rule guidance and preserve behaviour."
    return PredicateMetadata(
        rule_id=binding.rule_id,
        rule_family=family,
        predicate_text=predicate,
        negated_predicate_text=negated,
        cwe_ids=binding.cwe_ids,
        severity="error" if family == "injection" else "warning",
        description=(
            f"{binding.rule_id} fired for {binding.file_path or 'unknown file'}"
        ),
        fix_guidance=guidance,
        available_examples=1 if negated else 0,
        confidence="heuristic" if negated is None else "analyser",
    )
