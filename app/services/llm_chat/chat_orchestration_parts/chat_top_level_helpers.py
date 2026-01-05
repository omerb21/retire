from typing import Any

from .tool_calling import _get_chat_orchestration_facade


def _get_llm_service():
    facade = _get_chat_orchestration_facade()
    svc = getattr(facade, "pension_llm_service", None)
    if svc is not None:
        return svc
    from app.services.llm_pension_agent_service import pension_llm_service as _local_llm_service

    return _local_llm_service


def _load_latest_pension_portfolio_snapshot_models(*args: Any, **kwargs: Any) -> Any:
    facade = _get_chat_orchestration_facade()
    fn = getattr(facade, "load_latest_pension_portfolio_snapshot_models", None)
    if callable(fn):
        return fn(*args, **kwargs)
    from app.services.pension_portfolio.snapshot_loader import (
        load_latest_pension_portfolio_snapshot_models as _local_loader,
    )

    return _local_loader(*args, **kwargs)
