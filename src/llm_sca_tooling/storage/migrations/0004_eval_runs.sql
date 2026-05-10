CREATE TABLE IF NOT EXISTS eval_runs (
  eval_run_id TEXT PRIMARY KEY,
  suite_id TEXT NOT NULL,
  status TEXT NOT NULL,
  harness_condition_id TEXT NOT NULL,
  started_ts TEXT NOT NULL,
  completed_ts TEXT,
  payload_json TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eval_runs_suite ON eval_runs(suite_id, created_ts);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON eval_runs(status, created_ts);
CREATE INDEX IF NOT EXISTS idx_eval_runs_hcs ON eval_runs(harness_condition_id);
