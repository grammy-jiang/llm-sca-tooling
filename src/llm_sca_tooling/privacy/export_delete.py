"""Privacy export and deletion receipts."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.privacy.redaction import redact_for_export
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel

DELETE_CONFIRMATION = "DELETE_LEDGER_RECORDS"


class PrivacyExportRequest(StrictBaseModel):
    requester: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    redacted: bool = True


class PrivacyDeletionRequest(StrictBaseModel):
    requester: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    dry_run: bool = True
    confirmation: str | None = None


class PrivacyActionReceipt(StrictBaseModel):
    action: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    requester: str = Field(min_length=1)
    dry_run: bool
    approved: bool
    affected_ids: list[str] = Field(default_factory=list)


def build_privacy_export_payload(
    records: list[JsonObject], request: PrivacyExportRequest
) -> JsonObject:
    payload_records = (
        [redact_for_export(record) for record in records]
        if request.redacted
        else records
    )
    receipt = PrivacyActionReceipt(
        action="export",
        scope=request.scope,
        requester=request.requester,
        dry_run=False,
        approved=True,
        affected_ids=[str(record.get("record_id", "")) for record in records],
    )
    return {
        "request": request.model_dump(mode="json"),
        "receipt": receipt.model_dump(mode="json"),
        "records": payload_records,
    }


def validate_delete_request(request: PrivacyDeletionRequest) -> PrivacyActionReceipt:
    approved = request.dry_run or request.confirmation == DELETE_CONFIRMATION
    return PrivacyActionReceipt(
        action="delete",
        scope=request.scope,
        requester=request.requester,
        dry_run=request.dry_run,
        approved=approved,
        affected_ids=[],
    )
