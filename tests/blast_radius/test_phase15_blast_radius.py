from __future__ import annotations

from pydantic import ValidationError

from llm_sca_tooling.blast_radius.abi_impact import compute_abi_impact
from llm_sca_tooling.blast_radius.ambiguous_links import make_cross_repo_unresolved
from llm_sca_tooling.blast_radius.change_type import classify_change_type
from llm_sca_tooling.blast_radius.cross_repo import traverse_cross_repo
from llm_sca_tooling.blast_radius.generated_stub import detect_generated_stub_notes
from llm_sca_tooling.blast_radius.graph_traversal import build_nx_graph, traverse
from llm_sca_tooling.blast_radius.impact_groups import group_impacts
from llm_sca_tooling.blast_radius.models import (
    AmbiguousLinkRecord,
    BlastRadiusReport,
    ChangeType,
    ImpactGroup,
)
from llm_sca_tooling.blast_radius.sarif_reachability import compute_sarif_reachability
from llm_sca_tooling.blast_radius.service import BlastRadiusService
from llm_sca_tooling.blast_radius.traversal_policy import policy_for
from llm_sca_tooling.mcp_server.prompts import PromptRegistry, register_default_prompts
from llm_sca_tooling.mcp_server.sampling import SamplingCapability

# Fixture graph: authenticate → validate_token → session_create (all confirmed)
NODES = [
    {"node_id": "symbol:auth", "node_type": "symbol"},
    {"node_id": "symbol:validate", "node_type": "symbol"},
    {"node_id": "symbol:session", "node_type": "symbol"},
    {"node_id": "test:test_auth", "node_type": "test"},
    {"node_id": "interface:api_auth", "node_type": "interface"},
    {"node_id": "sarif:alert1", "node_type": "sarif_alert", "rule_id": "CWE-89"},
    {"node_id": "doc:spec_auth", "node_type": "design_clause"},
]
EDGES = [
    {
        "source": "symbol:auth",
        "target": "symbol:validate",
        "edge_type": "calls",
        "confidence": 0.9,
    },
    {
        "source": "symbol:validate",
        "target": "symbol:session",
        "edge_type": "calls",
        "confidence": 0.95,
    },
    {
        "source": "symbol:auth",
        "target": "test:test_auth",
        "edge_type": "tests",
        "confidence": 0.9,
    },
    {
        "source": "symbol:auth",
        "target": "interface:api_auth",
        "edge_type": "exposes",
        "confidence": 0.85,
    },
    # Low-confidence edge → ambiguous
    {
        "source": "symbol:auth",
        "target": "sarif:alert1",
        "edge_type": "warns_by",
        "confidence": 0.4,
    },
    # Linked doc
    {
        "source": "symbol:auth",
        "target": "doc:spec_auth",
        "edge_type": "satisfies",
        "confidence": 0.8,
    },
]


def test_models_round_trip() -> None:
    svc = BlastRadiusService()
    report = svc.compute(
        diff_id="d1",
        changed_symbol_ids=["symbol:auth"],
        graph_nodes=NODES,
        graph_edges=EDGES,
    )
    assert BlastRadiusReport.model_validate_json(report.model_dump_json()) == report
    import pytest as _pytest

    with _pytest.raises(ValidationError):
        BlastRadiusReport.model_validate({"report_id": "x"})

    # ChangeType and ImpactGroup enums exhaustive
    assert ChangeType.mixed.value == "MIXED"
    assert ImpactGroup.repositories.value == "REPOSITORIES"
    all_groups = set(ImpactGroup)
    assert len(all_groups) == 8


def test_change_type_classification() -> None:
    # Internal implementation: no public API, no IDL, no security
    ct, apps = classify_change_type(["symbol:_internal"])
    assert ct == ChangeType.internal_implementation

    # Public API
    ct2, _ = classify_change_type(["symbol:authenticate"], is_public_api=True)
    assert ct2 == ChangeType.public_api_change

    # IDL/proto — use internal symbol so only IDL is detected
    ct3, _ = classify_change_type(
        ["symbol:_proto_msg"], changed_file_paths=["api/service.proto"]
    )
    assert ct3 == ChangeType.idl_schema_contract_change

    # Security — via explicit flag only
    ct4, _ = classify_change_type(["symbol:validate_token"], has_security_context=True)
    assert ct4 == ChangeType.security_sensitive_change

    # Generated file — use internal symbol
    ct5, _ = classify_change_type(
        ["symbol:_stub"], changed_file_paths=["api/service_pb2.py"]
    )
    assert ct5 == ChangeType.generated_file_change

    # Mixed (public API + security)
    ct6, apps6 = classify_change_type(
        ["symbol:auth"], is_public_api=True, has_security_context=True
    )
    assert ct6 == ChangeType.mixed
    assert len(apps6) >= 2


def test_traversal_policy_defaults() -> None:
    internal = policy_for(ChangeType.internal_implementation)
    assert internal.max_hops == 3
    assert internal.stop_at_interface_boundary is True
    assert internal.include_cross_language is False
    assert internal.include_cross_repo is False
    assert internal.include_sarif_reachability is False

    public_api = policy_for(ChangeType.public_api_change)
    assert public_api.max_hops == 5
    assert public_api.include_cross_language is True
    assert public_api.include_cross_repo is True

    security = policy_for(ChangeType.security_sensitive_change)
    assert security.include_sarif_reachability is True

    idl = policy_for(ChangeType.idl_schema_contract_change)
    assert idl.max_hops == 6
    assert idl.include_sarif_reachability is True
    assert idl.include_doc_spec_links is True

    gen = policy_for(ChangeType.generated_file_change)
    assert gen.max_hops == 2
    assert gen.stop_at_interface_boundary is True


def test_graph_traversal_confirmed_vs_ambiguous() -> None:
    g = build_nx_graph(NODES, EDGES)
    policy = policy_for(ChangeType.public_api_change)
    confirmed, ambiguous = traverse(g, ["symbol:auth"], policy)

    confirmed_ids = {r.node_id for r in confirmed}
    ambiguous_ids = {a.target_node_id for a in ambiguous}

    # Confirmed high-confidence edges
    assert "symbol:validate" in confirmed_ids
    assert "test:test_auth" in confirmed_ids
    assert "interface:api_auth" in confirmed_ids

    # Low-confidence edge → ambiguous bucket
    assert "sarif:alert1" in ambiguous_ids
    # Confirmed nodes NOT in ambiguous
    assert "symbol:validate" not in ambiguous_ids


def test_impact_groups_population() -> None:
    g = build_nx_graph(NODES, EDGES)
    policy = policy_for(ChangeType.public_api_change)
    confirmed, _ = traverse(g, ["symbol:auth"], policy)
    groups = group_impacts(confirmed)

    # Direct callers (hop=1) and downstream (hop>1)
    direct = groups[ImpactGroup.direct_callers]
    downstream = groups[ImpactGroup.downstream_behaviours]
    tests = groups[ImpactGroup.tests]
    interfaces = groups[ImpactGroup.interfaces]

    assert any(r.node_id == "symbol:validate" for r in direct + downstream)
    assert any(r.node_id == "test:test_auth" for r in tests)
    assert any(r.node_id == "interface:api_auth" for r in interfaces)


def test_generated_stub_notes() -> None:
    notes = detect_generated_stub_notes("d1", ["api/service_pb2.py", "src/app.py"])
    assert len(notes) == 1
    assert notes[0].manual_edit_policy_flag is True
    assert notes[0].generated_file_path == "api/service_pb2.py"

    # With allowlist
    allowed = detect_generated_stub_notes(
        "d1", ["api/service_pb2.py"], manual_edit_allowed=True
    )
    assert allowed[0].manual_edit_policy_flag is False


def test_abi_impact_fallback() -> None:
    notes = compute_abi_impact(["symbol:auth"], cpp_backend_available=False)
    assert notes[0].abi_change_type == "unknown"
    assert "libclang" in notes[0].diagnostics[0]

    with_backend = compute_abi_impact(["symbol:auth"], cpp_backend_available=True)
    assert with_backend[0].abi_change_type == "signature_changed"
    assert with_backend[0].confidence == "analyser"


def test_cross_repo_traversal() -> None:
    records, is_partial = traverse_cross_repo(["symbol:auth"], overlay_available=False)
    assert is_partial is True
    assert records[0].is_partial is True

    records2, is_partial2 = traverse_cross_repo(
        ["symbol:auth"],
        registered_repos=["repo:downstream"],
        overlay_available=True,
    )
    assert is_partial2 is False
    assert records2[0].repo_id == "repo:downstream"


def test_sarif_reachability() -> None:
    alert_nodes = [
        {"node_id": "sarif:sql", "rule_id": "CWE-89", "severity": "error"},
        {"node_id": "sarif:null", "rule_id": "NULL_DEREF", "severity": "warning"},
    ]
    records = compute_sarif_reachability(["symbol:auth"], alert_nodes)
    assert len(records) == 2
    groups = {r.node_id: r for r in records}
    assert groups["sarif:sql"].breaking_change_flag is True
    assert groups["sarif:null"].breaking_change_flag is False


def test_ambiguous_link_separation() -> None:
    link = make_cross_repo_unresolved("symbol:auth", "unregistered-repo")
    assert link.match_method == "cross_repo_unresolved"
    assert link.confidence == 0.0
    assert AmbiguousLinkRecord.model_validate_json(link.model_dump_json()) == link


def test_blast_radius_service_full_report() -> None:
    svc = BlastRadiusService()

    # Internal change: no cross-repo, no SARIF reachability
    internal = svc.compute(
        diff_id="d-internal",
        changed_symbol_ids=["symbol:_helper"],
        graph_nodes=NODES,
        graph_edges=EDGES,
    )
    assert internal.change_type == ChangeType.internal_implementation
    assert internal.is_partial is True  # ABI notes without C++ backend

    # Public API change: cross-language, cross-repo
    public_api = svc.compute(
        diff_id="d-api",
        changed_symbol_ids=["symbol:auth"],
        graph_nodes=NODES,
        graph_edges=EDGES,
        is_public_api=True,
    )
    assert public_api.change_type == ChangeType.public_api_change
    assert public_api.confirmed_impact_count > 0
    assert public_api.ambiguous_impact_count >= 0

    # Ambiguous links are always separate from impact_groups
    all_confirmed_ids = {
        r["node_id"] for group in public_api.impact_groups.values() for r in group
    }
    ambiguous_target_ids = {a.target_node_id for a in public_api.ambiguous_links}
    assert all_confirmed_ids.isdisjoint(ambiguous_target_ids)

    # Security change: SARIF reachability populated
    security = svc.compute(
        diff_id="d-security",
        changed_symbol_ids=["symbol:auth"],
        graph_nodes=NODES,
        graph_edges=EDGES,
        has_security_context=True,
        sarif_alert_nodes=[
            {"node_id": "sarif:sql", "rule_id": "CWE-89", "severity": "error"}
        ],
    )
    assert security.change_type == ChangeType.security_sensitive_change
    sarif_group = security.impact_groups.get("SARIF_REACHABILITY", [])
    assert sarif_group  # SARIF reachability populated

    # Generated file change: manual_edit_policy_flag
    gen = svc.compute(
        diff_id="d-gen",
        changed_symbol_ids=["symbol:stub"],
        changed_file_paths=["api/service_pb2.py"],
    )
    assert gen.change_type == ChangeType.generated_file_change
    assert gen.generated_stub_notes
    assert gen.generated_stub_notes[0].manual_edit_policy_flag is True

    # compute_from_changed_symbols convenience method
    simple = svc.compute_from_changed_symbols(["symbol:auth", "symbol:validate"])
    assert simple.confirmed_impact_count >= 0


def test_phase13_stub_replacement() -> None:
    from llm_sca_tooling.workflows.bug_resolve.blast_radius_stub import (
        compute_blast_radius,
    )
    from llm_sca_tooling.workflows.bug_resolve.models import CandidatePatch

    patch = CandidatePatch(
        run_id="r1",
        candidate_index=0,
        diff_text="--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n",
        changed_files=["src/app.py"],
        changed_symbol_ids=["symbol:auth"],
        generation_method="null_repair",
        generator_model="phase13-null",
    )
    result = compute_blast_radius(patch)
    # Phase 15 service backs the stub now
    assert result.run_id == "r1"
    assert result.is_partial is True  # ABI without C++ backend


def test_blast_radius_prompt_upgraded() -> None:
    registry = PromptRegistry(SamplingCapability(status="unsupported"))
    register_default_prompts(registry)
    prompt = registry.get("blast-radius")
    instr = prompt["instructions"]
    assert "DIRECT_CALLERS" in instr
    assert "REPOSITORIES" in instr
    assert "ambiguous" in instr.lower()
    assert "is_partial" in instr
