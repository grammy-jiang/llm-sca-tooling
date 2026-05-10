"""Stage 1: Markdown spec document ingestion."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from llm_sca_tooling.workflows.impl_check.models import SpecDocument


def ingest_markdown(
    source: str | Path, doc_id: str | None = None
) -> tuple[SpecDocument, str]:
    """Ingest a Markdown document. Returns (SpecDocument, raw_text)."""
    if isinstance(source, Path):
        raw_text = source.read_text(encoding="utf-8")
        source_path = str(source)
    else:
        raw_text = source
        source_path = "<inline>"

    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    if doc_id is None:
        doc_id = f"doc:{content_hash[:24]}"

    title = ""
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            break

    spec_doc = SpecDocument(
        doc_id=doc_id,
        source_path=source_path,
        doc_format="markdown",
        title=title,
        content_hash=content_hash,
        ingested_ts=datetime.now(UTC).isoformat(),
        clause_count=0,
        provenance={"ingested_from": source_path},
    )
    return spec_doc, raw_text
