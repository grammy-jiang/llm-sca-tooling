from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import TextIO

from typer.testing import CliRunner

from llm_sca_tooling.cli.main import app
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Severity,
)
from llm_sca_tooling.schemas.incidents import Incident, IncidentStatus, TimelineEntry
from llm_sca_tooling.schemas.provenance import Provenance, RepoRef, SnapshotRef
from llm_sca_tooling.storage import initialize_workspace
from tests.storage.conftest import run_event, run_record

TS = "2026-05-09T00:00:00Z"


def test_cli_version_option() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "evidence-sca" in result.output


def test_cli_config_show() -> None:
    result = CliRunner().invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "Configuration" in result.output


def test_cli_run_create(tmp_path) -> None:
    result = CliRunner().invoke(
        app, ["run", "create", "demo", "--run-dir", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert result.output.startswith("run:")


def test_cli_replay_and_diagnose(tmp_path: Path) -> None:
    workspace_path = tmp_path / ".llm-sca"
    workspace = initialize_workspace(workspace_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    registered = workspace.repositories.register_repo(repo_root)
    repo_ref = RepoRef(
        repo_id=registered.repo_id,
        name=registered.name,
        default_branch=registered.default_branch,
    )
    run = run_record(repo_ref)
    event = run_event(1)
    workspace.operations.create_run(run)
    workspace.operations.append_run_event(run.run_id, event)
    prov = _provenance(repo_ref)
    workspace.operations.record_incident(
        Incident(
            incident_id="incident:1",
            severity=Severity.HIGH,
            status=IncidentStatus.OPEN,
            title="Loop",
            impact="lost time",
            timeline=[TimelineEntry(ts=TS, description="opened")],
            source_run_ids=[run.run_id],
            source_event_ids=[event.event_id],
            provenance=prov,
        ),
        primary_repo_id=repo_ref.repo_id,
    )
    workspace.close()
    runner = CliRunner()
    replay = runner.invoke(
        app,
        [
            "replay",
            "run:demo",
            "--workspace",
            str(workspace_path),
            "--filter-stage",
            "policy",
        ],
    )
    assert replay.exit_code == 0
    assert "Replay run:demo" in replay.output
    diagnose = runner.invoke(
        app,
        ["diagnose", "incident:1", "--workspace", str(workspace_path)],
    )
    assert diagnose.exit_code == 0
    assert "Incident incident:1" in diagnose.output


def test_cli_check_drift_json_report(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("S3 no plaintext secrets\n", encoding="utf-8")
    (tmp_path / ".agent").mkdir()
    (tmp_path / ".agent" / "plan.md").write_text("plan\n", encoding="utf-8")
    (tmp_path / ".agent" / "harness-stage.json").write_text(
        '{"stage":"S3"}\n', encoding="utf-8"
    )
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "verify.yml").write_text(
        "name: verify\n", encoding="utf-8"
    )
    report = tmp_path / "drift.json"
    result = CliRunner().invoke(
        app,
        [
            "check-drift",
            str(tmp_path),
            "--stage",
            "S3",
            "--report-out",
            str(report),
            "--fail-on",
            "relaxed",
        ],
    )
    assert result.exit_code == 0
    assert report.exists()


def test_cli_mcp_http_transport_validation() -> None:
    result = CliRunner().invoke(
        app,
        ["mcp", "validate", "--transport", "http", "--port", "9090"],
    )
    assert result.exit_code == 0
    assert "http://127.0.0.1:9090" in result.output


def test_mcp_stdio_serve_protocol_smoke(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "llm_sca_tooling.mcp_server.dev_server",
            "--workspace",
            str(tmp_path / "workspace"),
        ],
        cwd=Path.cwd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    try:
        _write_jsonrpc(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"},
                },
            },
        )
        initialized = _read_jsonrpc(process.stdout)
        assert initialized["id"] == 1
        assert initialized["result"]["serverInfo"]["name"] == "code-intelligence"

        _write_jsonrpc(
            process.stdin,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        _write_jsonrpc(
            process.stdin,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        tools = _read_jsonrpc(process.stdout)
        assert tools["id"] == 2
        assert any(
            tool["name"] == "run_readiness_audit" for tool in tools["result"]["tools"]
        )

        _write_jsonrpc(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": "code-intelligence://skills"},
            },
        )
        skills = _read_jsonrpc(process.stdout)
        assert skills["id"] == 3
        assert "impl-check" in skills["result"]["contents"][0]["text"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _write_jsonrpc(stream: TextIO, payload: dict[str, object]) -> None:
    stream.write(json.dumps(payload) + "\n")
    stream.flush()


def _read_jsonrpc(stream: TextIO, timeout: float = 10.0) -> dict[str, object]:
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: lines.put(stream.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=timeout)
    except queue.Empty as exc:
        raise AssertionError("timed out waiting for MCP stdio response") from exc
    assert line
    parsed = json.loads(line)
    assert isinstance(parsed, dict)
    return parsed


def _provenance(repo_ref: RepoRef) -> Provenance:
    snapshot_ref = SnapshotRef(
        repo_id=repo_ref.repo_id,
        git_sha="0" * 40,
        branch="main",
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )
    return Provenance(
        source_tool="test",
        source_version="0.1",
        source_run_id="run:demo",
        source_event_id="event:run:demo:1",
        repo=repo_ref,
        snapshot=snapshot_ref,
        derivation=DerivationType.PARSER,
        confidence=1.0,
        evidence_strength=EvidenceStrength.HARD_STATIC,
        created_ts=TS,
        attributes={},
    )
