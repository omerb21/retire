import json

from fastapi.responses import StreamingResponse

from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    store_pending_approval_request,
)
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    evaluate_blocked_balances_policy_for_build_target_plan,
)

from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
    compute_effective_plan_target,
)


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
            media_type="text/plain",
        )

    def _exec_target_plan_tools_first():
        tool_name = "BUILD_TARGET_PENSION_PLAN"
        requested_target = float(target_net)
        breakdown = None
        if client_id is not None:
            breakdown = compute_effective_plan_target(
                db=db,
                client_id=int(client_id),
                desired_total=requested_target,
                target_is_net=True,
            )

        _effective = breakdown.effective_plan_target if breakdown is not None else requested_target
        if _effective <= 0:
            yield "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת."
            delete_marker(pending_plan)
            return

        tool_args = {
            "target_monthly_pension": float(requested_target),
            "target_is_net": True,
        }

        if client_id is not None:
            policy_status, tool_args, policy_text = evaluate_blocked_balances_policy_for_build_target_plan(
                db=db,
                client_id=int(client_id),
                portfolio=request.pension_portfolio,
                plan_args=tool_args,
            )
            if isinstance(policy_text, str) and policy_text.strip():
                yield policy_text.strip() + "\n\n"
            if policy_status == "ask_current_employer_termination":
                delete_marker(pending_plan)
                return
            if policy_status == "needs_termination_approval":
                termination_args = {"confirmed": True}
                try:
                    store_pending_approval_request(
                        db=db,
                        client_id=int(client_id),
                        tool_name="PROCESS_TERMINATION",
                        tool_args=termination_args,
                    )
                except Exception:
                    pass
                yield build_approval_request_ui_action(
                    tool_name="PROCESS_TERMINATION",
                    tool_args=termination_args,
                    reason="נדרש אישור לפני ביצוע עזיבת עבודה במערכת.",
                    risk_level="high",
                    rag_sources=None,
                )
                delete_marker(pending_plan)
                return

        breakdown_lines: list[str] = []
        breakdown_lines.append("✅ חישוב דטרמיניסטי:")
        breakdown_lines.append(f"- יעד חודשי מבוקש (נטו): {requested_target:,.0f} ₪")
        if breakdown is not None and breakdown.other_income_offset_net > 0:
            breakdown_lines.append(
                f"- קיזוז הכנסות נוספות (נטו): {breakdown.other_income_offset_net:,.0f} ₪"
            )
        breakdown_lines.append(
            f"- יעד קצבה לתכנית (נטו, אחרי קיזוז הכנסות נוספות): {_effective:,.0f} ₪"
        )
        yield "\n".join(breakdown_lines) + "\n\n"

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
        media_type="text/plain",
    )
