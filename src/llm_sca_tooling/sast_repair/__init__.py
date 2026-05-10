"""Phase 12 SAST repair package."""

from llm_sca_tooling.sast_repair.alert_binding import bind_alert
from llm_sca_tooling.sast_repair.alert_classification import classify_alert
from llm_sca_tooling.sast_repair.analyser_rerun import rerun_analyser
from llm_sca_tooling.sast_repair.build_test_runner import run_build_and_tests
from llm_sca_tooling.sast_repair.corpus_adapter import (
    CleanCorpusAdapter,
    LocalFixtureCorpusAdapter,
)
from llm_sca_tooling.sast_repair.models import (
    AlertBinding,
    AlertClassification,
    AlertSpan,
    AnalyserRerunResult,
    BindingConfidence,
    BuildTestResult,
    ClassificationConfidence,
    ClassificationValue,
    GenerationMethod,
    PredicateExampleRecord,
    PredicateMetadata,
    RemainingRiskNote,
    RepairContext,
    RerunStatus,
    RetrievalMethod,
    RiskLevel,
    SandboxResult,
    SARIFDeltaVerificationResult,
    SASTPatch,
    SASTRepairReport,
    SuppressionKind,
    SuppressionProposal,
    Verdict,
)
from llm_sca_tooling.sast_repair.patch_generator import (
    NullPatchGenerator,
    PatchGeneratorInterface,
)
from llm_sca_tooling.sast_repair.predicate_examples import get_predicate_examples
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata
from llm_sca_tooling.sast_repair.remaining_risk import generate_remaining_risk
from llm_sca_tooling.sast_repair.repair_context import build_repair_context
from llm_sca_tooling.sast_repair.report import run_sast_repair
from llm_sca_tooling.sast_repair.rule_evolution import evolve_static_rules
from llm_sca_tooling.sast_repair.sandbox import SandboxManager
from llm_sca_tooling.sast_repair.sarif_delta_verifier import verify_sarif_delta
from llm_sca_tooling.sast_repair.suppression import propose_suppression

__all__ = [
    "AlertBinding",
    "AlertClassification",
    "AlertSpan",
    "AnalyserRerunResult",
    "BindingConfidence",
    "BuildTestResult",
    "CleanCorpusAdapter",
    "ClassificationConfidence",
    "ClassificationValue",
    "GenerationMethod",
    "LocalFixtureCorpusAdapter",
    "NullPatchGenerator",
    "PatchGeneratorInterface",
    "PredicateExampleRecord",
    "PredicateMetadata",
    "RemainingRiskNote",
    "RepairContext",
    "RerunStatus",
    "RetrievalMethod",
    "RiskLevel",
    "SARIFDeltaVerificationResult",
    "SASTPatch",
    "SASTRepairReport",
    "SandboxManager",
    "SandboxResult",
    "SuppressionKind",
    "SuppressionProposal",
    "Verdict",
    "bind_alert",
    "build_repair_context",
    "classify_alert",
    "evolve_static_rules",
    "extract_predicate_metadata",
    "generate_remaining_risk",
    "get_predicate_examples",
    "propose_suppression",
    "rerun_analyser",
    "run_build_and_tests",
    "run_sast_repair",
    "verify_sarif_delta",
]
