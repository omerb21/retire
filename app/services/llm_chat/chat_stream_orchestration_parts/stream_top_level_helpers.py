import importlib
from typing import Any

from app.services.llm_chat.chat_orchestration_helpers import build_transform_accounts_from_target_plan_payload
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)

PC_LLM_MAX_RETRIES = 3
PC_LLM_TIMEOUT_SECONDS = 120.0
PC_LLM_BACKOFF_SECONDS = (0.75, 1.5, 3.0)


def _get_stream_orchestration_facade():
    # NOTE: Must be dynamic import so that pytest monkeypatching
    # app.services.llm_chat.chat_stream_orchestration continues to affect
    # runtime behavior even though logic lives in *_parts.
    return importlib.import_module("app.services.llm_chat.chat_stream_orchestration")


def _store_pending_approval_request(*args: Any, **kwargs: Any) -> Any:
    return _get_stream_orchestration_facade().store_pending_approval_request(*args, **kwargs)


def _get_llm_service():
    return _get_stream_orchestration_facade().pension_llm_service


def _get_retry_settings() -> tuple[int, float, tuple[float, ...]]:
    facade = _get_stream_orchestration_facade()
    try:
        retries = int(getattr(facade, "PC_LLM_MAX_RETRIES", PC_LLM_MAX_RETRIES) or 1)
    except Exception:
        retries = int(PC_LLM_MAX_RETRIES or 1)
    try:
        timeout = float(getattr(facade, "PC_LLM_TIMEOUT_SECONDS", PC_LLM_TIMEOUT_SECONDS) or 0)
    except Exception:
        timeout = float(PC_LLM_TIMEOUT_SECONDS or 0)
    try:
        backoffs = getattr(facade, "PC_LLM_BACKOFF_SECONDS", PC_LLM_BACKOFF_SECONDS)
    except Exception:
        backoffs = PC_LLM_BACKOFF_SECONDS
    try:
        backoffs_tuple = tuple(float(x) for x in (backoffs or ()))
    except Exception:
        backoffs_tuple = tuple(float(x) for x in PC_LLM_BACKOFF_SECONDS)
    return retries, timeout, backoffs_tuple


def _load_latest_pension_portfolio_snapshot_models(*args: Any, **kwargs: Any) -> Any:
    facade = _get_stream_orchestration_facade()
    fn = getattr(facade, "load_latest_pension_portfolio_snapshot_models", None)
    if callable(fn):
        return fn(*args, **kwargs)
    # Fallback to local import (shouldn't happen, but keeps runtime robust)
    return load_latest_pension_portfolio_snapshot_models(*args, **kwargs)


def _build_transform_accounts_from_target_plan_payload(payload: dict) -> list[dict]:
    facade = _get_stream_orchestration_facade()
    fn = getattr(facade, "build_transform_accounts_from_target_plan_payload", None)
    if callable(fn):
        out = fn(payload)
        return out if isinstance(out, list) else []
    try:
        out = build_transform_accounts_from_target_plan_payload(payload)
        return out if isinstance(out, list) else []
    except Exception:
        return []
