"""Tests for AmbiguousLinkRecord and ambiguous-link bucket helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.blast_radius.ambiguous_links import (
    make_candidate_link,
    make_unresolved_cross_repo_link,
)
from llm_sca_tooling.blast_radius.models import AmbiguousLinkRecord, MatchMethod


class TestAmbiguousLinkRecord:
    def test_round_trip(self) -> None:
        rec = AmbiguousLinkRecord(
            source_node_id="n:src",
            target_node_id="n:tgt",
            edge_type="calls",
            confidence=0.4,
            match_method=MatchMethod.CANDIDATE_EDGE,
            reason_ambiguous="low confidence",
            recommended_followup="re-run analyser",
        )
        data = rec.model_dump(mode="json")
        restored = AmbiguousLinkRecord.model_validate(data)
        assert restored.source_node_id == "n:src"
        assert restored.match_method == MatchMethod.CANDIDATE_EDGE

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            AmbiguousLinkRecord.model_validate(
                {
                    "source_node_id": "n:a",
                    "target_node_id": "n:b",
                    "edge_type": "calls",
                    "confidence": 0.4,
                    "match_method": "candidate_edge",
                    "unknown_field": True,
                }
            )

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            AmbiguousLinkRecord(
                source_node_id="n:a",
                target_node_id="n:b",
                edge_type="calls",
                confidence=1.5,
                match_method=MatchMethod.CANDIDATE_EDGE,
            )


class TestMatchMethod:
    def test_all_values_present(self) -> None:
        values = {m.value for m in MatchMethod}
        assert "url_pattern_match" in values
        assert "name_heuristic" in values
        assert "candidate_edge" in values
        assert "cross_repo_unresolved" in values


class TestHelpers:
    def test_make_unresolved_cross_repo_link(self) -> None:
        link = make_unresolved_cross_repo_link(
            source_node_id="n:src",
            target_node_id="n:tgt",
            edge_type="consumes",
            confidence=0.0,
        )
        assert link.match_method == MatchMethod.CROSS_REPO_UNRESOLVED
        assert link.source_node_id == "n:src"

    def test_make_candidate_link(self) -> None:
        link = make_candidate_link(
            source_node_id="n:a",
            target_node_id="n:b",
            edge_type="calls",
            confidence=0.3,
            analyser_threshold=0.75,
        )
        assert link.match_method == MatchMethod.CANDIDATE_EDGE
        assert "0.30" in link.reason_ambiguous
        assert "0.75" in link.reason_ambiguous

    def test_make_unresolved_with_reason(self) -> None:
        link = make_unresolved_cross_repo_link(
            source_node_id="n:src",
            target_node_id="n:tgt",
            edge_type="consumes",
            confidence=0.0,
            reason="Repo not registered",
        )
        assert "Repo not registered" in link.reason_ambiguous
