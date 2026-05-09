CREATE TABLE IF NOT EXISTS sarif_runs (
  run_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
  git_sha TEXT,
  worktree_snapshot_id TEXT,
  analyser_id TEXT NOT NULL,
  analyser_version TEXT,
  analyser_name TEXT NOT NULL,
  ruleset_id TEXT NOT NULL,
  ruleset_name TEXT,
  invocation_start_ts TEXT,
  invocation_end_ts TEXT,
  invocation_exit_code INTEGER,
  invocation_successful INTEGER NOT NULL,
  alert_count INTEGER NOT NULL,
  rule_count INTEGER NOT NULL,
  raw_sarif_artifact_id TEXT,
  produced_by_run_id TEXT,
  delta_from_run_id TEXT,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sarif_runs_repo ON sarif_runs(repo_id, invocation_start_ts);
CREATE INDEX IF NOT EXISTS idx_sarif_runs_analyser ON sarif_runs(repo_id, analyser_id, ruleset_id);

CREATE TABLE IF NOT EXISTS sarif_rules (
  rule_pk TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES sarif_runs(run_id),
  rule_id TEXT NOT NULL,
  analyser_id TEXT NOT NULL,
  name TEXT,
  short_description TEXT,
  normalized_severity TEXT NOT NULL,
  cwe_ids_json TEXT NOT NULL,
  owasp_json TEXT NOT NULL,
  rule_family TEXT NOT NULL,
  predicate_id TEXT,
  tags_json TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  rule_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sarif_rules_run ON sarif_rules(run_id);
CREATE INDEX IF NOT EXISTS idx_sarif_rules_rule ON sarif_rules(rule_id);

CREATE TABLE IF NOT EXISTS sarif_alerts (
  alert_pk TEXT PRIMARY KEY,
  alert_id TEXT NOT NULL,
  run_id TEXT NOT NULL REFERENCES sarif_runs(run_id),
  rule_id TEXT NOT NULL,
  analyser_id TEXT NOT NULL,
  normalized_severity TEXT NOT NULL,
  message TEXT NOT NULL,
  file_path TEXT,
  start_line INTEGER,
  start_column INTEGER,
  end_line INTEGER,
  end_column INTEGER,
  suppressed INTEGER NOT NULL,
  fingerprint TEXT NOT NULL,
  baseline_state TEXT,
  bound_file_node_id TEXT,
  bound_symbol_ids_json TEXT NOT NULL,
  binding_confidence TEXT NOT NULL,
  alert_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sarif_alerts_run ON sarif_alerts(run_id);
CREATE INDEX IF NOT EXISTS idx_sarif_alerts_alert_id ON sarif_alerts(alert_id);
CREATE INDEX IF NOT EXISTS idx_sarif_alerts_file ON sarif_alerts(file_path);
CREATE INDEX IF NOT EXISTS idx_sarif_alerts_rule ON sarif_alerts(rule_id);
CREATE INDEX IF NOT EXISTS idx_sarif_alerts_severity ON sarif_alerts(normalized_severity);

CREATE TABLE IF NOT EXISTS sarif_deltas (
  delta_id TEXT PRIMARY KEY,
  before_run_id TEXT NOT NULL REFERENCES sarif_runs(run_id),
  after_run_id TEXT NOT NULL REFERENCES sarif_runs(run_id),
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  appeared_count INTEGER NOT NULL,
  disappeared_count INTEGER NOT NULL,
  unchanged_count INTEGER NOT NULL,
  changed_count INTEGER NOT NULL,
  new_critical_high_count INTEGER NOT NULL,
  fixed_critical_high_count INTEGER NOT NULL,
  delta_json TEXT NOT NULL,
  computed_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sarif_deltas_runs ON sarif_deltas(before_run_id, after_run_id);
CREATE INDEX IF NOT EXISTS idx_sarif_deltas_repo ON sarif_deltas(repo_id, computed_ts);
