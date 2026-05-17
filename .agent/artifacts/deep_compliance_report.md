# Deep Compliance Report — research-pipeline (methodology audit)

**Date**: 2025-07-13
**Spec used**: `docs/implementation-plan.md` + `docs/architecture.md` + deep-research/*.md reports
**Previous audit method**: direct_file_inspection (structural only)
**This audit method**: code-level formula/parameter verification + spec cross-check

---

## Confirmed Correct (with code evidence)

| Phase | Spec Requirement | Code Evidence |
|-------|-----------------|---------------|
| 3.1 | model=`allenai/specter2` | `embedding.py:35,79` |
| 3.1 | batch_size=32 | `embedding.py:79,144` |
| 3.1 | lazy-load + cache | `embedding.py:49-50` (`_model_cache`) |
| 3.1 | GPU if available | `embedding.py:67` (`torch.cuda.is_available()`) |
| 3.2 | query format `"{topic} [SEP]"` | `embedding.py:158` |
| 3.2 | candidate text = `title + " " + abstract` | `embedding.py:159` |
| 3.2 | cosine similarity | `embedding.py:120-134` |
| 3.2 | scores normalized [0,1] | `embedding.py:171-177` |
| 3.3 | bm25_title total=0.20, bm25_abstract total=0.25 | `heuristic.py:99-108` (0.12+0.08=0.20, 0.15+0.10=0.25) |
| 3.3 | semantic_similarity=0.25 | `heuristic.py:104` |
| 3.3 | cat_match=0.12, negative_penalty=0.08, recency_bonus=0.10 | `heuristic.py:105-107` |
| 3.4 | `use_semantic_reranking`, `embedding_model`, `embedding_batch_size` in ScreenConfig | `config/models.py:40-42` |
| 5.1 | `min(1.0, log(1+n) / log(1+1000))` | `citation_metrics.py:28` |
| 5.2 | A*=1.0, A=0.8, B=0.5, C=0.3, unknown=0.1 | `venue_scoring.py:14-21` |
| 5.2 | bundled core_rankings.json | `venue_scoring.py:43` |
| 5.3 | `min(1.0, log(1+h) / log(1+100))` | `author_metrics.py:28` |
| 5.3 | max h-index used | `author_metrics.py:16` |
| 4.1 | S2 API `/paper/{id}/citations` and `/paper/{id}/references` | `citation_graph.py:321` |
| 4.1 | rate limit 1 req/sec | `citation_graph.py:56` (RateLimiter min_interval=1.0) |
| 4.1 | `get_citations(paper_id, limit=50)` | `citation_graph.py:82` |
| 4.1 | `get_references(paper_id, limit=50)` | `citation_graph.py:94` |
| 4.2 | `fetch_related(paper_ids, direction="both\|cit\|ref")` | `citation_graph.py:106` |
| 6.1 | retry backoff: base=2.0, jitter=±25%, Retry-After header | `retry.py:40-97` |
| Q2D | template-based query augmentation | `q2d_augmentation.py` |
| Q2D | domain synonym expansion (LLM→large language model, etc.) | `q2d_augmentation.py:22-66` |

---

## Confirmed Gaps (methodology-level)

### GAP-002 (HIGH): DEFAULT_WEIGHTS in composite.py diverge from spec

- **Clause**: implementation-plan.md §5.4 and §5.7
- **Spec**: citation_weight=0.35, venue_weight=0.25, author_weight=0.25, recency_weight=0.15 (4 components, sum=1.00)
- **DEFAULT_WEIGHTS in code**: citation_weight=0.30, venue_weight=0.20, author_weight=0.20, recency_weight=0.15, reproducibility_weight=0.15 (5 components, sum=1.00)
- **QualityConfig defaults**: citation_weight=0.35 (matches spec) — but NOT passed to compute_quality_score() by default
- **Impact**: Direct calls to `compute_quality_score(candidate)` without weights use wrong defaults. CLI and MCP calls build weights from QualityConfig but omit `reproducibility_weight`, so `w.get("reproducibility_weight", 0.0)` returns 0.0 — reproducibility feature exists but is never actually enabled.
- **Fix**: (a) Add `reproducibility_weight: float = 0.0` to QualityConfig; (b) Update DEFAULT_WEIGHTS to match spec + add reproducibility_weight=0.0; (c) Pass reproducibility_weight in CLI and MCP weights dicts.

### GAP-003 (MEDIUM): Missing `get_venue_tier` MCP tool

- **Clause**: implementation-plan.md §5.6
- **Spec**: "New MCP tool — Input: `venue_name` → Output: `{tier: "A*"|"A"|"B"|"C"|null, score: float}`"
- **Current state**: `venue_score()` and `get_venue_tier()` functions exist in `venue_scoring.py` but are NOT exposed as MCP tools in `server.py`
- **Fix**: Add `get_venue_tier` tool to mcp_server/server.py

### GAP-004 (MEDIUM): Missing `compute_semantic_scores` standalone MCP tool

- **Clause**: implementation-plan.md §3.5
- **Spec**: "New MCP tool — Input: `run_id`, `topic` → Output: list of `{arxiv_id, semantic_score}`"
- **Current state**: semantic scoring only runs inside `screen_candidates` when `use_semantic_reranking=True`; no standalone semantic scoring tool exists
- **Fix**: Add `compute_semantic_scores` tool to mcp_server/server.py

---

## Research Report Findings

| Report | Key Algorithms | Implementation Status |
|--------|----------------|----------------------|
| citation-graph-expansion | BFS forward/backward/both, budget-aware stopping | ✅ `bfs_expand()` in citation_graph.py |
| citation-graph-expansion | CitationEdge provenance model | ❌ Not implemented (aspirational per plan) |
| q2d-query-augmentation | Template-based Q2D (Phase Q1) | ✅ q2d_augmentation.py |
| q2d-query-augmentation | LLM-based Q2D (Phase Q2) | ❌ Not implemented (Phase Q2, OK) |
| evaluation-framework-gaps | RACE/FACT dual metrics, coherence, blinding audit | ✅ dual_metrics, coherence, blinding_audit tools |
| memory-system-integration | Session memory store, memory search | ✅ memory_stats/episodes/search tools |
| self-improving-retrieval | Feedback loop, RL weight adjustment | ✅ record_feedback, adaptive_stopping tools |

---

## Next Steps

1. Fix GAP-002: Align DEFAULT_WEIGHTS, add reproducibility_weight to QualityConfig, update callers
2. Fix GAP-003: Add get_venue_tier MCP tool
3. Fix GAP-004: Add compute_semantic_scores MCP tool
4. Run make verify, commit, push, release
