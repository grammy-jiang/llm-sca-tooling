# blast-radius (Phase 15 — hardened)

Entry: `blast-radius(change_set, repos?)`.

## Workflow

1. Call `BlastRadiusService.compute(change_set)`.
2. Read the `BlastRadiusReport`.
3. Report all eight impact groups with counts and representative examples:
   - DIRECT_CALLERS
   - DOWNSTREAM_BEHAVIOURS
   - TESTS
   - INTERFACES
   - SERVICES
   - REPOSITORIES
   - SARIF_REACHABILITY
   - LINKED_DOCS_SPECS
4. Report generated-stub notes with recommended actions.
5. Report ABI impact for C/C++ changes (or `unknown` fallback if backend unavailable).
6. Report cross-repo impact records.
7. Separate confirmed and ambiguous links explicitly — never merge them.
8. State `is_partial: true` with partial reason if cross-repo or ABI analysis is unavailable.
9. Flag SARIF reachability changes for security-sensitive and IDL changes.
10. Flag stale implementation-check verdicts in LINKED_DOCS_SPECS.

## Rules

- Never merge ambiguous links with confirmed links in any summary.
- Always include `is_partial` flag when cross-repo or ABI analysis is unavailable.
- Generated files directly changed: flag `manual_edit_policy_flag: true` unless allowlist permits.
- ABI notes must always be produced for C/C++ changes — `unknown` fallback if backend absent.
- Template snapshot must be stable.

## Change-type traversal policies

| Change type | Max hops | Cross-language | Cross-repo | SARIF reachability |
|---|---|---|---|---|
| INTERNAL_IMPLEMENTATION | 3 | No | No | No |
| PUBLIC_API_CHANGE | 5 | Yes | Yes | No |
| IDL_SCHEMA_CONTRACT_CHANGE | 6 | Yes | Yes | Yes |
| SECURITY_SENSITIVE_CHANGE | 4 | Yes | Yes | Yes |
| GENERATED_FILE_CHANGE | 2 | No | No | No |
