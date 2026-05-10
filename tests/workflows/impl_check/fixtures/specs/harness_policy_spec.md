# Harness Policy Specification

## Hard Constraints

HC1 must be enforced: No plaintext secrets in repository, prompts, logs, or commits.
The AGENTS.md policy gate must run before every merge.
The verification gate shall pass before any deployment.
