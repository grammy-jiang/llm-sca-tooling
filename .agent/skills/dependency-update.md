# SKILL: dependency-update

Update a dependency with lockfile, test, SAST, and licence checks.

---

## Preconditions

- A specific dependency and target version are identified.
- `make verify` passes on the current branch before starting.
- The update is within the write allowlist (pyproject.toml, uv.lock).

---

## Steps

1. **Check the changelog** of the dependency for breaking changes and CVEs.
2. **Update the version constraint** in `pyproject.toml`.
3. **Regenerate the lockfile**: `uv lock`.
4. **Run the test suite**: `uv run pytest tests/ -x`.
5. **Run the dependency audit**: `uv run pip-audit`.
6. **Run SAST** (S1+): `uv run bandit -r src/ -c pyproject.toml`.
7. **Check licence compatibility**: the new version must not introduce an
   incompatible or copyleft licence.
8. **Update the supply-chain ledger**: `.agent/eval/supply-chain-ledger.yaml`.
9. **Run full verify**: `make verify`.
10. **Update plan.md** with decisions log.

---

## Verify Gate

```
uv run pip-audit
make verify
```

---

## Completion Criteria

- `uv.lock` is updated and committed alongside `pyproject.toml`.
- `uv run pip-audit` reports no new critical CVEs.
- All tests pass.
- Licence compatibility confirmed.
- Supply-chain ledger updated with new version, `last_updated_ts`, and `dependency_scan_ts`.
- PR description notes the dependency name, old version, new version, reason for update,
  and CVE/licence status.
