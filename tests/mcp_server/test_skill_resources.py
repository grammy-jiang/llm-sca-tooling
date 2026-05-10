from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.mcp_server import CodeIntelligenceServer, McpServerConfig


def test_skill_inventory_resource_exposes_product_and_harness_skills(
    mcp_server,
) -> None:
    payload = mcp_server.read_resource("code-intelligence://skills").payload

    skills = {
        (skill["source"], skill["name"]): skill
        for skill in payload["skills"]
        if isinstance(skill, dict)
    }
    assert payload["count"] >= 8
    assert ("product", "impl-check") in skills
    assert ("product", "sast-repair") in skills
    assert ("agent-harness", "test-first-repair") in skills
    assert skills[("product", "impl-check")]["path"] == ".skills/impl_check.SKILL.md"
    assert skills[("product", "impl-check")]["origin"] == "workspace"


def test_skill_template_resource_returns_preferred_product_template(
    mcp_server,
) -> None:
    payload = mcp_server.read_resource("code-intelligence://skills/impl-check").payload

    assert payload["name"] == "impl-check"
    assert payload["preferred"]["source"] == "product"
    assert "run_implementation_check" in payload["preferred"]["content"]


def test_skill_template_resource_accepts_underscore_alias(mcp_server) -> None:
    payload = mcp_server.read_resource(
        "code-intelligence://skills/risk_classify"
    ).payload

    assert payload["name"] == "risk-classify"
    assert payload["preferred"]["path"] == ".skills/risk_classify.SKILL.md"


def test_skill_resources_fall_back_to_packaged_templates(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    server = CodeIntelligenceServer(
        McpServerConfig(
            workspace_path=tmp_path / ".llm-sca",
            schema_dir=repo_root / "schemas",
        )
    ).start()
    try:
        payload = server.read_resource("code-intelligence://skills").payload
        detail = server.read_resource("code-intelligence://skills/impl-check").payload
    finally:
        server.shutdown()

    assert payload["count"] >= 8
    assert detail["preferred"]["origin"] == "package"
    assert detail["preferred"]["path"].startswith(
        "package:llm_sca_tooling.skill_templates.bundled:PRODUCT_SKILLS"
    )
    assert "run_implementation_check" in detail["preferred"]["content"]
