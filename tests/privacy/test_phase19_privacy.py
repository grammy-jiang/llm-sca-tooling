from __future__ import annotations

from llm_sca_tooling.privacy.export_delete import (
    DELETE_CONFIRMATION,
    PrivacyDeletionRequest,
    PrivacyExportRequest,
    build_privacy_export_payload,
    validate_delete_request,
)
from llm_sca_tooling.privacy.redaction import (
    contains_sensitive_value,
    redact_for_export,
)
from llm_sca_tooling.privacy.retention_policy import (
    RetentionAction,
    RetentionPolicy,
    RetentionPolicyEvaluator,
)


def test_redaction_removes_sensitive_keys() -> None:
    payload = {"safe": "ok", "authorization": "placeholder"}
    assert contains_sensitive_value(payload)
    assert redact_for_export(payload)["authorization"] == "[REDACTED]"


def test_retention_policy_marks_expired_records_for_export() -> None:
    policy = RetentionPolicy(operational_record_days=1)
    decisions = RetentionPolicyEvaluator(policy).evaluate_records(
        [{"record_id": "record:1", "created_ts": "2026-05-01T00:00:00Z"}],
        now_ts="2026-05-10T00:00:00Z",
    )
    assert decisions[0].action == RetentionAction.EXPORT


def test_privacy_export_redacts_records_and_delete_requires_confirmation() -> None:
    payload = build_privacy_export_payload(
        [{"record_id": "record:1", "authorization": "placeholder"}],
        PrivacyExportRequest(requester="ops", scope="run:1", reason="audit"),
    )
    assert payload["records"][0]["authorization"] == "[REDACTED]"
    rejected = validate_delete_request(
        PrivacyDeletionRequest(
            requester="ops", scope="run:1", reason="cleanup", dry_run=False
        )
    )
    assert not rejected.approved
    approved = validate_delete_request(
        PrivacyDeletionRequest(
            requester="ops",
            scope="run:1",
            reason="cleanup",
            dry_run=False,
            confirmation=DELETE_CONFIRMATION,
        )
    )
    assert approved.approved
