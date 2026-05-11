---
name: dependency-update
description: >
  Update a Python dependency with lockfile regeneration, test, SAST, and
  licence checks. Use when asked to update, bump, or upgrade a dependency
  version, when a CVE is reported in a dependency, when `pip-audit` flags a
  vulnerable package, or when asked to keep dependencies current.
compatibility: >
  Requires Python 3.12+, uv, pip-audit, and bandit installed in the dev
  environment (`uv sync`). Run `make verify` before starting.
license: MIT
metadata:
  version: "1.0.0"
---

# dependency-update

## Preconditions

- A specific dependency and target version are identified
- `make verify` passes on the current branch before starting
- The update is within the write allowlist (`pyproject.toml`, `uv.lock`)

## Steps

1. **Check changelog** of the dependency for breaking changes and CVEs
2. **Update version constraint** in `pyproject.toml`
3. **Regenerate lockfile**: `uv lock`
4. **Run test suite**: `uv run pytest tests/ -x`
5. **Run dependency audit**: `uv run pip-audit`
6. **Run SAST**: `uv run bandit -r src/ -c pyproject.toml`
7. **Check licence compatibility**: new version must not introduce an incompatible or copyleft licence
8. **Update supply-chain ledger**: `.agent/eval/supply-chain-ledger.yaml`
9. **Run full verify**: `make verify`
10. **Update `plan.md`** with decisions log

## Verify Gate

```bash
uv run pip-audit
make verify
```

## Completion Criteria

- `uv.lock` updated and committed alongside `pyproject.toml`
- `uv run pip-audit` reports no new critical CVEs
- All tests pass
- Licence compatibility confirmed
- Supply-chain ledger updated with new version, `last_updated_ts`, `dependency_scan_ts`
- PR description notes: dependency name, old version, new version, reason, CVE/licence status
