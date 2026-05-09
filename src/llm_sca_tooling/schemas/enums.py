"""Stable enum values used by Phase 1 contracts."""

from __future__ import annotations

from enum import StrEnum


class SchemaFamily(StrEnum):
    GRAPH = "graph"
    RUN_RECORD = "run-record"
    EVIDENCE = "evidence"
    VERDICT = "verdict"
    HARNESS_CONDITION = "harness-condition"
    GOVERNANCE = "governance"
    READINESS = "readiness"
    INCIDENT = "incident"


class IndexStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SnapshotConsistency(StrEnum):
    CLEAN = "clean"
    DIRTY = "dirty"
    STALE = "stale"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RedactionStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    REDACTED = "redacted"
    HASH_ONLY = "hash_only"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class DerivationType(StrEnum):
    PARSER = "parser"
    ANALYSER = "analyser"
    BUILD = "build"
    TEST = "test"
    TRACE = "trace"
    LLM = "llm"
    HEURISTIC = "heuristic"
    POLICY = "policy"
    REVIEW = "review"


class EvidenceStrength(StrEnum):
    HARD_STATIC = "hard_static"
    HARD_DYNAMIC = "hard_dynamic"
    STRUCTURED_REPOSITORY = "structured_repository"
    CALIBRATED_MODEL = "calibrated_model"
    SOFT_LLM = "soft_llm"


EVIDENCE_STRENGTH_RANK = {
    EvidenceStrength.HARD_STATIC: 5,
    EvidenceStrength.HARD_DYNAMIC: 4,
    EvidenceStrength.STRUCTURED_REPOSITORY: 3,
    EvidenceStrength.CALIBRATED_MODEL: 2,
    EvidenceStrength.SOFT_LLM: 1,
}


class ArtifactKind(StrEnum):
    GRAPH_CHUNK = "graph_chunk"
    SARIF = "sarif"
    TRACE = "trace"
    DIFF = "diff"
    TEST_OUTPUT = "test_output"
    LOG = "log"
    SUMMARY = "summary"
    REPORT = "report"
    SCHEMA = "schema"
    OTHER = "other"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    NOTE = "note"
    NONE = "none"
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GraphNodeType(StrEnum):
    REPO = "repo"
    PACKAGE = "package"
    DIRECTORY = "directory"
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    TYPE = "type"
    INTERFACE = "interface"
    IDL_INTERFACE = "idl_interface"
    HTTP_ROUTE = "http_route"
    WEBSOCKET_EVENT = "websocket_event"
    GRPC_SERVICE = "grpc_service"
    PROTOBUF_MESSAGE = "protobuf_message"
    DOCUMENT = "document"
    DESIGN_CLAUSE = "design_clause"
    INTENT_NODE = "intent_node"
    CONTRACT_ARTIFACT = "contract_artifact"
    GENERATED_TEST = "generated_test"
    PREDICATE = "predicate"
    TEST = "test"
    RUNTIME_TRACE = "runtime_trace"
    SAST_RULE = "sast_rule"
    SARIF_ALERT = "sarif_alert"
    BUILD_TARGET = "build_target"
    CI_JOB = "ci_job"
    EVAL_RUN = "eval_run"
    PATCH = "patch"
    DIFF_HUNK = "diff_hunk"
    RISK_FINDING = "risk_finding"
    VERDICT = "verdict"
    TRAJECTORY = "trajectory"
    ISSUE_CLASS = "issue_class"
    FL_DECISION = "fl_decision"
    PATCH_CLASS = "patch_class"
    OUTCOME = "outcome"
    SESSION = "session"
    RUN_RECORD = "run_record"
    RUN_EVENT = "run_event"
    HARNESS_CONDITION = "harness_condition"
    PERMISSION_PROFILE = "permission_profile"
    TOOL_POLICY = "tool_policy"
    TOOL_CALL = "tool_call"
    APPROVAL = "approval"
    BUDGET_EVENT = "budget_event"
    COMPACTION_EVENT = "compaction_event"
    MONITOR_ALERT = "monitor_alert"
    INCIDENT = "incident"
    READINESS_SCORE = "readiness_score"
    MAINTAINABILITY_ORACLE = "maintainability_oracle"
    MANIFEST_REGRESSION = "manifest_regression"


class GraphEdgeType(StrEnum):
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    DATAFLOW = "dataflow"
    TESTS = "tests"
    DOCUMENTS = "documents"
    DECOMPOSES_TO = "decomposes_to"
    CHECKS = "checks"
    SATISFIES = "satisfies"
    VIOLATES = "violates"
    IMPLEMENTS = "implements"
    EXPOSES = "exposes"
    CONSUMES = "consumes"
    FFI = "ffi"
    NULLABLE = "nullable"
    OWNS = "owns"
    INSTANTIATES = "instantiates"
    WARNED_BY = "warned_by"
    FIXED_BY = "fixed_by"
    CHANGED_BY = "changed_by"
    OBSERVED_IN = "observed_in"
    USED_TOOL = "used_tool"
    APPROVED_BY = "approved_by"
    DENIED_BY = "denied_by"
    VERIFIED_BY = "verified_by"
    BLOCKED_BY = "blocked_by"
    COMPACTED_TO = "compacted_to"
    PROMOTED_TO = "promoted_to"
    TRIGGERED_INCIDENT = "triggered_incident"


class VerdictValue(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    SAFE = "safe"
    RISKY = "risky"
    UNKNOWN = "unknown"
    PROCESS_COMPLIANT = "process-compliant"
    PROCESS_NONCOMPLIANT = "process-noncompliant"
    TRACE_INCOMPLETE = "trace-incomplete"
    BUDGET_EXHAUSTED = "budget-exhausted"
    NEEDS_READINESS_WORK = "needs-readiness-work"


class PolicyAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    CHECKPOINT = "checkpoint"
    FORCE_UNKNOWN = "force_unknown"
    NOT_APPLICABLE = "not_applicable"


class HarnessStage(StrEnum):
    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class DriftClassification(StrEnum):
    MISSING = "missing"
    STALE = "stale"
    RELAXED = "relaxed"
    OUT_OF_STAGE = "out-of-stage"
    CLEAN = "clean"


class Status(StrEnum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"
    CREATED = "created"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PermissionMode(StrEnum):
    READ = "read"
    SEARCH = "search"
    EDIT = "edit"
    EXECUTE = "execute"
    REVIEW = "review"
    COMMIT = "commit"


class SideEffectClass(StrEnum):
    NONE = "none"
    READ_ONLY = "read_only"
    WRITES_REPO = "writes_repo"
    WRITES_OUTSIDE_REPO = "writes_outside_repo"
    EXECUTES_CODE = "executes_code"
    NETWORK = "network"
    DESTRUCTIVE = "destructive"
    RELEASE = "release"
