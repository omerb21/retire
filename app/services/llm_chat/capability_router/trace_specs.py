from __future__ import annotations

from app.services.llm_chat.orchestration_core.core_types import TraceEventSpec
from app.services.llm_chat.capability_router.runtime_context import RouterDecision


def build_router_selected_trace_spec(*, trace_id: str | None, decision: RouterDecision) -> TraceEventSpec:
    return TraceEventSpec(
        event_type="router_selected",
        trace_id=trace_id,
        payload={
            "capability_id": decision.capability_id,
            "mode": decision.mode,
            "output_schema_id": decision.output_schema_id,
            "tool_chain": list(decision.tool_chain),
            "capability_map_version": decision.capability_map_version,
            "router_normalization_version": decision.router_normalization_version,
            "normalized_text_hash": decision.normalized_text_hash,
        },
    )
