from __future__ import annotations


def _build_messages_and_prompt(*, request, db, logger):
    from app.services.llm_chat.chat_orchestration_parts.chat_top_level_helpers import (
        _load_latest_pension_portfolio_snapshot_models,
    )
    from app.services.llm_chat.message_preparation import prepare_messages_with_context
    from app.services.llm_chat.message_utils import find_last_user_message

    # 1) Start from request payload
    req_portfolio = request.pension_portfolio
    req_snapshot_at = request.pension_portfolio_snapshot_at

    request_has_portfolio = isinstance(req_portfolio, list) and len(req_portfolio) > 0

    # Optional override flags (safe even if not defined on request)
    prefer_db_snapshot = bool(getattr(request, "prefer_db_pension_portfolio_snapshot", False))
    force_db_snapshot = bool(getattr(request, "force_db_pension_portfolio_snapshot", False))
    use_db_even_if_request_has_portfolio = prefer_db_snapshot or force_db_snapshot

    effective_portfolio = req_portfolio if request_has_portfolio else []
    effective_snapshot_at = req_snapshot_at

    # Request portfolio count for logs
    try:
        request_portfolio_count = len(req_portfolio) if isinstance(req_portfolio, list) else 0
    except Exception:
        request_portfolio_count = 0

    # 2) Load from DB only as fallback (or forced)
    if request.client_id is not None and (
        (not request_has_portfolio) or use_db_even_if_request_has_portfolio
    ):
        loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            db_portfolio, db_snapshot_at = loaded
            effective_portfolio = db_portfolio or []
            effective_snapshot_at = db_snapshot_at or effective_snapshot_at
            try:
                logger.info(
                    "📦 Portfolio source=DB snapshot (client_id=%s, request_accounts=%s, db_accounts=%s, db_snapshot_at=%s, forced=%s)",
                    request.client_id,
                    request_portfolio_count,
                    len(effective_portfolio) if isinstance(effective_portfolio, list) else 0,
                    effective_snapshot_at,
                    bool(use_db_even_if_request_has_portfolio),
                )
            except Exception:
                pass
        else:
            # No DB snapshot found, keep request (even if empty) as-is
            try:
                logger.info(
                    "📦 Portfolio source=request (no DB snapshot found) (client_id=%s, request_accounts=%s, request_snapshot_at=%s)",
                    request.client_id,
                    request_portfolio_count,
                    req_snapshot_at,
                )
            except Exception:
                pass
    else:
        # client_id missing OR request has portfolio and we are not forced to use DB
        try:
            logger.info(
                "📦 Portfolio source=request (client_id=%s, request_accounts=%s, request_snapshot_at=%s)",
                request.client_id,
                request_portfolio_count,
                req_snapshot_at,
            )
        except Exception:
            pass

    # Log state_source for trace observability
    try:
        from app.services.agent_trace_logger import log_trace_event
        _portfolio_source = "request_payload"
        if request.client_id is not None and (
            (not request_has_portfolio) or use_db_even_if_request_has_portfolio
        ):
            _portfolio_source = "db_snapshot"
        log_trace_event(
            event_type="state_source",
            payload={
                "portfolio_source": _portfolio_source,
                "portfolio_count": len(effective_portfolio) if effective_portfolio else 0,
                "snapshot_at": str(effective_snapshot_at) if effective_snapshot_at else None,
            },
            client_id=request.client_id,
            endpoint="/api/v1/llm/pension-chat",
        )
    except Exception:
        pass

    messages, computed_data = prepare_messages_with_context(request, db)
    original_user_msg = find_last_user_message(request.messages)

    return (
        effective_portfolio,
        effective_snapshot_at,
        messages,
        computed_data,
        original_user_msg,
    )
