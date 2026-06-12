"""LLM contract generator (Tier B1).

Spec rule: generated predicates/tests must compile or lint before they can
contribute hard evidence; otherwise they remain soft candidate artefacts.
"""

from __future__ import annotations

import json
from typing import Any

from llm_sca_tooling.impl_check.contract_generator import (
    ContractArtifactGenerator,
    LLMContractGenerator,
    NullContractGenerator,
)
from llm_sca_tooling.impl_check.models import Clause, ClauseGrounding
from llm_sca_tooling.impl_check.report import run_implementation_check
from llm_sca_tooling.impl_check.static_verdict import run_static_verdict

SPEC = """# Mini spec

- The service must validate user input before authentication.
"""


def _clause() -> Clause:
    return Clause(
        clause_id="clause:test:0001",
        doc_id="spec:test",
        text="The service must validate user input before authentication.",
        source_span=(0, 60),
        checkability="static",
        risk_class="functional",
        atomic=True,
    )


def _grounding(method: str = "graph_path") -> ClauseGrounding:
    return ClauseGrounding(
        clause_id="clause:test:0001",
        grounding_method=method,
        symbol_node_ids=["node:function:validate", "node:function:authenticate"],
        confidence="analyser",
    )


def test_llm_generator_is_a_contract_generator() -> None:
    generator = LLMContractGenerator(complete=lambda p: "{}", model_id="m1")
    assert isinstance(generator, ContractArtifactGenerator)


def test_valid_predicate_compiles_and_carries_metadata() -> None:
    def fake_complete(prompt: str) -> str:
        assert "validate user input" in prompt
        assert "node:function:validate" in prompt
        return json.dumps(
            {
                "language": "python",
                "content": (
                    "def predicate(graph):\n"
                    "    return graph.calls('validate', before='authenticate')\n"
                ),
                "target_symbols": ["node:function:validate"],
            }
        )

    generator = LLMContractGenerator(complete=fake_complete, model_id="m1")
    artifact = generator.generate(_clause(), _grounding())

    assert artifact.language == "python"
    assert artifact.artifact_type == "python_predicate"
    assert artifact.compile_status == "passed"
    assert artifact.clause_id == "clause:test:0001"
    assert artifact.target_symbols == ["node:function:validate"]
    assert artifact.confidence > 0.0
    assert "def predicate" in artifact.content


def test_non_compiling_predicate_stays_soft() -> None:
    generator = LLMContractGenerator(
        complete=lambda p: json.dumps(
            {"language": "python", "content": "def broken(:\n    pass"}
        ),
        model_id="m1",
    )
    artifact = generator.generate(_clause(), _grounding())
    assert artifact.compile_status == "failed"
    assert artifact.confidence == 0.0

    # Spec rule: failed compile must not contribute hard evidence — the
    # static verdict for a grounded clause stays unknown.
    verdict = run_static_verdict(_clause(), _grounding(), artifact)
    assert verdict.verdict == "unknown"
    assert verdict.evidence_type == "no_static_evidence"


def test_malformed_llm_output_falls_back_to_null_equivalent() -> None:
    generator = LLMContractGenerator(complete=lambda p: "not json", model_id="m1")
    artifact = generator.generate(_clause(), _grounding())

    null_artifact = NullContractGenerator().generate(_clause(), _grounding())
    assert artifact.artifact_type == null_artifact.artifact_type
    assert artifact.language == null_artifact.language
    assert artifact.compile_status == null_artifact.compile_status
    assert artifact.confidence == 0.0


def test_non_python_language_is_not_compile_checked() -> None:
    generator = LLMContractGenerator(
        complete=lambda p: json.dumps({"language": "semgrep", "content": "rules: []"}),
        model_id="m1",
    )
    artifact = generator.generate(_clause(), _grounding())
    assert artifact.language == "semgrep"
    assert artifact.compile_status == "not_attempted"


def test_run_implementation_check_accepts_injected_generator() -> None:
    calls: list[str] = []

    class SpyGenerator(NullContractGenerator):
        def generate(self, clause: Any, grounding: Any) -> Any:
            calls.append(clause.clause_id)
            return super().generate(clause, grounding)

    report = run_implementation_check(
        spec=SPEC, doc_id="spec:b1", contract_generator=SpyGenerator()
    )
    assert report.report_id
    assert calls  # the injected generator handled every groundable clause
