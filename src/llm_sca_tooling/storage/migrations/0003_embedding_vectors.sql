CREATE TABLE IF NOT EXISTS embedding_vectors (
  cache_key TEXT PRIMARY KEY,
  repo_id TEXT REFERENCES repositories(repo_id),
  file_path TEXT,
  node_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  git_sha TEXT NOT NULL,
  worktree_snapshot_id TEXT,
  vector_blob BLOB NOT NULL,
  dimensions INTEGER NOT NULL,
  text_hash TEXT NOT NULL,
  produced_ts TEXT NOT NULL,
  expires_ts TEXT,
  hit_count INTEGER NOT NULL DEFAULT 0,
  last_hit_ts TEXT
);
CREATE INDEX IF NOT EXISTS idx_embedding_node ON embedding_vectors(node_id, model_id);
CREATE INDEX IF NOT EXISTS idx_embedding_git_sha ON embedding_vectors(git_sha);
CREATE INDEX IF NOT EXISTS idx_embedding_repo_file ON embedding_vectors(repo_id, file_path);
