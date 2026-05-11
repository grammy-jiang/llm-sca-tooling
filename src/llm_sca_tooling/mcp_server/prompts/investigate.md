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
For each candidate, state the signal evidence, graph/static evidence, counter-evidence, and a concise reasoning chain.

## Constraints
- Only cite file paths and symbol names from the pre-assembled evidence.
- Mark localisation as uncertain if fewer than {min_agreement_signals} signals agree.
- Do not expand context beyond the pre-assembled bundle.
