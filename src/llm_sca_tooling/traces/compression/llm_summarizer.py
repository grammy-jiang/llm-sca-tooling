"""LLM trace summarizer (Tier B3).

Spec rules enforced here:
- Raw traces are never inserted wholesale into LLM context — the LLM sees a
  capped digest of the deterministically filtered events.
- Only the natural-language fields (`executed_path_summary`,
  `uncertainty_notes`) are LLM-derived; the event lists are produced by the
  same deterministic path as the null summarizer.
- Fail-closed: unparseable LLM output keeps the null summarizer's summary and
  `summarizer_model: null` so downstream consumers never mistake a fallback
  for an LLM-graded summary.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from llm_sca_tooling.traces.compression.interface import TraceSummarizerInterface
from llm_sca_tooling.traces.compression.null_summarizer import NullTraceSummarizer
from llm_sca_tooling.traces.models import (
    CompressedTrace,
    RawTraceArtefact,
    ScopeFilter,
)

# Cap on event lines included in the LLM digest, independent of how many
# events survive deterministic filtering.
_DIGEST_EVENT_CAP = 30

_PROMPT_TEMPLATE = """\
You are summarizing a runtime trace for code-analysis evidence. Below is a
capped digest of the deterministically filtered events (the full trace has
{total_events} events; you see at most {cap}). Summarize the executed path
and note any uncertainty caused by the sampling cap.

trace_run_id: {trace_run_id}
language: {language}
exception_count: {exception_count}
event_digest:
{digest}

Respond with a single JSON object and nothing else:
{{"executed_path_summary": "<one- or two-sentence path summary>",
 "uncertainty_notes": ["<optional notes>"]}}
"""


class LLMTraceSummarizer(TraceSummarizerInterface):
    """Trace summarizer backed by an injected LLM completion callable."""

    version = "b3.v1"

    def __init__(
        self,
        *,
        complete: Callable[[str], str],
        model_id: str,
    ) -> None:
        self._complete = complete
        self.model_id = model_id

    def summarize(
        self,
        raw_artefact: RawTraceArtefact,
        scope_filter: ScopeFilter,
        budget_tokens: int = 2000,
    ) -> CompressedTrace:
        # Deterministic event selection is shared with the null summarizer;
        # the LLM only ever rewrites the natural-language summary fields.
        base = NullTraceSummarizer().summarize(
            raw_artefact, scope_filter, budget_tokens
        )

        digest_events = (base.relevant_events + base.exception_events)[
            :_DIGEST_EVENT_CAP
        ]
        digest = "\n".join(
            f"- {event.event_type} {event.module}.{event.function} "
            f"({event.file_path}:{event.line_number})"
            for event in digest_events
        )
        prompt = _PROMPT_TEMPLATE.format(
            total_events=raw_artefact.event_count,
            cap=_DIGEST_EVENT_CAP,
            trace_run_id=raw_artefact.trace_run_id,
            language=raw_artefact.language,
            exception_count=len(base.exception_events),
            digest=digest or "- none",
        )
        raw = self._complete(prompt)
        parsed = self._parse_response(raw)
        summary = parsed.get("executed_path_summary")
        if not isinstance(summary, str) or not summary.strip():
            return base

        raw_notes = parsed.get("uncertainty_notes")
        note_candidates = raw_notes if isinstance(raw_notes, list) else []
        notes = [note for note in note_candidates if isinstance(note, str)]
        return base.model_copy(
            update={
                "executed_path_summary": summary.strip(),
                "uncertainty_notes": notes or base.uncertainty_notes,
                "summarizer_model": self.model_id,
            }
        )

    @staticmethod
    def _parse_response(raw: str) -> dict[str, object]:
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed
