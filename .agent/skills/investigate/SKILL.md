# Investigate

Private Phase 9 skill foundation for fault localisation.

Use this skill after `get_relevant_files` has assembled a bounded context bundle.
The workflow is intentionally read-only in Phase 9:

1. Normalize the issue text into symptoms, expected/observed behaviour, file and
   symbol mentions, error strings, and stack frames.
2. Run `get_relevant_files` with the available registered repositories and a
   default 6-10 file context budget.
3. Use only the returned ranked candidates, context bundle reference, graph
   slices, SARIF evidence, blame evidence, and exact spans.
4. Produce per-candidate reasoning that cites only paths and symbols present in
   the returned evidence.
5. Mark the result uncertain when signal agreement is low or the context budget
   is exceeded.

Phase 13 will connect this template to the repair workflow. Phase 9 does not
author patches from this skill.
