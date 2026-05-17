## Compliance Summary
- `overall_verdict`: `partially_compliant`
- `satisfied_clauses`: 5
- `violated_clauses`: 0
- `unknown_clauses`: 5
- Primary artifact: `.agent/artifacts/docs_audit_impl_check_20260517.json`

## Confirmed Gaps
- No direct violated clauses were reported by the MCP implementation check.
- The five unknown clauses remain review-required because the graph build
  skipped hidden governance paths (`.agent`, `.agents`, `.codex`, `.github`)
  and MCP relevance responses for Markdown/docs returned `span=null`.
- Clause investigation artifact:
  `.agent/artifacts/docs_audit_clause_investigation_20260517.json`

## Readiness Blockers
- Readiness stage: `S3`
- AI-readiness score: 22
- Missing gates: none
- Weak docs/spec links: none
- Drift finding: `.codex/INSTRUCTIONS.md does not restate HC controls`
- Readiness artifact:
  `.agent/artifacts/docs_audit_readiness_20260517.json`

## Verification
- `make verify`: passed
- Pip audit reported no known vulnerabilities.
- Bandit reported no issues identified.

## Policy Events
- HC2 out-of-scope generated changes occurred during MCP/verify execution in
  `.llm-sca/`, `.secrets.baseline`, and `uv.lock`.
- Those generated changes were reverted with `git restore`.
- Remaining intentional writes are limited to `.agent/plan.md` and
  `.agent/artifacts/`.

## Next Steps
- Address or waive the readiness drift finding for `.codex/INSTRUCTIONS.md`.
- If exact file:line evidence is required for docs clauses, rerun with a graph
  policy that indexes the hidden governance paths or add non-hidden mirrors for
  the required contracts.
