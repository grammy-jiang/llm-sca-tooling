"""Phase 6 SARIF and static-analysis layer tests."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

import llm_sca_tooling.sarif.adapters.bandit as bandit_module
import llm_sca_tooling.sarif.adapters.codeql as codeql_module
import llm_sca_tooling.sarif.adapters.semgrep as semgrep_module
import llm_sca_tooling.sarif.service as service_module
from llm_sca_tooling.indexing.service import IndexingService
from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig
from llm_sca_tooling.sarif.adapters import (
    BanditAdapter,
    CodeQLAdapter,
    SemgrepAdapter,
    SonarQubeAdapter,
)
from llm_sca_tooling.sarif.adapters.base import (
    AnalyserAvailability,
    AnalyserRunResult,
    RulesetConfig,
)
from llm_sca_tooling.sarif.adapters.ruleset import resolve_ruleset
from llm_sca_tooling.sarif.binding import bind_sarif_run
from llm_sca_tooling.sarif.delta import compute_sarif_delta
from llm_sca_tooling.sarif.fingerprint import compute_alert_fingerprint
from llm_sca_tooling.sarif.models import SarifLog
from llm_sca_tooling.sarif.normalizer import (
    extract_cwe_ids,
    normalize_rule_family,
    normalize_sarif_log,
    normalize_severity,
    predicate_id,
)
from llm_sca_tooling.sarif.parser import (
    SarifParseError,
    SarifVersionError,
    parse_sarif_file,
    resolve_artifact_uri,
)
from llm_sca_tooling.sarif.resource import sarif_run_resource, sarif_run_summaries
from llm_sca_tooling.sarif.service import _run_adapter, run_static_analysis
from llm_sca_tooling.sarif.store import SarifRunStore
from llm_sca_tooling.schemas.graph import GraphEdgeType
from llm_sca_tooling.storage import WorkspaceStore

FIXTURES = Path(__file__).parent / "fixtures"
PYTHON_REPO = Path(__file__).parents[2] / "fixtures" / "repos" / "python_basic"


def test_sarif_parser_validates_version_malformed_and_locations(
    tmp_path: Path,
) -> None:
    parsed = parse_sarif_file(FIXTURES / "semgrep_python_basic.sarif.json")
    result = parsed.runs[0].results[0]
    assert parsed.version == "2.1.0"
    assert result.rule_id == "python.lang.security.audit.sqli"
    assert result.locations[0].physical_location is not None
    assert result.fingerprints["primaryLocationLineHash"] == "existing"

    bad_version = tmp_path / "bad-version.sarif.json"
    bad_version.write_text('{"version": "2.0.0", "runs": []}')
    with pytest.raises(SarifVersionError):
        parse_sarif_file(bad_version)

    with pytest.raises(SarifParseError):
        parse_sarif_file(FIXTURES / "malformed.sarif.json")


def test_sarif_parser_edge_cases(tmp_path: Path) -> None:
    missing_runs = tmp_path / "missing-runs.sarif.json"
    missing_runs.write_text('{"version": "2.1.0"}')
    with pytest.raises(SarifParseError, match="invalid SARIF shape"):
        parse_sarif_file(missing_runs)

    raw = tmp_path / "edge.sarif.json"
    raw.write_text("""
        {
          "version": "2.1.0",
          "$schema": "https://example.test/sarif-schema.json",
          "runs": [{
            "tool": {
              "driver": {
                "name": "custom",
                "semanticVersion": "1.2.3",
                "guid": "tool-guid",
                "rules": [{"id": "R1", "defaultConfiguration": {"level": "note"}}]
              },
              "extensions": [{"name": "ext", "version": "0.1"}]
            },
            "originalUriBaseIds": {"SRCROOT": {"uri": "file:///outside/root"}},
            "invocations": [{"executionSuccessful": false, "exitCode": 2}],
            "results": [{
              "ruleIndex": 0,
              "message": {},
              "locations": [{
                "physicalLocation": {
                  "artifactLocation": {"uri": "src/pkg/core.py", "uriBaseId": "SRCROOT"},
                  "region": {}
                }
              }],
              "relatedLocations": [{"message": {"text": "related"}}]
            }]
          }]
        }
        """)
    parsed = parse_sarif_file(raw, repo_root=tmp_path)
    run = parsed.runs[0]
    assert parsed.schema_uri == "https://example.test/sarif-schema.json"
    assert run.tool.driver.semantic_version == "1.2.3"
    assert run.tool.extensions[0].name == "ext"
    assert run.invocation_successful is False
    assert run.invocation_exit_code == 2
    assert run.results[0].rule_id == "R1"
    assert run.results[0].locations[0].physical_location is not None
    assert run.results[0].locations[0].physical_location.region is None
    assert run.results[0].related_locations[0].message == "related"
    assert (
        resolve_artifact_uri("https://example.test/file.py", None, {}, tmp_path) is None
    )
    assert resolve_artifact_uri("/outside/file.py", None, {}, tmp_path) is None


def test_normalizer_severity_cwe_family_and_predicates() -> None:
    assert normalize_severity("semgrep", "error").value == "high"
    assert (
        normalize_severity("semgrep", "warning", {"security-severity": "9.5"}).value
        == "critical"
    )
    assert (
        normalize_severity(
            "bandit",
            None,
            {"issue_severity": "HIGH", "issue_confidence": "HIGH"},
        ).value
        == "high"
    )
    assert (
        normalize_severity(
            "bandit",
            None,
            {"issue_severity": "LOW", "issue_confidence": "LOW"},
        ).value
        == "low"
    )
    assert normalize_severity("codeql", "warning").value == "medium"
    assert normalize_severity("unknown", "error").value == "high"
    assert extract_cwe_ids("CWE-89", "cwe: 79", ["798"]) == [
        "CWE-79",
        "CWE-89",
        "CWE-798",
    ]
    assert normalize_rule_family("x", ["CWE-89"], []) == "sql-injection"
    assert (
        normalize_rule_family("python.lang.security.audit.sqli", [], [])
        == "sql-injection"
    )
    assert normalize_rule_family("B105", [], []) == "hardcoded-secret"
    assert predicate_id("bandit", "B105", {}) == "BANDIT-B105"
    assert predicate_id("codeql", "x", {"github/alertNumber": 42}) == "GHAS-42"
    assert SonarQubeAdapter().normalize_level("BLOCKER").value == "critical"
    assert (
        normalize_severity("semgrep", "warning", {"security-severity": "invalid"}).value
        == "medium"
    )
    assert normalize_severity("sonarqube", "critical").value == "high"
    assert normalize_severity("sonarqube", "minor").value == "low"
    assert normalize_severity("sonarqube", "info").value == "informational"
    assert normalize_severity("unknown", "note").value == "low"
    assert normalize_severity("unknown", "unrecognised").value == "informational"
    assert normalize_rule_family("null_pointer", [], ["nullptr"]) == "null-deref"
    assert normalize_rule_family("unknown", [], []) == "other"


def test_normalized_run_and_fingerprints_are_stable(tmp_path: Path) -> None:
    log = parse_sarif_file(FIXTURES / "semgrep_python_basic.sarif.json")
    run = normalize_sarif_log(
        log,
        repo_id="repo:test",
        snapshot_id="snap:test",
        git_sha="abc",
        run_id="sarif-run:test",
        analyser_id="semgrep",
    )
    alert = run.alerts[0]
    assert run.rules[0].rule_family == "sql-injection"
    assert alert.raw_fingerprints["primaryLocationLineHash"] == "existing"
    assert alert.normalized_severity.value == "high"
    assert (
        compute_alert_fingerprint(
            analyser_id="semgrep",
            rule_id=alert.rule_id,
            file_path=alert.file_path,
            start_line=alert.start_line,
            message="Potential   SQL injection",
            snippet="def compute(x: int, y: int) -> int:",
        )
        == alert.fingerprint
    )
    assert (
        compute_alert_fingerprint(
            analyser_id="semgrep",
            rule_id="different",
            file_path=alert.file_path,
            start_line=alert.start_line,
            message=alert.message,
        )
        != alert.fingerprint
    )

    missing_rule_fixture = tmp_path / "missing-rule.sarif.json"
    missing_rule_fixture.write_text("""
        {
          "version": "2.1.0",
          "runs": [{
            "tool": {"driver": {"name": "external", "rules": []}},
            "results": [{
              "ruleId": "GEN001",
              "level": "warning",
              "message": {"text": "Generated rule"},
              "locations": []
            }]
          }]
        }
        """)
    missing_rule_log = parse_sarif_file(missing_rule_fixture)
    missing_rule_run = normalize_sarif_log(
        missing_rule_log,
        repo_id="repo:test",
        snapshot_id="snap:test",
        git_sha="abc",
        run_id="sarif-run:missing-rule",
    )
    assert missing_rule_run.rules[0].rule_id == "GEN001"
    assert missing_rule_run.alerts[0].related_locations == []


def test_normalizer_handles_empty_runs_suppressions_and_rule_strength(
    tmp_path: Path,
) -> None:
    suppressed_fixture = tmp_path / "suppressed.sarif.json"
    suppressed_fixture.write_text("""
        {
          "version": "2.1.0",
          "runs": [{
            "tool": {
              "driver": {
                "name": "semgrep",
                "rules": [{
                  "id": "critical-rule",
                  "defaultConfiguration": {"level": "error"},
                  "properties": {
                    "security-severity": "9.1",
                    "tags": "CWE-89"
                  }
                }]
              }
            },
            "results": [{
              "ruleId": "critical-rule",
              "level": "note",
              "message": {"text": "Suppressed alert"},
              "locations": [{
                "physicalLocation": {
                  "artifactLocation": {"uri": "src/pkg/core.py"},
                  "region": {"startLine": 1}
                }
              }],
              "suppressions": [{
                "kind": "external",
                "status": "accepted",
                "justification": "known test fixture"
              }]
            }]
          }]
        }
        """)
    log = parse_sarif_file(suppressed_fixture)
    run = normalize_sarif_log(
        log,
        repo_id="repo:test",
        snapshot_id="snap:test",
        git_sha="abc",
        run_id="sarif-run:suppressed",
        analyser_id="semgrep",
    )
    assert run.alerts[0].suppressed is True
    assert run.alerts[0].suppression_kind == "external"
    assert run.alerts[0].suppression_status == "accepted"
    assert run.alerts[0].suppression_justification == "known test fixture"
    assert run.alerts[0].normalized_severity.value == "critical"
    assert run.rules[0].tags == ["CWE-89"]

    empty = normalize_sarif_log(
        SarifLog(version="2.1.0", runs=[]),
        repo_id="repo:test",
        snapshot_id="snap:test",
        git_sha="abc",
        run_id="sarif-run:empty",
    )
    assert empty.analyser_name == "external"
    assert empty.alerts == []


async def test_sarif_store_queries_and_delta(tmp_path: Path) -> None:
    workspace = await WorkspaceStore.initialize(tmp_path, in_memory=True)
    store = SarifRunStore(workspace)
    before = normalize_sarif_log(
        parse_sarif_file(FIXTURES / "delta_before.sarif.json"),
        repo_id="repo:test",
        snapshot_id="snap:before",
        git_sha="abc",
        run_id="before",
        analyser_id="semgrep",
    )
    after = normalize_sarif_log(
        parse_sarif_file(FIXTURES / "delta_after.sarif.json"),
        repo_id="repo:test",
        snapshot_id="snap:after",
        git_sha="def",
        run_id="after",
        analyser_id="semgrep",
    )
    await store.store_run(before)
    await store.store_run(after)
    delta = compute_sarif_delta(before, after)
    await store.store_delta(delta)

    assert (await store.get_run("before")) == before
    assert len(await store.list_runs("repo:test", "semgrep")) == 2
    assert await store.get_alerts_for_file("repo:test", "src/pkg/core.py")
    assert await store.get_alerts(
        "after", severity_min=after.alerts[1].normalized_severity
    )
    assert (await store.get_latest_run("repo:test", "semgrep", "default")) is not None
    assert (await store.get_delta(delta.delta_id)) == delta
    assert delta.summary.appeared_count == 1
    assert delta.summary.disappeared_count == 0
    assert delta.summary.changed_count == 1
    assert delta.summary.new_critical_or_high_count == 1
    await store.delete_run("before")
    assert await store.get_run("before") is None


async def test_external_import_binds_alerts_and_emits_warned_by_edges(
    tmp_path: Path,
) -> None:
    workspace = await WorkspaceStore.initialize(tmp_path / "workspace", in_memory=True)
    repo = tmp_path / "repo"
    shutil.copytree(PYTHON_REPO, repo)
    build = await IndexingService(workspace).graph_build(repo)

    result = await run_static_analysis(
        workspace,
        repo=build.repo_id,
        analyser="semgrep",
        import_sarif_path=str(FIXTURES / "semgrep_python_basic.sarif.json"),
    )

    store = SarifRunStore(workspace)
    run = await store.get_run(str(result["run_id"]))
    assert run is not None
    assert run.produced_by_run_id in result["run_event_ids"]
    assert run.alerts[0].bound_file_node_id is not None
    assert run.alerts[0].bound_symbol_node_ids
    assert await store.get_alerts_for_symbol(run.alerts[0].bound_symbol_node_ids[0])
    assert result["new_critical_high_count"] == 1
    warned = await workspace.queries.fetch_edges_by_type(
        build.repo_id, GraphEdgeType.warned_by.value
    )
    assert warned
    payload = await sarif_run_resource(store, build.repo_id, run.run_id)
    assert payload["severity_summary"]["high"] == 1
    assert (await sarif_run_summaries(store, build.repo_id))[0]["run_id"] == run.run_id


async def test_external_import_computes_delta_between_runs(tmp_path: Path) -> None:
    workspace = await WorkspaceStore.initialize(tmp_path / "workspace", in_memory=True)
    repo = tmp_path / "repo"
    shutil.copytree(PYTHON_REPO, repo)
    build = await IndexingService(workspace).graph_build(repo)

    first = await run_static_analysis(
        workspace,
        repo=build.repo_id,
        analyser="semgrep",
        import_sarif_path=str(FIXTURES / "delta_before.sarif.json"),
    )
    second = await run_static_analysis(
        workspace,
        repo=build.repo_id,
        analyser="semgrep",
        import_sarif_path=str(FIXTURES / "delta_after.sarif.json"),
    )

    assert second["delta_from_run_id"] == first["run_id"]
    assert second["delta_id"] is not None


async def test_binding_reports_unresolved_and_mixed_snapshot(tmp_path: Path) -> None:
    workspace = await WorkspaceStore.initialize(tmp_path / "workspace", in_memory=True)
    repo = tmp_path / "repo"
    shutil.copytree(PYTHON_REPO, repo)
    build = await IndexingService(workspace).graph_build(repo)

    base_run = normalize_sarif_log(
        parse_sarif_file(FIXTURES / "semgrep_python_basic.sarif.json"),
        repo_id=build.repo_id,
        snapshot_id="snap:test",
        git_sha="different-sha",
        run_id="sarif-run:binding",
        analyser_id="semgrep",
    )
    suppressed = base_run.alerts[0].model_copy(update={"suppressed": True})
    mixed = base_run.model_copy(update={"alerts": [suppressed]})
    mixed_result = await bind_sarif_run(workspace, mixed)
    assert mixed_result.run.alerts[0].properties["mixed_snapshot_binding"] is True
    assert mixed_result.run.alerts[0].properties["suppressed"] is True

    missing_file = base_run.alerts[0].model_copy(update={"file_path": "missing.py"})
    no_location = base_run.alerts[0].model_copy(update={"file_path": None})
    diagnostics = (
        await bind_sarif_run(
            workspace,
            base_run.model_copy(update={"alerts": [missing_file, no_location]}),
        )
    ).diagnostics
    assert [item.code for item in diagnostics] == [
        "SARIF_FILE_NODE_NOT_FOUND",
        "SARIF_UNRESOLVABLE_LOCATION",
    ]


async def test_mcp_run_static_analysis_tool_and_resource(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(PYTHON_REPO, repo)
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize()
    try:
        build_task = await server.call_tool("graph_build", {"repo_path": str(repo)})
        task_id = build_task.payload["task"]["task_id"]
        status = None
        for _ in range(100):
            status = await server.call_tool("task_status", {"task_id": task_id})
            if status.payload["task"]["status"] == "completed":
                break
            await asyncio.sleep(0.01)
        assert status is not None
        assert status.payload["task"]["status"] == "completed"
        repo_id = status.payload["task"]["result"]["repo_id"]
        result = await server.call_tool(
            "run_static_analysis",
            {
                "repo": repo_id,
                "analyser": "external",
                "import_sarif_path": str(FIXTURES / "external_generic.sarif.json"),
            },
        )
        assert result.status == "completed"
        run_id = result.payload["run_id"]
        resource = await server.read_resource(
            f"code-intelligence://sarif/{repo_id}/{run_id}"
        )
        assert resource.payload["alert_count"] == 1
        listing = await server.read_resource(f"code-intelligence://sarif/{repo_id}")
        assert listing.payload["runs"][0]["run_id"] == run_id
        assert any(
            note["method"] == "notifications/resources/updated"
            for note in result.notifications
        )
    finally:
        await server.close()


async def test_adapter_availability_and_ruleset_offline(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert not (await SemgrepAdapter().check_availability()).available
    assert not (await BanditAdapter().check_availability()).available
    assert not (await CodeQLAdapter().check_availability()).available
    unavailable_run = await SemgrepAdapter().run(Path.cwd())
    assert unavailable_run.diagnostics == ["BACKEND_UNAVAILABLE: semgrep not found"]
    unavailable_bandit = await BanditAdapter().run(Path.cwd())
    assert unavailable_bandit.diagnostics == ["BACKEND_UNAVAILABLE: bandit not found"]
    with pytest.raises(ValueError, match="requires network"):
        resolve_ruleset(["p/security-audit"], offline=True)
    resolved = resolve_ruleset(["local-rule"], offline=False)
    assert resolved.ruleset_id.startswith("ruleset:")


async def test_codeql_availability_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("LLM_SCA_CODEQL_BACKEND_ENABLED", "1")
    monkeypatch.setattr(codeql_module.shutil, "which", lambda name: "/usr/bin/codeql")
    availability = await CodeQLAdapter().check_availability()
    assert availability.available is True
    assert availability.tool_path == "/usr/bin/codeql"


async def test_semgrep_availability_when_installed(monkeypatch) -> None:
    monkeypatch.setattr(semgrep_module.shutil, "which", lambda name: "/usr/bin/semgrep")

    async def fake_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        return _FakeProcess(stdout=b"1.2.3")

    monkeypatch.setattr(semgrep_module.asyncio, "create_subprocess_exec", fake_exec)
    availability = await SemgrepAdapter().check_availability()
    assert availability.available is True
    assert availability.tool_version == "1.2.3"


async def test_bandit_availability_when_installed(monkeypatch) -> None:
    monkeypatch.setattr(bandit_module.shutil, "which", lambda name: "/usr/bin/bandit")

    async def fake_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        return _FakeProcess(stdout=b"bandit 1.7.5")

    monkeypatch.setattr(bandit_module.asyncio, "create_subprocess_exec", fake_exec)
    availability = await BanditAdapter().check_availability()
    assert availability.available is True
    assert availability.tool_version == "bandit 1.7.5"


class _FakeProcess:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        output_path: Path | None = None,
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._output_path = output_path
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._output_path is not None:
            self._output_path.write_bytes(
                (FIXTURES / "semgrep_python_basic.sarif.json").read_bytes()
            )
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


async def test_semgrep_adapter_success_error_timeout_and_offline(
    monkeypatch, tmp_path: Path
) -> None:
    adapter = SemgrepAdapter()
    monkeypatch.setattr(
        adapter,
        "check_availability",
        lambda: asyncio.sleep(
            0,
            result=AnalyserAvailability("semgrep", True, "/bin/semgrep", "1.0"),
        ),
    )

    created: list[_FakeProcess] = []

    async def fake_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        output_path = Path(cmd[cmd.index("--output") + 1])
        proc = _FakeProcess(
            stdout=b"semgrep stdout",
            stderr=b"semgrep stderr",
            output_path=output_path,
        )
        created.append(proc)
        return proc

    monkeypatch.setattr(semgrep_module.asyncio, "create_subprocess_exec", fake_exec)
    result = await adapter.run(tmp_path)
    assert result.sarif_log is not None
    assert result.diagnostics == ["semgrep stdout", "semgrep stderr"]

    offline = await adapter.run(
        tmp_path, RulesetConfig(entries=["p/security-audit"], offline=True)
    )
    assert offline.sarif_log is None
    assert offline.diagnostics == ["NETWORK_REQUIRED: registry rules disabled"]

    async def failing_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        return _FakeProcess(returncode=2, stderr=b"bad config")

    monkeypatch.setattr(semgrep_module.asyncio, "create_subprocess_exec", failing_exec)
    failed = await adapter.run(tmp_path)
    assert failed.exit_code == 2
    assert failed.diagnostics == ["bad config"]

    async def timeout_wait_for(coro: object, timeout: float) -> object:
        if hasattr(coro, "close"):
            coro.close()
        raise TimeoutError

    proc = _FakeProcess()

    async def hanging_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        return proc

    monkeypatch.setattr(semgrep_module.asyncio, "create_subprocess_exec", hanging_exec)
    monkeypatch.setattr(semgrep_module.asyncio, "wait_for", timeout_wait_for)
    timed_out = await adapter.run(tmp_path)
    assert timed_out.diagnostics == ["ANALYSER_TIMEOUT: semgrep timed out"]
    assert proc.killed is True


async def test_bandit_adapter_success_error_timeout_and_version(
    monkeypatch, tmp_path: Path
) -> None:
    adapter = BanditAdapter()
    monkeypatch.setattr(
        adapter,
        "check_availability",
        lambda: asyncio.sleep(
            0,
            result=AnalyserAvailability("bandit", True, "/bin/bandit", "1.0"),
        ),
    )

    async def fake_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        if "--version" in cmd:
            return _FakeProcess(stdout=b"bandit 1.7.0\n")
        output_path = Path(cmd[cmd.index("-o") + 1])
        return _FakeProcess(output_path=output_path)

    monkeypatch.setattr(bandit_module.asyncio, "create_subprocess_exec", fake_exec)
    assert await bandit_module._version("/bin/bandit") == "bandit 1.7.0"
    result = await adapter.run(tmp_path)
    assert result.sarif_log is not None

    calls: list[tuple[object, ...]] = []

    async def json_fallback_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        calls.append(cmd)
        output_path = Path(cmd[cmd.index("-o") + 1])
        if "-f" in cmd and cmd[cmd.index("-f") + 1] == "json":
            output_path.write_bytes(b"""
                {
                  "results": [{
                    "filename": "./src/pkg/core.py",
                    "line_number": 12,
                    "col_offset": 4,
                    "test_id": "B105",
                    "test_name": "hardcoded_password_string",
                    "issue_text": "Possible hardcoded password",
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "code": "password = 'secret'"
                  }]
                }
                """)
            return _FakeProcess(returncode=1)
        return _FakeProcess(returncode=2, stderr=b"sarif unsupported")

    monkeypatch.setattr(
        bandit_module.asyncio, "create_subprocess_exec", json_fallback_exec
    )
    fallback = await adapter.run(
        tmp_path, RulesetConfig(entries=["B105", "!B101"], offline=True)
    )
    assert fallback.sarif_log is not None
    assert fallback.sarif_log.runs[0].results[0].rule_id == "B105"
    assert any("-t" in call and "B105" in call for call in calls)
    assert any("-s" in call and "B101" in call for call in calls)

    async def failing_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        return _FakeProcess(returncode=3, stderr=b"bandit failed")

    monkeypatch.setattr(bandit_module.asyncio, "create_subprocess_exec", failing_exec)
    failed = await adapter.run(tmp_path)
    assert failed.exit_code == 3
    assert failed.diagnostics == ["bandit failed"]

    async def timeout_wait_for(coro: object, timeout: float) -> object:
        if hasattr(coro, "close"):
            coro.close()
        raise TimeoutError

    proc = _FakeProcess()

    async def hanging_exec(*cmd: object, **kwargs: object) -> _FakeProcess:
        return proc

    monkeypatch.setattr(bandit_module.asyncio, "create_subprocess_exec", hanging_exec)
    monkeypatch.setattr(bandit_module.asyncio, "wait_for", timeout_wait_for)
    timed_out = await adapter.run(tmp_path)
    assert timed_out.diagnostics == ["ANALYSER_TIMEOUT: bandit timed out"]
    assert proc.killed is True


async def test_bandit_json_fallback_timeout_and_converter_edges(
    monkeypatch, tmp_path: Path
) -> None:
    proc = _FakeProcess()

    async def fake_run_bandit(*args: object, **kwargs: object) -> _FakeProcess:
        return proc

    async def timeout_wait_for(coro: object, timeout: float) -> object:
        if hasattr(coro, "close"):
            coro.close()
        raise TimeoutError

    monkeypatch.setattr(bandit_module, "_run_bandit", fake_run_bandit)
    monkeypatch.setattr(bandit_module.asyncio, "wait_for", timeout_wait_for)
    timeout = await bandit_module._run_json_fallback(
        "/bin/bandit",
        tmp_path,
        tmp_dir=tmp_path,
        config=RulesetConfig(),
        prior_diagnostics=["sarif unsupported"],
        prior_exit_code=2,
    )
    assert timeout.diagnostics == [
        "sarif unsupported",
        "ANALYSER_TIMEOUT: bandit JSON fallback timed out",
    ]
    assert proc.killed is True

    repo_file = tmp_path / "src" / "pkg" / "core.py"
    repo_file.parent.mkdir(parents=True)
    repo_file.write_text("x = 1")
    converted = bandit_module._bandit_json_to_sarif(
        f"""
        {{
          "results": [
            null,
            {{
              "filename": "{repo_file}",
              "line_number": 1,
              "test_id": "B101",
              "issue_text": "medium",
              "issue_severity": "MEDIUM"
            }},
            {{
              "filename": "/outside/secret.py",
              "line_number": 2,
              "test_id": "B102",
              "issue_text": "low",
              "issue_severity": "LOW"
            }}
          ]
        }}
        """.encode(),
        tmp_path,
    )
    assert [result.level for result in converted.runs[0].results] == [
        "warning",
        "note",
    ]
    assert (
        converted.runs[0]
        .results[0]
        .locations[0]
        .physical_location.artifact_location.resolved_path
        == "src/pkg/core.py"
    )
    assert (
        converted.runs[0]
        .results[1]
        .locations[0]
        .physical_location.artifact_location.resolved_path
        == "secret.py"
    )


async def test_service_requires_index_and_adapter_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    workspace = await WorkspaceStore.initialize(tmp_path / "workspace", in_memory=True)
    repo = await workspace.registry.register_repo(tmp_path)
    with pytest.raises(ValueError, match="indexed"):
        await run_static_analysis(workspace, repo=repo.repo_id, analyser="semgrep")

    class FakeSemgrep:
        async def run(self, repo_root: Path) -> AnalyserRunResult:
            return AnalyserRunResult(None, ["BACKEND_UNAVAILABLE: semgrep not found"])

    monkeypatch.setattr(service_module, "SemgrepAdapter", FakeSemgrep)
    run, diagnostics = await _run_adapter(
        "semgrep",
        tmp_path,
        "repo:test",
        "snap:test",
        "abc",
        "sarif-run:fallback",
        ["local-rule"],
    )
    assert diagnostics == ["BACKEND_UNAVAILABLE: semgrep not found"]
    assert run.alerts == []
    assert run.ruleset_id.startswith("ruleset:")
