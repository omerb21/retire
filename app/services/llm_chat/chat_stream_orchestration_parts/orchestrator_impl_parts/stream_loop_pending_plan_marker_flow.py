import json

from fastapi.responses import StreamingResponse


def _maybe_handle_pending_plan_target_marker_flow(
    *,
    request,
    db,
    stream_request_id: str,
    original_user_msg: str,
    client_id: int | None,
    pending_plan,
    target_net,
    delete_marker,
    sanitize_user_visible_text,
    ClientModel,
    infer_retirement_age_for_plan_args,
    execute_tool_call,
    get_tool_display_name_hebrew,
    format_tool_output_for_user_stream,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
 ):
    if not (
        pending_plan is not None
        and target_net is not None
        and (not original_user_msg.startswith("###USER_APPROVED###"))
    ):
        return None

    if pending_plan.is_expired():
        delete_marker(pending_plan)

        def _prompt_for_target_net_again():
            yield sanitize_user_visible_text(
                "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n" "כתוב: יעד נטו: <מספר>."
            )

        return StreamingResponse(
            _prompt_for_target_net_again(),
            media_type="text/plain; charset=utf-8",
        )

    def _exec_target_plan_tools_first():
        tool_name = "BUILD_TARGET_PENSION_PLAN"
        tool_args = {
            "target_monthly_pension": float(target_net),
            "target_is_net": True,
        }
        pending_payload = None
        try:
            pending_payload = json.loads(pending_plan.row.parameters or "{}")
        except Exception:
            pending_payload = None
        client_obj = None
        try:
            client_obj = db.query(ClientModel).filter(ClientModel.id == client_id).first()
        except Exception:
            client_obj = None
        inferred_age = infer_retirement_age_for_plan_args(
            client_obj=client_obj,
            pending_payload=pending_payload if isinstance(pending_payload, dict) else None,
        )
        if inferred_age is not None:
            tool_args["retirement_age"] = int(inferred_age)
        tool_result = execute_tool_call(
            tool_name,
            tool_args,
            client_id,
            db,
            pension_portfolio=request.pension_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=stream_request_id,
        )
        try:
            store_latest_target_pension_plan_data(
                db=db,
                client_id=client_id,
                tool_result=tool_result,
            )
        except Exception:
            pass
        try:
            store_latest_target_pension_plan(
                db=db,
                client_id=client_id,
                tool_result=tool_result,
            )
        except Exception:
            pass
        yield sanitize_user_visible_text(
            "🔧 **פלט כלי (" + get_tool_display_name_hebrew(tool_name) + "):**\n"
            + format_tool_output_for_user_stream(tool_name, tool_result)
        )
        delete_marker(pending_plan)

    return StreamingResponse(
        _exec_target_plan_tools_first(),
        media_type="text/plain; charset=utf-8",
    )
