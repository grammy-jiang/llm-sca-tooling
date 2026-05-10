---
name: investigate
description: Phase 13 investigate stage skill — combine Phase 9 fault localisation with Phase 8 repo-QA behavioural context to produce ranked file/symbol candidates. Use when the bug-resolve workflow enters the `investigate` stage.
metadata:
  version: 0.1.0
---

# investigate

Private skill template for the investigate stage of the bug-resolve workflow.

## Entry

`investigate(issue_text, repos?, budget?)`

## Instructions

1. Normalise the issue text using Phase 9's `IssueTextNormalizer`.
2. Call `get_relevant_files(issue_text, repos)` to run fault localisation.
3. For each of the top-3 suspects:
   a. Call `get_graph_slice(node_id)` to load the symbol graph context.
   b. Call `get_interface_contract(path)` to check interface membership.
4. Call `answer_repo_question` for behavioural context on each suspect.
5. Flag answers with `confidence < 0.5` as supporting evidence, not hard evidence.
6. If the graph snapshot is stale relative to the issue timestamp, set
   `stale_snapshot_flag: true`.
7. Assemble `InvestigateResult` with `ranked_candidates`,
   `top3_file_suspects`, `agreement_score`, and `diagnostics`.

## Output

`InvestigateResult` containing:
- `ranked_candidates` — ordered by combined FL score.
- `top3_file_suspects` — top-3 file paths.
- `repo_qa_answers` — Phase 8 answers for behavioural context.
- `behavioural_context` — answers above confidence threshold.
- `stale_snapshot_flag` — whether graph snapshot is stale.

## Rules

- Empty `ranked_candidates` transitions the workflow to `completed_no_fix`.
- Repo-QA answers with `QuestionClass.BEHAVIOUR_TRACE` below the Phase 8 ship
  gate (≥70% accuracy) are tagged as supporting evidence only.
- Context budget starts at top-6 suspects; expands to top-10 if evidence is sparse.
