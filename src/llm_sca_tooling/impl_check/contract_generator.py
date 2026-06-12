"""Stage 3: Contract artefact generation — null adapter and LLM boundary.

The LLM generator follows the project's boundary pattern (see
``memory.relabelling.llm_relabeller``): the completion callable is injected so
the module carries no network or provider dependency (HC5), and output is
fail-closed — generated predicates must compile before they can contribute
hard evidence; otherwise they remain soft candidate artefacts.
"""

from __future__ import annotations

import ast
import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable

from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseGrounding,
    HarnessPolicyClause,
    ImplContractArtifact,
)


class ContractArtifactGenerator(ABC):
    artifact_type: str

    @abstractmethod
    def generate(
        self, clause: Clause | HarnessPolicyClause, grounding: ClauseGrounding
    ) -> ImplContractArtifact:
        raise NotImplementedError

    def compile_check(self, artifact: ImplContractArtifact) -> str:
        return "not_attempted"


class NullContractGenerator(ContractArtifactGenerator):
    artifact_type = "natural_language_probe"

    def generate(
        self, clause: Clause | HarnessPolicyClause, grounding: ClauseGrounding
    ) -> ImplContractArtifact:
        return ImplContractArtifact(
            artifact_id=f"artifact:{uuid.uuid4().hex[:8]}",
            clause_id=clause.clause_id,
            language="natural_language",
            artifact_type="natural_language_probe",
            target_symbols=grounding.symbol_node_ids[:3],
            source_clause_span=clause.source_span,
            compile_status="not_applicable",
            last_run_status="not_run",
            confidence=0.0,
            content=f"Does the implementation satisfy: {clause.text[:120]}?",
        )


_PROMPT_TEMPLATE = """\
You are generating a verification predicate for an implementation-check
clause. Produce a small, self-contained checker for the clause below.

clause_id: {clause_id}
clause_text: {clause_text}
risk_class: {risk_class}
grounded_symbols: {symbols}
grounded_files: {files}

Respond with a single JSON object and nothing else:
{{"language": "python|semgrep|natural_language",
 "content": "<the predicate source — for python, a function taking a graph
              handle and returning bool>",
 "target_symbols": ["<node ids from grounded_symbols this predicate checks>"]}}
"""

# Confidence assigned to a predicate that parsed and compiled. The predicate
# has not been *executed*, so this never reaches analyser-grade certainty.
_COMPILED_CONFIDENCE = 0.5


class LLMContractGenerator(ContractArtifactGenerator):
    """Contract generator backed by an injected LLM completion callable.

    Fail-closed: unparseable output degrades to the null generator's
    natural-language probe; python predicates that do not compile are emitted
    with ``compile_status="failed"`` so the static verdict stage treats them
    as soft candidate artefacts, never hard evidence.
    """

    artifact_type = "python_predicate"
    version = "b1.v1"

    def __init__(
        self,
        *,
        complete: Callable[[str], str],
        model_id: str,
    ) -> None:
        self._complete = complete
        self.model_id = model_id

    def generate(
        self, clause: Clause | HarnessPolicyClause, grounding: ClauseGrounding
    ) -> ImplContractArtifact:
        prompt = _PROMPT_TEMPLATE.format(
            clause_id=clause.clause_id,
            clause_text=clause.text,
            risk_class=getattr(clause, "risk_class", "unknown"),
            symbols=", ".join(grounding.symbol_node_ids[:5]) or "none",
            files=", ".join(grounding.file_node_ids[:5]) or "none",
        )
        raw = self._complete(prompt)
        parsed = self._parse_response(raw)
        content = parsed.get("content")
        language = parsed.get("language")
        if not isinstance(content, str) or not content.strip():
            return NullContractGenerator().generate(clause, grounding)
        if not isinstance(language, str) or not language:
            language = "natural_language"

        raw_symbols = parsed.get("target_symbols")
        symbol_candidates = raw_symbols if isinstance(raw_symbols, list) else []
        target_symbols = [
            symbol
            for symbol in symbol_candidates
            if isinstance(symbol, str) and symbol in grounding.symbol_node_ids
        ] or grounding.symbol_node_ids[:3]

        artifact = ImplContractArtifact(
            artifact_id=f"artifact:llm:{uuid.uuid4().hex[:8]}",
            clause_id=clause.clause_id,
            language=language,
            artifact_type=(
                "python_predicate" if language == "python" else f"{language}_probe"
            ),
            target_symbols=target_symbols,
            source_clause_span=clause.source_span,
            compile_status="not_attempted",
            last_run_status="not_run",
            confidence=0.0,
            content=content,
        )
        compile_status = self.compile_check(artifact)
        return artifact.model_copy(
            update={
                "compile_status": compile_status,
                "confidence": (
                    _COMPILED_CONFIDENCE if compile_status == "passed" else 0.0
                ),
            }
        )

    def compile_check(self, artifact: ImplContractArtifact) -> str:
        """Compile-gate python predicates; other languages are not attempted."""
        if artifact.language != "python":
            return "not_attempted"
        try:
            ast.parse(artifact.content)
        except SyntaxError:
            return "failed"
        return "passed"

    @staticmethod
    def _parse_response(raw: str) -> dict[str, object]:
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed
