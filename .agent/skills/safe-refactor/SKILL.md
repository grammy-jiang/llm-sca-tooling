# safe-refactor

Use when changing structure without intended behaviour changes.

## Preconditions

- Document the preserved public behaviour.
- Identify tests that cover the touched surface.

## Steps

1. Capture current test results for the target area.
2. Make mechanical changes in small steps.
3. Keep API compatibility unless explicitly approved.
4. Run targeted tests and `make verify`.

## Done

- Behavioural tests remain unchanged.
- Any public API movement is documented.
