# SAST Repair

Private Phase 12 SAST repair loop template.

Use `run_sast_repair` to bind a SARIF alert to graph nodes, retrieve
predicate examples, and generate a candidate fix.

Workflow:
1. Bind the alert to a graph node using the file path and rule ID.
2. Retrieve predicate examples from the corpus (PredicateFix-style).
3. Assemble bounded context: graph slice, blame chain, SARIF neighbours.
4. Generate a candidate patch that eliminates the alert predicate.
5. Verify the SARIF delta: the alert must disappear; no new alerts may appear.
6. Run tests and confirm the suite passes.

Record the repair in a Harness Condition Sheet before committing.
