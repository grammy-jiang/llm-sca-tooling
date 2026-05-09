# dependency-update

Use when adding, removing, or upgrading dependencies.

## Preconditions

- Identify why the dependency change is needed.
- Confirm network access and package-publish actions are approved if required.

## Steps

1. Update dependency metadata and lockfiles with the chosen package manager.
2. Run tests that cover the dependency use.
3. Run dependency audit and secrets scan.
4. Record versions and audit result in the Harness Condition Sheet.

## Done

- Lockfile and metadata are consistent.
- Dependency risks are documented or resolved.
