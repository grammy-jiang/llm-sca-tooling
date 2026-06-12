"""Embedding adapter and semantic retrieval (Phase 9 activation, gap A1)."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_sca_tooling.fl.embedding_adapters import (
    FastembedEmbeddingAdapter,
    NullEmbeddingAdapter,
    get_default_embedding_adapter,
)
from llm_sca_tooling.fl.embedding_retrieval import embedding_retrieve
from llm_sca_tooling.fl.issue import normalize_issue_text
from llm_sca_tooling.fl.localisation import get_relevant_files
from llm_sca_tooling.schemas.graph import GraphNode, GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
)
from llm_sca_tooling.storage import WorkspaceStore

NOW = datetime.now(UTC).isoformat()

_VOCAB = [
    "user",
    "service",
    "validate",
    "authenticate",
    "none",
    "payment",
    "invoice",
    "render",
]


def _bag_encoder(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words encoder over a fixed vocabulary."""
    vectors = []
    for text in texts:
        lowered = text.lower()
        vector = [float(lowered.count(term)) for term in _VOCAB]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        vectors.append([v / norm for v in vector])
    return vectors


def _fake_adapter() -> FastembedEmbeddingAdapter:
    return FastembedEmbeddingAdapter(model_id="test-bag", encoder=_bag_encoder)


@pytest.fixture()
async def workspace(tmp_path: Path) -> WorkspaceStore:
    return await WorkspaceStore.initialize(tmp_path / "workspace", in_memory=True)


@pytest.fixture()
async def seeded_workspace(workspace: WorkspaceStore, tmp_path: Path) -> WorkspaceStore:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "user_service.py").write_text("def validate(user): ...\n")
    (root / "src" / "invoice_renderer.py").write_text("def render(invoice): ...\n")
    repo = await workspace.registry.register_repo(root, name="fl")
    await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="abc123", branch="main", index_status="fresh"
    )
    repo_ref = RepoRef(repo_id=repo.repo_id, name="fl", default_branch="main")
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc123",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    provenance = Provenance(
        source_tool="test",
        repo=repo_ref,
        snapshot=snapshot,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )
    nodes = [
        GraphNode(
            node_id="node:file:user_service",
            node_type=GraphNodeType.file,
            label="user service validate authenticate",
            repo=repo_ref,
            snapshot=snapshot,
            provenance=provenance,
            created_ts=NOW,
            file_path="src/user_service.py",
        ),
        GraphNode(
            node_id="node:file:invoice_renderer",
            node_type=GraphNodeType.file,
            label="invoice render payment",
            repo=repo_ref,
            snapshot=snapshot,
            provenance=provenance,
            created_ts=NOW,
            file_path="src/invoice_renderer.py",
        ),
    ]
    await workspace.graph.add_nodes(nodes)
    return workspace


def test_factory_falls_back_to_null_without_fastembed() -> None:
    adapter = get_default_embedding_adapter()
    # In environments without the optional dependency the factory must return
    # the null adapter; with it installed, the fastembed adapter.
    assert isinstance(adapter, FastembedEmbeddingAdapter | NullEmbeddingAdapter)
    if isinstance(adapter, NullEmbeddingAdapter):
        assert not adapter.is_available()
    else:
        assert adapter.is_available()


def test_unavailable_fastembed_adapter_reports_unavailable() -> None:
    adapter = FastembedEmbeddingAdapter(model_id="missing", encoder=None)
    if adapter.is_available():
        pytest.skip("fastembed installed; unavailability path not reachable")
    assert not adapter.is_available()


def test_fake_encoder_adapter_satisfies_contract() -> None:
    adapter = _fake_adapter()
    assert adapter.is_available()
    vectors = adapter.embed_batch(["user service validate", "invoice render"])
    assert len(vectors) == 2
    assert vectors[0].model_id == "test-bag"
    assert adapter.dimensions == len(_VOCAB)
    query = adapter.embed_text("user validate")
    top = adapter.top_k_similar(query, vectors, k=1)
    assert top[0][0] == 0  # the user-service text wins
    assert 0.0 < top[0][1] <= 1.0


async def test_embedding_retrieve_ranks_semantically(
    seeded_workspace: WorkspaceStore,
) -> None:
    issue = normalize_issue_text("user validate authenticate raises None error")
    candidates = await embedding_retrieve(seeded_workspace, issue, _fake_adapter())
    assert candidates
    assert candidates[0].file_path == "src/user_service.py"
    assert candidates[0].signals[0].signal_type.value == "EMBEDDING"


async def test_localisation_includes_embedding_signal(
    seeded_workspace: WorkspaceStore,
) -> None:
    result, _context = await get_relevant_files(
        seeded_workspace,
        issue_text="user validate authenticate error",
        embedding_adapter=_fake_adapter(),
    )
    assert "EMBEDDING" in result.signals_used
    assert result.signals_missing == []


async def test_localisation_records_missing_embedding_with_null_adapter(
    seeded_workspace: WorkspaceStore,
) -> None:
    result, _context = await get_relevant_files(
        seeded_workspace,
        issue_text="user validate authenticate error",
        embedding_adapter=NullEmbeddingAdapter(),
    )
    assert result.signals_missing == ["EMBEDDING"]
    assert "EMBEDDING" not in result.signals_used


class _CountingAdapter(FastembedEmbeddingAdapter):
    def __init__(self) -> None:
        super().__init__(model_id="test-bag", encoder=self._counted)
        self.encode_calls = 0

    def _counted(self, texts: list[str]) -> list[list[float]]:
        self.encode_calls += len(texts)
        return _bag_encoder(texts)


async def test_embedding_retrieve_uses_vector_cache(
    seeded_workspace: WorkspaceStore,
) -> None:
    adapter = _CountingAdapter()
    issue = normalize_issue_text("user validate authenticate raises None error")

    first = await embedding_retrieve(seeded_workspace, issue, adapter)
    calls_after_first = adapter.encode_calls
    assert first

    second = await embedding_retrieve(seeded_workspace, issue, adapter)
    assert [c.file_path for c in second] == [c.file_path for c in first]
    # Node vectors come from the cache on the second run; only the query
    # text is re-embedded.
    assert adapter.encode_calls == calls_after_first + 1
