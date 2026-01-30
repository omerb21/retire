import json

from fastapi.responses import StreamingResponse


def _maybe_handle_pre_retirement_plan_resolution_yes_no(
    *,
    request,
    db,
    stream_request_id: str,
    lowered_user_msg: str,
    load_pending_pre_retirement_plan_resolution,
    clear_pending_pre_retirement_plan_resolution,
    load_latest_pension_portfolio_snapshot_models,
    coerce_float_safe,
    compute_existing_income_offset_monthly,
    build_transform_accounts_from_portfolio,
    execute_tool_call,
    sanitize_user_visible_text,
    format_tool_output_for_user_stream,
    store_pending_approval_request,
    build_approval_request_ui_action,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
    clear_pending_plan_target_marker,
    clear_pending_approval_request,
 ):
    if lowered_user_msg not in {"כן", "לא"}:
        return None

    pending_payload = None
    try:
        pending_payload = load_pending_pre_retirement_plan_resolution(
            db=db,
            client_id=request.client_id,
        )
    except Exception:
        pending_payload = None

    if not (isinstance(pending_payload, dict) and pending_payload.get("requested_target") is not None):
        return None

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    try:
        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded
    except Exception:
        pass

    requested_target = coerce_float_safe(pending_payload.get("requested_target"))
    target_is_net_val = bool(pending_payload.get("target_is_net", True))
    retirement_age_val = pending_payload.get("retirement_age")
    retirement_age_int = None
    if retirement_age_val is not None:
        try:
            retirement_age_int = int(retirement_age_val)
        except Exception:
            retirement_age_int = None

    if lowered_user_msg == "לא":
        try:
            clear_pending_pre_retirement_plan_resolution(db=db, client_id=request.client_id)
        except Exception:
            pass
        existing_income_offset = compute_existing_income_offset_monthly(
            db=db,
            client_id=request.client_id,
            target_is_net=bool(target_is_net_val),
        )
        eff_target = max(float(requested_target) - float(existing_income_offset), 0.0)
        if eff_target <= 0:
            return StreamingResponse(
                iter(["היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת"]),
                media_type="text/plain; charset=utf-8",
            )

        plan_args = {
            "target_monthly_pension": float(eff_target),
            "target_is_net": bool(target_is_net_val),
        }
        if retirement_age_int is not None:
            plan_args["retirement_age"] = int(retirement_age_int)

        def _run_plan_after_no(req_id: str):
            plan_result = execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                plan_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            stored_data_ok = False
            try:
                stored_data_ok = bool(
                    store_latest_target_pension_plan_data(
                        db=db,
                        client_id=request.client_id,
                        tool_result=plan_result,
                    )
                )
            except Exception:
                stored_data_ok = False

            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass

            if stored_data_ok:
                try:
                    clear_pending_plan_target_marker(db=db, client_id=request.client_id)
                except Exception:
                    pass
                try:
                    clear_pending_approval_request(db=db, client_id=request.client_id)
                except Exception:
                    pass

            try:
                tool_result_text = (
                    plan_result
                    if isinstance(plan_result, str)
                    else json.dumps(plan_result, ensure_ascii=False)
                )
            except Exception:
                tool_result_text = str(plan_result)
            yield sanitize_user_visible_text(
                "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", tool_result_text)
            )

        return StreamingResponse(
            _run_plan_after_no(stream_request_id),
            media_type="text/plain; charset=utf-8",
        )

    try:
        clear_pending_pre_retirement_plan_resolution(db=db, client_id=request.client_id)
    except Exception:
        pass
    accounts = build_transform_accounts_from_portfolio(effective_portfolio)
    if not accounts:
        return StreamingResponse(
            iter(["לא הצלחתי לבנות רשימת חשבונות להמרה מתוך הסנאפשוט."]),
            media_type="text/plain; charset=utf-8",
        )

    transform_args = {
        "accounts": accounts,
        "use_provided_accounts_only": True,
        "ignore_blocked_balances": False,
        "skip_non_convertible_accounts": True,
        "_after_build_target_pension_plan_args": {
            "target_monthly_pension": float(requested_target),
            "target_is_net": bool(target_is_net_val),
            "retirement_age": retirement_age_int,
            "_pre_retirement_plan_resolution": True,
        },
    }
    try:
        store_pending_approval_request(
            db=db,
            client_id=request.client_id,
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=transform_args,
        )
    except Exception:
        pass
    ui_action = build_approval_request_ui_action(
        tool_name="TRANSFORM_FUNDS_TO_ASSETS",
        tool_args=transform_args,
        reason="נדרש אישור לפני המרה כדי לכלול יתרות חסומות בתכנון",
        risk_level="high",
        rag_sources=None,
    )
    return StreamingResponse(iter([ui_action]), media_type="text/plain; charset=utf-8")
