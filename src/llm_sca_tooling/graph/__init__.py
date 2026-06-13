"""Graph namespace.

The in-memory graph layer designed for this package in Phase 0 was absorbed
into the storage layer during Phase 3: graph persistence lives in
``llm_sca_tooling.storage.graph_store`` and traversal/queries in
``llm_sca_tooling.storage.graph_queries``. This package re-exports the query
surface so the documented namespace resolves to the real implementation.
"""

from llm_sca_tooling.storage.graph_queries import GraphQueryStore

__all__ = ["GraphQueryStore"]
