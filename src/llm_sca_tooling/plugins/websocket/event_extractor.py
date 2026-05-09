"""WebSocket event matching helpers."""

from __future__ import annotations

from llm_sca_tooling.plugins.capability import ConfidenceLevel
from llm_sca_tooling.plugins.websocket.namespace_resolver import namespace_matches


def match_events(server: dict, client: dict) -> ConfidenceLevel | None:
    if server["event"] == client["event"] and namespace_matches(server.get("namespace"), client.get("namespace")):
        return ConfidenceLevel.PARSER if server.get("confidence") == ConfidenceLevel.PARSER and client.get("confidence") != ConfidenceLevel.HEURISTIC else ConfidenceLevel.ANALYSER
    if server["event"] == client["event"]:
        return ConfidenceLevel.HEURISTIC
    return None
