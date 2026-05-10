"""Tests for interface_compat."""

from __future__ import annotations

from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.interface_compat import check_interface_compatibility


def _diff(files: list[str]):
    parts = []
    for f in files:
        parts.append(
            f"diff --git a/{f} b/{f}\n--- a/{f}\n+++ b/{f}\n@@ -1 +1 @@\n-a\n+b\n"
        )
    return parse_unified_diff("".join(parts))


def test_breaking_change_classified() -> None:
    diff = _diff(["api/routes/x.py"])
    result = check_interface_compatibility(
        diff,
        interface_records=[
            {"operation": "/users", "change": "removed"},
            {"operation": "/items", "change": "required_param_added"},
        ],
        consumer_links={"/users": ["svc-a"]},
    )
    assert len(result.breaking_changes) == 2
    assert "svc-a" in result.affected_consumers


def test_optional_param_added_is_compatible() -> None:
    diff = _diff(["api/routes/x.py"])
    result = check_interface_compatibility(
        diff, interface_records=[{"operation": "/x", "change": "optional_param_added"}]
    )
    assert not result.breaking_changes
    assert not result.candidate_changes


def test_return_type_change_breaking_for_http() -> None:
    diff = _diff(["api/routes/x.py"])
    result = check_interface_compatibility(
        diff,
        interface_records=[
            {
                "operation": "/x",
                "change": "return_type_changed",
                "interface_type": "http",
            }
        ],
    )
    assert result.breaking_changes


def test_return_type_change_candidate_for_python() -> None:
    diff = _diff(["src/x.py"])
    result = check_interface_compatibility(
        diff,
        interface_records=[{"operation": "fn", "change": "return_type_changed"}],
    )
    assert result.candidate_changes


def test_no_records_emits_diagnostic() -> None:
    diff = _diff(["src/x.py"])
    result = check_interface_compatibility(diff)
    assert any(d["code"] == "no_interface_records" for d in result.diagnostics)


def test_protobuf_inferred() -> None:
    diff = _diff(["proto/items.proto"])
    result = check_interface_compatibility(diff)
    assert result.interface_type == "protobuf"


def test_generated_source_recorded() -> None:
    diff = _diff(["api/routes/x.py"])
    result = check_interface_compatibility(
        diff,
        interface_records=[
            {"operation": "/x", "change": "renamed", "generated_source": "openapi.yaml"}
        ],
    )
    assert result.generated_file_impact[0]["source_contract"] == "openapi.yaml"


def test_candidate_links_added() -> None:
    diff = _diff(["api/routes/x.py"])
    result = check_interface_compatibility(
        diff,
        interface_records=[{"operation": "/x", "change": "renamed"}],
        candidate_links={"/x": ["svc-c"]},
    )
    assert any(c.get("consumer") == "svc-c" for c in result.candidate_changes)


def test_skip_invalid_records() -> None:
    diff = _diff(["api/routes/x.py"])
    result = check_interface_compatibility(
        diff, interface_records=[{"operation": "", "change": ""}]
    )
    assert result.changed_operations == []
