# risk-classify

Private Phase 11 skill for patch-risk classification before merge.

Use after `blast-radius` analysis to produce a final risk verdict.

## Preconditions

- A candidate patch diff and blast-radius report.
- The repository is registered and indexed.

## Steps

1. Feed the diff to `classify_patch_risk` with the associated repo and run_id.
2. Examine SARIF delta: call `run_static_analysis` before and after the patch if SARIF data is available.
3. Check contract compatibility: call `get_interface_contract` for any modified public API.
4. Apply risk class rules:
   - **LOW**: no SARIF delta, no interface breakage, blast radius < 5 files.
   - **MEDIUM**: minor SARIF change, internal callers affected, blast radius 5-20 files.
   - **HIGH**: new SARIF alert, public interface changed, blast radius > 20 files, or critical path crossed.
5. Record rationale for the risk class, especially for MEDIUM/HIGH.
6. HIGH risk: escalate to human review before merge; do not auto-merge.

## Done

- `classify_patch_risk` verdict is recorded with evidence.
- HIGH risk patches are blocked pending human approval.
- Risk verdict is attached to the patch review report.
