"""Stage 1: Markdown spec ingestion."""

from __future__ import annotations

import hashlib

from llm_sca_tooling.impl_check.models import SpecDocument


def ingest_spec(*, doc_id: str, source: str, title: str = "") -> SpecDocument:
    content_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
    return SpecDocument(
        doc_id=doc_id,
        source_path=f"inline://{doc_id}",
        doc_format="markdown",
        title=title or doc_id,
        content_hash=content_hash,
        provenance={"ingestion": "phase14-null-mode"},
    )
