# release

Use when preparing a package or workflow release.

## Preconditions

- All required feature, workflow, operational, and release gates are known.
- No open P0/P1 incidents block release.

## Steps

1. Run `make verify` and any release-specific gates.
2. Confirm readiness no-regression.
3. Confirm dependency, SAST, and secrets evidence.
4. Prepare release notes with risks, rollback path, and dependency changes.

## Done

- Release evidence is complete and auditable.
- Rollback and incident paths are documented.
