"""Real ts-morph TypeScript backend — parser-grade facts + fallback delegation.

These assert the facts a regex parser cannot produce: resolved methods,
cross-file call edges (caller in one file, callee defined in another), and a
real ts-morph version. When Node/ts-morph is unavailable the backend delegates
to the regex fallback instead of failing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_sca_tooling.indexing.backends.base import BackendResult, IndexingContext
from llm_sca_tooling.indexing.backends.typescript.ts_morph_backend import (
    TsMorphBackend,
)
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    IndexStatus,
    RepoRef,
    SnapshotRef,
)

NOW = datetime.now(UTC).isoformat()

UTIL_TS = """\
export function helper(x: number): number {
  return x * 2;
}

export class Calc {
  compute(n: number): number {
    return helper(n);
  }
}
"""

MAIN_TS = """\
import { Calc, helper } from "./util";

export function run(): number {
  const c = new Calc();
  return c.compute(helper(21));
}
"""

requires_node = pytest.mark.skipif(
    not TsMorphBackend().is_available(),
    reason="node/ts-morph runner not available",
)


def _context(repo_root: Path) -> IndexingContext:
    repo = RepoRef(repo_id="repo:tsm", name=repo_root.name)
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    return IndexingContext(
        repo_root=repo_root,
        repo_ref=repo,
        snapshot_ref=snapshot,
        config=IndexingConfig(),
        run_id="run:tsm",
    )


def _labels(result: BackendResult, node_type: GraphNodeType) -> set[str]:
    return {n.label for n in result.nodes if n.node_type == node_type}


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ts_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "util.ts").write_text(UTIL_TS)
    (repo / "src" / "main.ts").write_text(MAIN_TS)
    return repo


@requires_node
async def test_emits_parser_grade_symbols_and_methods(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    files = sorted(repo.rglob("*.ts"))
    result = await TsMorphBackend().index_files(_context(repo), files)

    funcs = _labels(result, GraphNodeType.function)
    # regex backend never produced methods; ts-morph does (compute).
    assert {"helper", "run", "compute"} <= funcs
    assert "Calc" in _labels(result, GraphNodeType.class_)

    # parser-grade provenance: DerivationType.parser at full confidence.
    symbol_nodes = [n for n in result.nodes if n.label in {"helper", "compute"}]
    assert symbol_nodes
    assert all(n.provenance.derivation == DerivationType.parser for n in symbol_nodes)
    assert all(n.provenance.confidence >= 0.9 for n in symbol_nodes)


@requires_node
async def test_resolves_cross_file_call_edges(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    files = sorted(repo.rglob("*.ts"))
    result = await TsMorphBackend().index_files(_context(repo), files)

    # Build node_id -> (file, label) so we can read call edges back.
    by_id = {n.node_id: n for n in result.nodes}
    call_pairs = {
        (
            by_id[e.source_id].file_path,
            by_id[e.source_id].label,
            by_id[e.target_id].file_path,
            by_id[e.target_id].label,
        )
        for e in result.edges
        if e.edge_type == GraphEdgeType.calls
        and e.source_id in by_id
        and e.target_id in by_id
    }
    # run() (main.ts) calls helper() defined in util.ts — cross-file resolution.
    assert any(
        src_file.endswith("main.ts")
        and src_label == "run"
        and tgt_file.endswith("util.ts")
        and tgt_label == "helper"
        for (src_file, src_label, tgt_file, tgt_label) in call_pairs
    )


@requires_node
async def test_reports_real_ts_morph_version(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    files = sorted(repo.rglob("*.ts"))
    await TsMorphBackend().index_files(_context(repo), files)
    backend = TsMorphBackend()
    await backend.index_files(_context(repo), files)
    assert backend.backend_version().startswith("ts-morph")


async def test_delegates_to_fallback_when_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    # Force unavailable -> must delegate to the regex backend, not crash.
    monkeypatch.setattr(TsMorphBackend, "is_available", lambda self: False)
    repo = _make_repo(tmp_path)
    files = sorted(repo.rglob("*.ts"))
    result = await TsMorphBackend().index_files(_context(repo), files)
    # Regex fallback still produces module + symbol facts.
    assert result.backend_id == "typescript.heuristic"
    assert "helper" in _labels(result, GraphNodeType.function)


async def test_runner_failure_falls_back(tmp_path: Path, monkeypatch) -> None:
    async def boom(self, repo_root, files):
        raise OSError("runner exploded")

    monkeypatch.setattr(TsMorphBackend, "is_available", lambda self: True)
    monkeypatch.setattr(TsMorphBackend, "_run_runner", boom)
    repo = _make_repo(tmp_path)
    files = sorted(repo.rglob("*.ts"))
    result = await TsMorphBackend().index_files(_context(repo), files)
    # Falls back to regex facts and records a diagnostic.
    assert result.backend_id == "typescript.heuristic"
    assert any(d.code == "ts_morph_runner_failed" for d in result.diagnostics)
