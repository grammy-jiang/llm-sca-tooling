"""Tests for ChangeType enum and change-type classifier."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.change_type import ChangeType, classify_change_type
from llm_sca_tooling.patch_review.models import ChangedSymbolRecord, ChangeKind


def _rec(
    *,
    file_path: str = "src/app.py",
    symbol_path: str = "app.func",
    is_generated: bool = False,
    is_public_api: bool = False,
    is_interface_boundary: bool = False,
    graph_node_id: str | None = None,
) -> ChangedSymbolRecord:
    return ChangedSymbolRecord(
        diff_id="diff-001",
        file_path=file_path,
        symbol_path=symbol_path,
        symbol_type="function",
        change_kind=ChangeKind.MODIFIED_BODY,
        is_generated=is_generated,
        is_public_api=is_public_api,
        is_interface_boundary=is_interface_boundary,
        graph_node_id=graph_node_id,
    )


class TestChangeTypeEnum:
    def test_all_values_present(self) -> None:
        values = {ct.value for ct in ChangeType}
        assert "internal_implementation" in values
        assert "public_api_change" in values
        assert "idl_schema_contract_change" in values
        assert "security_sensitive_change" in values
        assert "generated_file_change" in values
        assert "mixed" in values
        assert "unknown" in values

    def test_exhaustive_count(self) -> None:
        assert len(ChangeType) == 7


class TestClassifyChangeType:
    def test_empty_records_returns_unknown(self) -> None:
        ct, applicable = classify_change_type([])
        assert ct == ChangeType.UNKNOWN
        assert applicable == []

    def test_internal_implementation(self) -> None:
        rec = _rec()
        ct, applicable = classify_change_type([rec])
        assert ct == ChangeType.INTERNAL_IMPLEMENTATION

    def test_public_api(self) -> None:
        rec = _rec(is_public_api=True)
        ct, applicable = classify_change_type([rec])
        assert ct == ChangeType.PUBLIC_API_CHANGE

    def test_generated_file(self) -> None:
        rec = _rec(is_generated=True)
        ct, applicable = classify_change_type([rec])
        assert ct == ChangeType.GENERATED_FILE_CHANGE

    def test_idl_path(self) -> None:
        rec = _rec(file_path="api/service.proto")
        ct, applicable = classify_change_type([rec])
        assert ct == ChangeType.IDL_SCHEMA_CONTRACT_CHANGE

    def test_openapi_path(self) -> None:
        rec = _rec(file_path="api/openapi.yaml")
        ct, applicable = classify_change_type([rec])
        assert ct == ChangeType.IDL_SCHEMA_CONTRACT_CHANGE

    def test_security_keyword_in_path(self) -> None:
        rec = _rec(file_path="src/auth/middleware.py")
        ct, applicable = classify_change_type([rec])
        assert ct == ChangeType.SECURITY_SENSITIVE_CHANGE

    def test_security_keyword_in_symbol(self) -> None:
        rec = _rec(symbol_path="app.crypto.sign")
        ct, applicable = classify_change_type([rec])
        assert ct == ChangeType.SECURITY_SENSITIVE_CHANGE

    def test_security_from_node_ids(self) -> None:
        rec = _rec(graph_node_id="node:123")
        ct, applicable = classify_change_type([rec], security_node_ids={"node:123"})
        assert ct == ChangeType.SECURITY_SENSITIVE_CHANGE

    def test_mixed_when_multiple_types(self) -> None:
        r1 = _rec(is_public_api=True)
        r2 = _rec(is_generated=True)
        ct, applicable = classify_change_type([r1, r2])
        assert ct == ChangeType.MIXED
        assert ChangeType.PUBLIC_API_CHANGE in applicable
        assert ChangeType.GENERATED_FILE_CHANGE in applicable

    def test_applicable_list_sorted(self) -> None:
        r1 = _rec(is_public_api=True)
        r2 = _rec(is_generated=True)
        _, applicable = classify_change_type([r1, r2])
        assert applicable == sorted(applicable)

    def test_single_type_applicable_list(self) -> None:
        rec = _rec(is_public_api=True)
        ct, applicable = classify_change_type([rec])
        assert len(applicable) == 1
        assert applicable[0] == ChangeType.PUBLIC_API_CHANGE
