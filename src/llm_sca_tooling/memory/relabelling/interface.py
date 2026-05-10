"""Hindsight relabelling interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_sca_tooling.memory.models import HindsightLabel, TrajectoryRecord


class HindsightRelabellerInterface(ABC):
    model_id: str
    version: str

    @abstractmethod
    def relabel(
        self, trajectory: TrajectoryRecord, candidate_goal: str
    ) -> HindsightLabel:
        raise NotImplementedError
