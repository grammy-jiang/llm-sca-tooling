# Investigate

Phase 9 fault-localisation skill with LLM reasoning chains.

Use this skill after `get_relevant_files` has assembled a bounded context bundle.

## Workflow

1. Normalize the issue text into symptoms, expected/observed behaviour, file and
   symbol mentions, error strings, and stack frames.
2. Run `get_relevant_files` with the available registered repositories and a
   default 6-10 file context budget.
3. Use only the returned ranked candidates, context bundle reference, graph
   slices, SARIF evidence, blame evidence, and exact spans.
4. **LLM reasoning chains** (when `FLSamplingClient` is available):
   - Pass a `sampling_client` to `LocalisationService(sampling_client=...)`.
   - The service calls `ReasoningChainScaffold.llm_chain()` to build a
     structured reasoning chain from the context bundle.
   - The chain output annotates each candidate with a natural-language
     justification backed by evidence spans.
5. Produce per-candidate reasoning that cites only paths and symbols present in
   the returned evidence.
6. Mark the result uncertain when signal agreement is low or the context budget
   is exceeded.
7. **Hindsight relabelling** (post-resolution only): use `LLMHindsightRelabeller`
   to reassign trajectory outcomes based on post-fix evidence. This runs after
   the repair workflow completes in Phase 13.

## Notes

- Phase 13 connects this template to the repair workflow.
- Phase 9 (read-only) does not author patches from this skill.
- Network egress is denied; `LLMHindsightRelabeller` uses keyword-matching
  fallback when no sampling endpoint is configured.
