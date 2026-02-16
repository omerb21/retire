from datetime import datetime


def _setup_tools_and_state(
    *,
    request,
    db,
    stream_request_id: str,
    original_user_msg: str,
    resolved_intent,
    advice_compensation_mode: bool,
    log_llm_event,
    logger,
    load_current_effective_state,
    load_latest_pension_portfolio_snapshot_models,
    build_restore_snapshot_banner_helper,
    latest_snapshot_operation_type_helper,
    wrap_with_restore_banner_helper,
    build_recent_state_banner_helper,
    ChatIntentClass,
 ):
    tools_enabled_reason: str | None = None
    tools_disabled_reason: str | None = None

    tools_enabled = bool(getattr(request, "tools_enabled", True))
    if advice_compensation_mode:
        tools_enabled = True

    if not tools_enabled:
        tools_enabled_reason = getattr(request, "tools_disabled_reason", None)
        tools_disabled_reason = tools_enabled_reason
        resolved_intent = ChatIntentClass.NO_TOOLS

    ui_action_short_circuit_allowed = tools_disabled_reason not in {"conceptual", "conceptual_form"}

    try:
        log_llm_event(
            request_id=stream_request_id,
            event_type="intent_resolution",
            payload={"intent": resolved_intent.value},
            client_id=request.client_id,
            extra={"endpoint": "stream"},
        )
    except Exception:
        pass

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    effective_state: dict | None = None
    _portfolio_source = "request_payload"
    if request.client_id is not None:
        try:
            effective_state = load_current_effective_state(db, request.client_id)
        except Exception:
            effective_state = None
        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded
            _portfolio_source = "db_snapshot"
            try:
                logger.info(
                    "📦 Using DB pension_portfolio_snapshot (client_id=%s, accounts=%s, snapshot_at=%s)",
                    request.client_id,
                    len(effective_portfolio),
                    effective_snapshot_at,
                )
            except Exception:
                pass

    try:
        from app.services.agent_trace_logger import log_trace_event
        log_trace_event(
            event_type="state_source",
            payload={
                "portfolio_source": _portfolio_source,
                "portfolio_count": len(effective_portfolio) if effective_portfolio else 0,
                "snapshot_at": str(effective_snapshot_at) if effective_snapshot_at else None,
                "has_effective_state": effective_state is not None,
            },
            client_id=request.client_id,
            endpoint="/api/v1/llm/pension-chat-stream",
        )
    except Exception:
        pass

    def _build_restore_snapshot_banner(*, now_utc: datetime) -> str | None:
        return build_restore_snapshot_banner_helper(
            db=db,
            client_id=request.client_id,
            effective_state=effective_state,
            now_utc=now_utc,
        )

    def _latest_snapshot_operation_type() -> str | None:
        return latest_snapshot_operation_type_helper(db=db, client_id=request.client_id)

    def _wrap_with_restore_banner(inner):
        yield from wrap_with_restore_banner_helper(
            inner=inner,
            db=db,
            client_id=request.client_id,
            effective_state=effective_state,
            resolved_intent=resolved_intent,
        )

    def _build_recent_state_banner() -> str | None:
        return build_recent_state_banner_helper(
            db=db,
            client_id=request.client_id,
            effective_state=effective_state,
            resolved_intent=resolved_intent,
        )

    return (
        tools_enabled_reason,
        tools_disabled_reason,
        tools_enabled,
        ui_action_short_circuit_allowed,
        resolved_intent,
        effective_portfolio,
        effective_snapshot_at,
        effective_state,
        _build_restore_snapshot_banner,
        _latest_snapshot_operation_type,
        _wrap_with_restore_banner,
        _build_recent_state_banner,
    )
