"""JSON Schema exporter.

Exports Pydantic models to ``.schema.json`` files in the ``schemas/``
directory.  Call ``export_all()`` after changing any schema model to keep
the checked-in JSON Schema files in sync with the Python source of truth.

Usage::

    from llm_sca_tooling.schemas.json_schema import export_all
    export_all()           # write to schemas/ relative to repo root
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson
from pydantic import BaseModel

from llm_sca_tooling.schemas.evidence import EvidenceBundle
from llm_sca_tooling.schemas.governance import PolicyDecisionSchema
from llm_sca_tooling.schemas.graph import GraphDocument
from llm_sca_tooling.schemas.harness import HarnessCondition
from llm_sca_tooling.schemas.incidents import Incident
from llm_sca_tooling.schemas.readiness import AIReadinessReport
from llm_sca_tooling.schemas.run_records import RunRecord
from llm_sca_tooling.schemas.verdicts import Verdict

__all__ = ["export_schema", "export_all", "SCHEMA_EXPORTS"]

# The repo-root ``schemas/`` directory (sibling of ``src/``)
_DEFAULT_OUT_DIR = Path(__file__).parent.parent.parent.parent / "schemas"


def export_schema(model: type[BaseModel], path: Path) -> None:
    """Export the JSON Schema for *model* to *path*.

    The output is canonical JSON (sorted keys, 2-space indent).
    """
    schema: dict[str, Any] = model.model_json_schema()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        orjson.dumps(schema, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
    )


# Registry: (output filename, source model)
SCHEMA_EXPORTS: list[tuple[str, type[BaseModel]]] = [
    ("graph.schema.json", GraphDocument),
    ("run-record.schema.json", RunRecord),
    ("harness-condition.schema.json", HarnessCondition),
    ("readiness.schema.json", AIReadinessReport),
    ("incident.schema.json", Incident),
    ("evidence.schema.json", EvidenceBundle),
    ("verdict.schema.json", Verdict),
    ("governance.schema.json", PolicyDecisionSchema),
]


def export_all(out_dir: Path | None = None) -> None:
    """Export all registered schema models to ``schemas/``."""
    target = out_dir or _DEFAULT_OUT_DIR
    for filename, model in SCHEMA_EXPORTS:
        export_schema(model, target / filename)
