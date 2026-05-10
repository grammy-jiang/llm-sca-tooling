CREATE TABLE IF NOT EXISTS memory_policy (
  workspace_id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_trajectories (
  trajectory_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  issue_class TEXT NOT NULL,
  outcome TEXT NOT NULL,
  utility TEXT NOT NULL,
  review_state TEXT NOT NULL,
  expiry_ts TEXT,
  source_run_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_trajectories_repo ON memory_trajectories(repo_id, review_state);
CREATE INDEX IF NOT EXISTS idx_memory_trajectories_issue ON memory_trajectories(repo_id, issue_class);
CREATE INDEX IF NOT EXISTS idx_memory_trajectories_utility ON memory_trajectories(repo_id, utility);

CREATE TABLE IF NOT EXISTS project_memory_records (
  record_id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  record_type TEXT NOT NULL,
  review_state TEXT NOT NULL,
  expiry_ts TEXT,
  source_run_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_project_memory_repo ON project_memory_records(repo_id, review_state);
CREATE INDEX IF NOT EXISTS idx_project_memory_type ON project_memory_records(repo_id, record_type);

CREATE TABLE IF NOT EXISTS operational_lessons (
  lesson_id TEXT PRIMARY KEY,
  source_run_id TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  target_type TEXT NOT NULL,
  review_state TEXT NOT NULL,
  promoted_to_ref TEXT,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operational_lessons_source ON operational_lessons(source_run_id, source_event_id);

CREATE TABLE IF NOT EXISTS memory_compaction_reports (
  report_id TEXT PRIMARY KEY,
  repo_id TEXT,
  dry_run INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_compaction_repo ON memory_compaction_reports(repo_id, created_ts);
