# sast-repair

Arguments: `alert_id`, optional `repo`.

1. Call `get_predicate_examples(alert_id)` to retrieve fix-knowledge.
2. Call `run_sast_repair(alert_id)` as a task.
3. Poll until completion.
4. Read the `SASTRepairReport`.
5. Report alert classification, predicate examples used, SARIF delta, build/test result, and patch-risk class.
6. If `alert_fixed`, state the fix clearly and include remaining-risk notes when non-empty.
7. If `alert_fixed_with_risk`, state the fix with the remaining-risk callout.
8. If `repair_blocked`, state the new alert(s) introduced.
9. If `false_positive_suppressed`, present the suppression proposal for reviewer decision.
10. Include the Harness Condition Sheet reference and `run_id`.

Do not claim `alert_fixed` when `original_alert_remains` is true. Never suppress new critical alerts. Always flag `reviewer_required` for suppression proposals.
