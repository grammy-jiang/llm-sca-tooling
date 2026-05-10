"""Phase 15 change-type classification."""

from __future__ import annotations

from enum import StrEnum

from llm_sca_tooling.patch_review.models import ChangedSymbolRecord


class ChangeType(StrEnum):
    INTERNAL_IMPLEMENTATION = "internal_implementation"
    PUBLIC_API_CHANGE = "public_api_change"
    IDL_SCHEMA_CONTRACT_CHANGE = "idl_schema_contract_change"
    SECURITY_SENSITIVE_CHANGE = "security_sensitive_change"
    GENERATED_FILE_CHANGE = "generated_file_change"
    MIXED = "mixed"
    UNKNOWN = "unknown"


_IDL_PATTERNS = (
    ".proto",
    ".thrift",
    ".idl",
    ".wsdl",
    ".avsc",
    ".avro",
    "openapi",
    "swagger",
)

_SECURITY_KEYWORDS = (
    "auth",
    "crypt",
    "perm",
    "secret",
    "token",
    "password",
    "passwd",
    "credential",
    "cwe",
    "sanitize",
    "escape",
    "jwt",
    "oauth",
    "acl",
    "rbac",
)


def _is_idl_path(file_path: str) -> bool:
    lower = file_path.lower()
    return any(pat in lower for pat in _IDL_PATTERNS)


def _is_security_sensitive(record: ChangedSymbolRecord) -> bool:
    lower = record.file_path.lower() + " " + record.symbol_path.lower()
    return any(kw in lower for kw in _SECURITY_KEYWORDS)


def classify_change_type(
    records: list[ChangedSymbolRecord],
    *,
    security_node_ids: set[str] | None = None,
) -> tuple[ChangeType, list[ChangeType]]:
    """Classify the change type from a list of ChangedSymbolRecord.

    Returns a tuple of (primary_type, applicable_types).
    If multiple change types apply, primary_type is MIXED.
    """
    if not records:
        return ChangeType.UNKNOWN, []

    applicable: set[ChangeType] = set()

    for rec in records:
        if rec.is_generated:
            applicable.add(ChangeType.GENERATED_FILE_CHANGE)
        if rec.is_public_api:
            applicable.add(ChangeType.PUBLIC_API_CHANGE)
        if _is_idl_path(rec.file_path):
            applicable.add(ChangeType.IDL_SCHEMA_CONTRACT_CHANGE)
        if _is_security_sensitive(rec) or (
            security_node_ids
            and rec.graph_node_id
            and rec.graph_node_id in security_node_ids
        ):
            applicable.add(ChangeType.SECURITY_SENSITIVE_CHANGE)

    if not applicable:
        return ChangeType.INTERNAL_IMPLEMENTATION, [ChangeType.INTERNAL_IMPLEMENTATION]

    if len(applicable) > 1:
        return ChangeType.MIXED, sorted(applicable)

    only = next(iter(applicable))
    return only, [only]


__all__ = ["ChangeType", "classify_change_type"]
