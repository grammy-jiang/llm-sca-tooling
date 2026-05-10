# Investigate: Fault Localisation

## Context
- Issue: {issue_text_normalized}
- Repos: {repos}
- Budget: {budget}

## Pre-assembled evidence
{context_bundle_summary}

## Candidate ranking
{ranked_candidates_with_signals}

## Instructions
For each candidate:
1. State the signal evidence linking the issue to this candidate.
2. State any graph/static evidence (calls, data-flow, SARIF, blame).
3. State counter-evidence if present.
4. Produce a 2-3 sentence reasoning chain.

After reasoning through each candidate, produce a final ranked list
with the most likely root-cause location first.

## Constraints
- Only cite file paths and symbol names from the pre-assembled evidence.
- Mark localisation as uncertain if fewer than {min_agreement_signals} signals agree.
- Do not expand context beyond the pre-assembled bundle.
