"""LLM trace summarizer (Tier B3).

Spec rules: raw traces are never inserted wholesale into LLM context — the
summarizer feeds the LLM a capped digest and only the natural-language summary
is LLM-derived; the event lists stay deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

import orjson

from llm_sca_tooling.traces.compression.llm_summarizer import LLMTraceSummarizer
from llm_sca_tooling.traces.compression.null_summarizer import NullTraceSummarizer
from llm_sca_tooling.traces.models import RawTraceArtefact, ScopeFilter


def _artefact(tmp_path: Path, event_count: int = 200) -> RawTraceArtefact:
    events_path = tmp_path / "events.jsonl"
    rows = []
    for index in range(event_count):
        rows.append(
            {
                "event_id": f"evt:{index}",
                "event_type": "exception" if index == 5 else "call",
                "module": "service",
                "function": f"fn_{index % 7}",
                "file_path": "src/service.py",
                "line_number": index,
            }
        )
    events_path.write_bytes(b"\n".join(orjson.dumps(r) for r in rows))
    return RawTraceArtefact(
        artefact_id="artefact:raw:0001",
        trace_run_id="trace:0001",
        language="python",
        adapter_version="test.v1",
        events_jsonl_path=str(events_path),
        event_count=event_count,
    )


def test_llm_summarizer_summary_is_llm_derived_events_deterministic(
    tmp_path: Path,
) -> None:
    prompts: list[str] = []

    def fake_complete(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(
            {
                "executed_path_summary": "service.fn_0 loops, raises at line 5",
                "uncertainty_notes": ["sampling capped at 50 events"],
            }
        )

    summarizer = LLMTraceSummarizer(complete=fake_complete, model_id="m1")
    artefact = _artefact(tmp_path)
    compressed = summarizer.summarize(artefact, ScopeFilter(), budget_tokens=2000)

    assert compressed.executed_path_summary == "service.fn_0 loops, raises at line 5"
    assert compressed.uncertainty_notes == ["sampling capped at 50 events"]
    assert compressed.summarizer_model == "m1"
    # Event lists are deterministic and identical to the null summarizer's.
    null_compressed = NullTraceSummarizer().summarize(
        artefact, ScopeFilter(), budget_tokens=2000
    )
    assert [e.event_id for e in compressed.relevant_events] == [
        e.event_id for e in null_compressed.relevant_events
    ]
    assert [e.event_id for e in compressed.exception_events] == [
        e.event_id for e in null_compressed.exception_events
    ]


def test_raw_trace_never_sent_wholesale(tmp_path: Path) -> None:
    prompts: list[str] = []

    def fake_complete(prompt: str) -> str:
        prompts.append(prompt)
        return "{}"

    summarizer = LLMTraceSummarizer(complete=fake_complete, model_id="m1")
    summarizer.summarize(_artefact(tmp_path, event_count=500), ScopeFilter(), 2000)

    assert prompts
    # 500 raw events, digest capped: the prompt must not contain every event id.
    assert "evt:499" not in prompts[0]


def test_malformed_llm_output_falls_back_to_null_summary(tmp_path: Path) -> None:
    summarizer = LLMTraceSummarizer(complete=lambda p: "not json", model_id="m1")
    artefact = _artefact(tmp_path)
    compressed = summarizer.summarize(artefact, ScopeFilter(), budget_tokens=2000)

    null_compressed = NullTraceSummarizer().summarize(
        artefact, ScopeFilter(), budget_tokens=2000
    )
    assert compressed.executed_path_summary == null_compressed.executed_path_summary
    assert compressed.summarizer_model == "null"
