from __future__ import annotations

from app.schemas.llm_chat import ChatResponse

from .legacy_loader import load_legacy_steps_module
from .types import _PreparedOrchestrationInputs


def _prepare_orchestration_inputs(
    *,
    request,
    db,
    request_id: str,
    logger,
    log_llm_event_fn,
) -> _PreparedOrchestrationInputs | ChatResponse:
    legacy_module = load_legacy_steps_module()
    return legacy_module._prepare_orchestration_inputs(
        request=request,
        db=db,
        request_id=request_id,
        logger=logger,
        log_llm_event_fn=log_llm_event_fn,
    )
