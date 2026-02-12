from fastapi.responses import StreamingResponse


def _maybe_handle_requested_cashflow_calc(
    *,
    request,
    db,
    original_user_msg: str,
    requested_cashflow_calc: bool,
    resolved_intent,
    ChatIntentClass,
    tools_enabled: bool,
    is_qa_mode: bool,
    no_tools_requested: bool,
    commutation_intent: bool,
    conceptual_tools_disabled: bool,
    effective_portfolio,
    force_max_exemption: bool,
    stream_request_id: str,
    build_recent_state_banner,
    load_latest_pension_portfolio_snapshot_models,
    generate_cashflow,
 ):
    if not (
        requested_cashflow_calc
        and (not commutation_intent)
        and (not conceptual_tools_disabled)
        and (resolved_intent != ChatIntentClass.REPORT)
    ):
        return None

    if (
        (request.client_id is not None)
        and (not is_qa_mode)
        and (not commutation_intent)
    ):

        def generate_cashflow_tool_exec():
            banner = build_recent_state_banner()
            if banner:
                yield banner + "\n\n"

            portfolio_for_cashflow = effective_portfolio

            try:
                loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    portfolio_for_cashflow, _snapshot_at = loaded
            except Exception:
                pass

            yield from generate_cashflow(
                computed_data=None,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=portfolio_for_cashflow,
                force_max_exemption=force_max_exemption,
                stream_request_id=stream_request_id,
            )

        return StreamingResponse(
            generate_cashflow_tool_exec(),
            media_type="text/plain",
        )

    return StreamingResponse(
        iter(["כדי להריץ חישוב תזרים/ניתוח תזרים אני צריך הפעלה עם client_id תקין."]),
        media_type="text/plain",
    )
