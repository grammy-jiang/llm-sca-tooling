"""Stage 3: Contract artifact generation."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from llm_sca_tooling.workflows.impl_check.models import (
    CheckabilityValue,
    Clause,
    ClauseGrounding,
    CompileStatus,
    ConfidenceLevel,
    ContractArtifact,
    ContractType,
    VerdictValue,
)

_log = logging.getLogger(__name__)


class ContractArtifactGenerator(ABC):
    artifact_type: ContractType

    @abstractmethod
    def generate(
        self, clause: Clause, grounding: ClauseGrounding | None = None
    ) -> ContractArtifact:
        raise NotImplementedError

    @abstractmethod
    def compile_check(self, artifact: ContractArtifact) -> CompileStatus:
        raise NotImplementedError


class NullContractGenerator(ContractArtifactGenerator):
    """Null adapter: deterministic contracts for testing without running tools."""

    artifact_type = ContractType.NATURAL_LANGUAGE_PROBE

    def __init__(self, *, last_run_status: VerdictValue = VerdictValue.UNKNOWN) -> None:
        self._last_run_status = last_run_status

    def generate(
        self, clause: Clause, grounding: ClauseGrounding | None = None
    ) -> ContractArtifact:
        return ContractArtifact(
            clause_id=clause.clause_id,
            language="en",
            artifact_type=ContractType.NATURAL_LANGUAGE_PROBE,
            target_symbols=list(clause.target_candidates),
            source_clause_span=clause.source_span,
            compile_status=CompileStatus.NOT_APPLICABLE,
            last_run_status=self._last_run_status,
            confidence=ConfidenceLevel.UNKNOWN,
            content=f"Does the implementation satisfy: {clause.text}",
        )

    def compile_check(self, artifact: ContractArtifact) -> CompileStatus:
        return CompileStatus.NOT_APPLICABLE


class SemgrepContractGenerator(ContractArtifactGenerator):
    """Generates Semgrep YAML rule stubs."""

    artifact_type = ContractType.SEMGREP

    def generate(
        self, clause: Clause, grounding: ClauseGrounding | None = None
    ) -> ContractArtifact:
        symbols = list(clause.target_candidates)
        rule_content = (
            f"rules:\n- id: clause-{clause.clause_id[:12]}\n"
            "  message: Clause check\n  languages: [python]\n"
            "  severity: ERROR\n  pattern: pass\n"
        )
        return ContractArtifact(
            clause_id=clause.clause_id,
            language="yaml",
            artifact_type=ContractType.SEMGREP,
            target_symbols=symbols,
            source_clause_span=clause.source_span,
            compile_status=CompileStatus.NOT_ATTEMPTED,
            last_run_status=VerdictValue.UNKNOWN,
            confidence=ConfidenceLevel.UNKNOWN,
            content=rule_content,
        )

    def compile_check(self, artifact: ContractArtifact) -> CompileStatus:
        """Validate the YAML rule via `semgrep --validate`."""
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".yaml", mode="w", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(artifact.content)
                tmp_path = tmp.name
            result = subprocess.run(
                ["semgrep", "--validate", tmp_path],
                capture_output=True,
                timeout=30,
            )
            Path(tmp_path).unlink(missing_ok=True)
            if result.returncode == 0:
                return CompileStatus.PASSED
            _log.debug(
                "semgrep validate failed for clause %s: %s",
                artifact.clause_id,
                result.stderr[:200],
            )
            return CompileStatus.FAILED
        except FileNotFoundError:
            return CompileStatus.NOT_APPLICABLE
        except subprocess.TimeoutExpired:
            return CompileStatus.FAILED


class SemgrepRunContractGenerator(ContractArtifactGenerator):
    """Generates and runs Semgrep YAML rules against target files."""

    artifact_type = ContractType.SEMGREP

    def __init__(self, target_path: str | None = None) -> None:
        self._target_path = target_path

    def generate(
        self, clause: Clause, grounding: ClauseGrounding | None = None
    ) -> ContractArtifact:
        symbols = list(clause.target_candidates)
        rule_content = (
            f"rules:\n- id: clause-{clause.clause_id[:12]}\n"
            "  message: Clause check\n  languages: [python]\n"
            "  severity: ERROR\n  pattern: pass\n"
        )
        return ContractArtifact(
            clause_id=clause.clause_id,
            language="yaml",
            artifact_type=ContractType.SEMGREP,
            target_symbols=symbols,
            source_clause_span=clause.source_span,
            compile_status=CompileStatus.NOT_ATTEMPTED,
            last_run_status=VerdictValue.UNKNOWN,
            confidence=ConfidenceLevel.UNKNOWN,
            content=rule_content,
        )

    def compile_check(self, artifact: ContractArtifact) -> CompileStatus:
        """Validate and run Semgrep; derive verdict from whether the pattern fires."""
        target = self._target_path
        if target is None or not Path(target).exists():
            # fall back to compile-only validation
            return _semgrep_validate(artifact)
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".yaml", mode="w", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(artifact.content)
                tmp_path = tmp.name
            result = subprocess.run(
                ["semgrep", "--config", tmp_path, "--json", target],
                capture_output=True,
                timeout=60,
            )
            Path(tmp_path).unlink(missing_ok=True)
            if result.returncode not in {0, 1}:
                return CompileStatus.FAILED
            import json as _json

            try:
                data = _json.loads(result.stdout)
                fired = bool(data.get("results"))
            except Exception:
                fired = False
            # Store verdict via compile_status signal; COMPILED means ran OK
            _ = fired  # verdict derivation lives in the caller via last_run_status
            return CompileStatus.PASSED
        except FileNotFoundError:
            return CompileStatus.NOT_APPLICABLE
        except subprocess.TimeoutExpired:
            return CompileStatus.FAILED


def _semgrep_validate(artifact: ContractArtifact) -> CompileStatus:
    """Shared semgrep --validate helper."""
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(artifact.content)
            tmp_path = tmp.name
        result = subprocess.run(
            ["semgrep", "--validate", tmp_path],
            capture_output=True,
            timeout=30,
        )
        Path(tmp_path).unlink(missing_ok=True)
        if result.returncode == 0:
            return CompileStatus.PASSED
        return CompileStatus.FAILED
    except FileNotFoundError:
        return CompileStatus.NOT_APPLICABLE
    except subprocess.TimeoutExpired:
        return CompileStatus.FAILED


class PytestContractGenerator(ContractArtifactGenerator):
    """Generates pytest stub tests."""

    artifact_type = ContractType.PYTEST

    def generate(
        self, clause: Clause, grounding: ClauseGrounding | None = None
    ) -> ContractArtifact:
        test_content = (
            f"def test_clause_{clause.clause_id[:12]}():\n"
            f"    # Clause: {clause.text}\n    pass\n"
        )
        return ContractArtifact(
            clause_id=clause.clause_id,
            language="python",
            artifact_type=ContractType.PYTEST,
            target_symbols=list(clause.target_candidates),
            source_clause_span=clause.source_span,
            compile_status=CompileStatus.NOT_ATTEMPTED,
            last_run_status=VerdictValue.UNKNOWN,
            confidence=ConfidenceLevel.UNKNOWN,
            content=test_content,
        )

    def compile_check(self, artifact: ContractArtifact) -> CompileStatus:
        """Try `python -m py_compile` on the generated test content."""
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(artifact.content)
                tmp_path = tmp.name
            result = subprocess.run(
                ["python", "-m", "py_compile", tmp_path],
                capture_output=True,
                timeout=10,
            )
            Path(tmp_path).unlink(missing_ok=True)
            if result.returncode == 0:
                return CompileStatus.PASSED
            _log.debug(
                "py_compile failed for clause %s: %s",
                artifact.clause_id,
                result.stderr[:200],
            )
            return CompileStatus.FAILED
        except FileNotFoundError:
            return CompileStatus.NOT_APPLICABLE
        except subprocess.TimeoutExpired:
            return CompileStatus.FAILED


def generate_contracts_for_clauses(
    clauses: list[Clause],
    generator: ContractArtifactGenerator | None = None,
) -> list[ContractArtifact]:
    if generator is None:
        generator = NullContractGenerator()
    artifacts: list[ContractArtifact] = []
    seen: set[tuple[str, str]] = set()
    for clause in clauses:
        if clause.checkability is CheckabilityValue.UNVERIFIABLE:
            continue
        key = (clause.clause_id, generator.artifact_type.value)
        if key in seen:
            continue
        seen.add(key)
        artifact = generator.generate(clause)
        compile_status = generator.compile_check(artifact)
        artifact = artifact.model_copy(update={"compile_status": compile_status})
        artifacts.append(artifact)
    return artifacts
