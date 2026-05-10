"""Phase 16 integration hooks."""

from llm_sca_tooling.traces.integration.bug_resolve_hook import should_run_trace_gate
from llm_sca_tooling.traces.integration.fl_hook import augment_localisation_with_trace
from llm_sca_tooling.traces.integration.impl_check_hook import (
    dynamic_verdict_payload_from_trace,
)
from llm_sca_tooling.traces.integration.patch_review_hook import (
    mismatch_with_trace_ref,
)

__all__ = [
    "augment_localisation_with_trace",
    "dynamic_verdict_payload_from_trace",
    "mismatch_with_trace_ref",
    "should_run_trace_gate",
]
