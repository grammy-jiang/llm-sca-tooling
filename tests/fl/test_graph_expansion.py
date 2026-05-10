from __future__ import annotations

from llm_sca_tooling.fl.graph_expansion import GraphNeighbourExpander
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
)


def test_graph_expansion_adds_test_file(fl_workspace, fl_repo) -> None:
    seed = CandidateFile(
        candidate_id="candidate:core",
        file_path="src/pkg/core.py",
        repo_id=fl_repo.repo_id,
        node_id="node:file:core",
        signals=[
            CandidateSignal(
                signal_type=SignalType.KEYWORD,
                raw_score=1.0,
                evidence="stack trace",
            )
        ],
        combined_score=1.0,
        confidence=ConfidenceLevel.ANALYSER,
        snapshot_id="snapshot:test",
    )

    expanded = GraphNeighbourExpander(fl_workspace.graph).expand([seed])

    assert any(candidate.file_path == "tests/test_core.py" for candidate in expanded)
    test_candidate = next(
        candidate
        for candidate in expanded
        if candidate.file_path == "tests/test_core.py"
    )
    assert test_candidate.signals[0].raw_score == 0.6
