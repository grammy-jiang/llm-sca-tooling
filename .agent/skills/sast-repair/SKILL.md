# sast-repair

Use when repairing a static-analysis alert.

## Preconditions

- Capture the original alert, rule ID, file, line, and analyser version.
- Bind the alert to repository evidence when available.

## Steps

1. Reproduce or import the alert.
2. Write a regression test when practical.
3. Apply the smallest fix.
4. Re-run the analyser or SARIF import path.
5. Compare before/after SARIF or alert state.

## Done

- The target alert is resolved or explicitly downgraded with evidence.
- No new high/critical alerts are introduced.
