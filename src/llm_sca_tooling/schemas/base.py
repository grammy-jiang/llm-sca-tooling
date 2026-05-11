"""Schema base primitives.

Every schema model uses :class:`StrictModel` as its base.
Use :func:`canonical_dumps` for deterministic JSON in test snapshots and
schema exports.  Never use ``json.dumps`` or ``json.loads`` in Phase 1 code.
"""

from __future__ import annotations

from typing import Annotated, Any, TypeVar

import orjson
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "SCHEMA_VERSION",
    "JsonValue",
    "NonEmptyStr",
    "StrictModel",
    "ExtensibleModel",
    "canonical_dumps",
    "canonical_loads",
]

SCHEMA_VERSION: str = "0.1.0"

JsonValue = str | int | float | bool | None | dict[str, Any] | list[Any]
NonEmptyStr = Annotated[str, Field(min_length=1)]

T = TypeVar("T", bound=BaseModel)


class StrictModel(BaseModel):
    """Base for all stable contract models.  Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True)


class ExtensibleModel(BaseModel):
    """Base for models with controlled extension points.

    Use for ``attributes``, ``properties``, and ``metadata`` fields where
    language backends or workflow plugins attach structured data.
    """

    model_config = ConfigDict(extra="ignore", frozen=False)


def canonical_dumps(model: BaseModel) -> bytes:
    """Serialize a model to canonical JSON bytes (sorted keys).

    Suitable for test snapshots and schema exports.  The output is
    deterministic: same model state always produces the same bytes.
    """
    return orjson.dumps(
        model.model_dump(mode="json"),
        option=orjson.OPT_SORT_KEYS,
    )


def canonical_loads(data: bytes | str, model_class: type[T]) -> T:
    """Parse canonical JSON bytes or string to a model instance."""
    return model_class.model_validate(orjson.loads(data))
