"""Tests for base primitives."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.base import (
    SCHEMA_VERSION,
    canonical_dumps,
    canonical_loads,
)
from llm_sca_tooling.schemas.provenance import RepoRef


def test_schema_version_is_semver() -> None:
    parts = SCHEMA_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_strict_model_rejects_extra_fields() -> None:
    with pytest.raises(Exception):
        RepoRef(repo_id="repo:x", unknown_field="bad")  # type: ignore[call-arg]


def test_canonical_dumps_is_deterministic() -> None:
    ref = RepoRef(repo_id="repo:x", name="x")
    a = canonical_dumps(ref)
    b = canonical_dumps(ref)
    assert a == b


def test_canonical_dumps_sorts_keys() -> None:
    ref = RepoRef(repo_id="repo:x", name="x", default_branch="main")
    data = canonical_dumps(ref)
    # Verify the output parses back and is canonical JSON
    import orjson

    parsed = orjson.loads(data)
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_canonical_round_trip() -> None:
    ref = RepoRef(repo_id="repo:demo", name="demo")
    dumped = canonical_dumps(ref)
    loaded = canonical_loads(dumped, RepoRef)
    assert loaded == ref


def test_non_empty_str_rejects_empty() -> None:
    with pytest.raises(Exception):
        RepoRef(repo_id="")
