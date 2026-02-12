import re

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


def _maybe_handle_plan_phrase_flow(
    *,
    original_user_msg: str,
    request,
    db,
    stream_request_id: str,
    client_id: int | None,
    ClientModel,
    extract_target_net_ils,
    load_effective_client_state,
    sanitize_user_visible_text,
    load_latest_pension_portfolio_snapshot_models,
    infer_retirement_age_for_plan_args,
    pre_retirement_plan_resolution,
    execute_tool_call,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
    get_tool_display_name_hebrew,
    format_tool_output_for_user_stream,
    infer_pending_retirement_fields_for_marker,
    store_pending_plan_target_marker,
 ):
    plan_phrase_detected = False
    try:
        msg_norm = (original_user_msg or "").replace("תוכנית", "תכנית")
        msg_norm_stripped = msg_norm.strip()
        msg_lower = msg_norm_stripped.lower()
        has_plan_phrase = bool(
            re.search(r"(?:^|\s)תכנית\s+(?:קצבה|יעד)(?:\s|$)", msg_norm_stripped)
            or re.search(
                r"(?:^|\s)חשב\s+תכנית\s+(?:קצבה|יעד)(?:\s|$)",
                msg_norm_stripped,
            )
        )
        has_retirement_plan_phrase = bool(
            ("תכנית פרישה" in msg_norm_stripped)
            and (re.search(r"\b\d{4,6}\b", msg_norm_stripped) is not None)
            and (("נטו" in msg_norm_stripped) or ("net" in msg_lower))
        )
        plan_phrase_detected = bool(has_plan_phrase or has_retirement_plan_phrase)
    except Exception:
        plan_phrase_detected = False

    if not plan_phrase_detected:
        return None

    # Never block plan building based on a post-conversion lock.

    target_net_from_phrase = extract_target_net_ils(original_user_msg)
    if target_net_from_phrase is not None and client_id is not None:

        def _exec_target_plan_tools_first_from_phrase():
            tool_name = "BUILD_TARGET_PENSION_PLAN"
            effective_portfolio = request.pension_portfolio
            try:
                if not isinstance(effective_portfolio, list) or not effective_portfolio:
                    loaded = load_latest_pension_portfolio_snapshot_models(db, client_id)
                    if loaded is not None:
                        effective_portfolio, _effective_snapshot_at = loaded
            except Exception:
                pass

            client_obj = None
            try:
                client_obj = db.query(ClientModel).filter(ClientModel.id == client_id).first()
            except Exception:
                client_obj = None

            inferred_age = infer_retirement_age_for_plan_args(
                client_obj=client_obj, pending_payload=None
            )

            requested_target = float(target_net_from_phrase)
            breakdown = compute_effective_plan_target(
                db=db,
                client_id=int(client_id),
                desired_total=requested_target,
                target_is_net=True,
            )

            breakdown_lines: list[str] = []
            breakdown_lines.append("✅ חישוב דטרמיניסטי:")
            breakdown_lines.append(f"- יעד חודשי מבוקש (נטו): {breakdown.desired_net_total:,.0f} ₪")
            if breakdown.other_income_offset_net > 0:
                breakdown_lines.append(
                    f"- קיזוז הכנסות נוספות (נטו): {breakdown.other_income_offset_net:,.0f} ₪"
                )
            breakdown_lines.append(f"- יעד קצבה לתכנית (נטו, אחרי קיזוז הכנסות נוספות): {breakdown.effective_plan_target:,.0f} ₪")
            yield "\n".join(breakdown_lines) + "\n\n"

            if breakdown.effective_plan_target <= 0:
                yield "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת."
                return

            tool_args = {
                "target_monthly_pension": float(requested_target),
                "target_is_net": True,
            }
            if inferred_age is not None:
                tool_args["retirement_age"] = int(inferred_age)

            policy_status, tool_args, policy_text = evaluate_blocked_balances_policy_for_build_target_plan(
                db=db,
                client_id=int(client_id),
                portfolio=effective_portfolio,
                plan_args=tool_args,
            )
            if isinstance(policy_text, str) and policy_text.strip():
                yield policy_text.strip() + "\n\n"
            if policy_status == "ask_current_employer_termination":
                return
            if policy_status in {
                "needs_termination_plan_confirmation",
                "needs_termination_plan_alternative",
            }:
                return
            if policy_status == "needs_termination_approval":
                termination_args = {"confirmed": True}
                try:
                    from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
                        load_current_employer_termination_plan_preview,
                    )

                    preview_payload = load_current_employer_termination_plan_preview(
                        db=db,
                        client_id=int(client_id),
                    )
                    if isinstance(preview_payload, dict):
                        template = preview_payload.get("termination_arguments_template")
                        approved = bool(preview_payload.get("approved")) is True
                        if approved and isinstance(template, dict) and template:
                            termination_args = dict(template)
                except Exception:
                    pass
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
                return

            tool_result = execute_tool_call(
                tool_name,
                tool_args,
                client_id,
                db,
                pension_portfolio=effective_portfolio,
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

        return StreamingResponse(
            _exec_target_plan_tools_first_from_phrase(),
            media_type="text/plain",
        )

    if client_id is not None:
        try:
            pending_age, pending_date = infer_pending_retirement_fields_for_marker(
                client_id=client_id
            )
            store_pending_plan_target_marker(
                db=db,
                client_id=client_id,
                ttl_seconds=5 * 60,
                source="stream_plan_phrase",
                pending_retirement_age=pending_age,
                pending_retirement_date=pending_date,
            )
        except Exception:
            pass

    def _prompt_for_target_net_for_phrase():
        yield sanitize_user_visible_text(
            "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
            "כתוב: יעד נטו: <מספר>."
        )

    return StreamingResponse(
        _prompt_for_target_net_for_phrase(),
        media_type="text/plain",
    )
