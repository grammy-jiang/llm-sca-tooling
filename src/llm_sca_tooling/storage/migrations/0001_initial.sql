CREATE TABLE IF NOT EXISTS workspace_metadata (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repositories (
  repo_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  root_path TEXT NOT NULL,
  root_path_hash TEXT NOT NULL,
  vcs_type TEXT NOT NULL,
  remote_url_hash TEXT,
  default_branch TEXT,
  current_branch TEXT,
  registered_ts TEXT NOT NULL,
  last_seen_ts TEXT NOT NULL,
  active INTEGER NOT NULL,
  index_status TEXT NOT NULL,
  latest_snapshot_id TEXT,
  capabilities_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  UNIQUE(root_path)
);
CREATE INDEX IF NOT EXISTS idx_repositories_active ON repositories(active);
CREATE INDEX IF NOT EXISTS idx_repositories_name ON repositories(name);
CREATE INDEX IF NOT EXISTS idx_repositories_latest_snapshot ON repositories(latest_snapshot_id);

CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  git_sha TEXT,
  branch TEXT,
  dirty INTEGER NOT NULL,
  worktree_snapshot_id TEXT,
  index_status TEXT NOT NULL,
  captured_ts TEXT NOT NULL,
  source_run_id TEXT,
  source_event_id TEXT,
  file_state_hash TEXT,
  diagnostics_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_repo ON snapshots(repo_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_git_sha ON snapshots(repo_id, git_sha);
CREATE INDEX IF NOT EXISTS idx_snapshots_worktree ON snapshots(repo_id, worktree_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_status ON snapshots(repo_id, index_status);
CREATE INDEX IF NOT EXISTS idx_snapshots_captured_ts ON snapshots(captured_ts);

CREATE TABLE IF NOT EXISTS graph_nodes (
  node_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  qualified_name TEXT,
  file_path TEXT,
  start_line INTEGER,
  end_line INTEGER,
  confidence REAL NOT NULL,
  derivation TEXT NOT NULL,
  evidence_strength TEXT NOT NULL,
  provenance_hash TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_repo_snapshot ON graph_nodes(repo_id, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON graph_nodes(repo_id, node_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_file ON graph_nodes(repo_id, snapshot_id, file_path);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_qualified_name ON graph_nodes(repo_id, qualified_name);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_span ON graph_nodes(repo_id, file_path, start_line, end_line);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_derivation ON graph_nodes(derivation);

CREATE TABLE IF NOT EXISTS graph_edges (
  edge_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
  edge_type TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
  target_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
  confidence REAL NOT NULL,
  derivation TEXT NOT NULL,
  evidence_strength TEXT NOT NULL,
  provenance_hash TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_repo_snapshot ON graph_edges(repo_id, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_type ON graph_edges(repo_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source_type ON graph_edges(source_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target_type ON graph_edges(target_id, edge_type);

CREATE TABLE IF NOT EXISTS graph_diagnostics (
  diagnostic_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT REFERENCES snapshots(snapshot_id),
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  affected_node_ids_json TEXT NOT NULL,
  affected_edge_ids_json TEXT NOT NULL,
  provenance_json TEXT,
  created_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS graph_manifests (
  graph_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
  node_count INTEGER NOT NULL,
  edge_count INTEGER NOT NULL,
  chunk_artifact_ids_json TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  generated_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS harness_metadata (
  metadata_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  kind TEXT NOT NULL,
  active INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_harness_metadata_repo_kind ON harness_metadata(repo_id, kind, active);

CREATE TABLE IF NOT EXISTS supply_chain_records (
  supply_chain_record_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  component_type TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT,
  source TEXT,
  hash TEXT,
  payload_json TEXT NOT NULL,
  captured_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_supply_chain_repo ON supply_chain_records(repo_id);
CREATE INDEX IF NOT EXISTS idx_supply_chain_component ON supply_chain_records(component_type);

CREATE TABLE IF NOT EXISTS run_records (
  run_id TEXT PRIMARY KEY,
  workflow TEXT NOT NULL,
  user_intent_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT,
  toolset_hash TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  permission_profile TEXT NOT NULL,
  harness_condition_id TEXT,
  final_verdict_id TEXT,
  run_event_count INTEGER NOT NULL,
  redaction_policy_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_records_workflow ON run_records(workflow);
CREATE INDEX IF NOT EXISTS idx_run_records_status ON run_records(status);
CREATE INDEX IF NOT EXISTS idx_run_records_start_ts ON run_records(start_ts);

CREATE TABLE IF NOT EXISTS run_repositories (
  run_id TEXT NOT NULL REFERENCES run_records(run_id),
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  PRIMARY KEY(run_id, repo_id)
);
CREATE INDEX IF NOT EXISTS idx_run_repositories_repo ON run_repositories(repo_id);

CREATE TABLE IF NOT EXISTS run_events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run_records(run_id),
  seq INTEGER NOT NULL,
  ts TEXT NOT NULL,
  type TEXT NOT NULL,
  actor TEXT NOT NULL,
  stage TEXT NOT NULL,
  policy_action TEXT,
  redaction_status TEXT NOT NULL,
  token_count INTEGER,
  wall_ms INTEGER,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  UNIQUE(run_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_run_events_type ON run_events(type);
CREATE INDEX IF NOT EXISTS idx_run_events_stage ON run_events(stage);
CREATE INDEX IF NOT EXISTS idx_run_events_ts ON run_events(ts);
CREATE INDEX IF NOT EXISTS idx_run_events_policy_action ON run_events(policy_action);

CREATE TABLE IF NOT EXISTS harness_conditions (
  harness_condition_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES run_records(run_id),
  toolset_hash TEXT NOT NULL,
  permission_profile TEXT NOT NULL,
  captured_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operational_records (
  record_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  run_id TEXT REFERENCES run_records(run_id),
  event_id TEXT REFERENCES run_events(event_id),
  kind TEXT NOT NULL,
  status TEXT,
  policy_action TEXT,
  severity TEXT,
  incident_id TEXT,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operational_records_repo ON operational_records(repo_id);
CREATE INDEX IF NOT EXISTS idx_operational_records_run ON operational_records(run_id);
CREATE INDEX IF NOT EXISTS idx_operational_records_kind ON operational_records(kind);
CREATE INDEX IF NOT EXISTS idx_operational_records_incident ON operational_records(incident_id);
CREATE INDEX IF NOT EXISTS idx_operational_records_created_ts ON operational_records(created_ts);
CREATE INDEX IF NOT EXISTS idx_operational_records_policy_action ON operational_records(policy_action);

CREATE TABLE IF NOT EXISTS incidents (
  incident_id TEXT PRIMARY KEY,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  primary_repo_id TEXT REFERENCES repositories(repo_id),
  opened_ts TEXT NOT NULL,
  closed_ts TEXT,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_runs (
  incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
  run_id TEXT NOT NULL REFERENCES run_records(run_id),
  PRIMARY KEY(incident_id, run_id)
);

CREATE TABLE IF NOT EXISTS incident_events (
  incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
  event_id TEXT NOT NULL REFERENCES run_events(event_id),
  PRIMARY KEY(incident_id, event_id)
);

CREATE TABLE IF NOT EXISTS promotion_records (
  promotion_id TEXT PRIMARY KEY,
  source_run_id TEXT NOT NULL REFERENCES run_records(run_id),
  target_type TEXT NOT NULL,
  review_state TEXT NOT NULL,
  owner TEXT,
  expires_ts TEXT,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promotion_source_run ON promotion_records(source_run_id);
CREATE INDEX IF NOT EXISTS idx_promotion_target_type ON promotion_records(target_type);
CREATE INDEX IF NOT EXISTS idx_promotion_review_state ON promotion_records(review_state);

CREATE TABLE IF NOT EXISTS readiness_reports (
  readiness_report_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repositories(repo_id),
  stage TEXT NOT NULL,
  total_score INTEGER NOT NULL,
  threshold_status TEXT NOT NULL,
  no_regression_status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readiness_reports_repo ON readiness_reports(repo_id, created_ts);
CREATE INDEX IF NOT EXISTS idx_readiness_reports_stage ON readiness_reports(stage);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  run_id TEXT REFERENCES run_records(run_id),
  kind TEXT NOT NULL,
  uri TEXT NOT NULL,
  sha256 TEXT,
  size_bytes INTEGER,
  media_type TEXT,
  redaction_status TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_repo ON artifacts(repo_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256);
