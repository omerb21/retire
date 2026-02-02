import re

from fastapi.responses import StreamingResponse

from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
    apply_income_offset_to_target,
    compute_existing_income_offset_monthly,
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
            existing_income_offset, effective_target = apply_income_offset_to_target(
                db,
                int(client_id),
                float(requested_target),
            )

            breakdown_lines: list[str] = []
            breakdown_lines.append("✅ חישוב דטרמיניסטי:")
            breakdown_lines.append(f"- יעד חודשי מבוקש (נטו): {float(requested_target):,.0f} ₪")
            breakdown_lines.append(
                f"- קיזוז הכנסות נוספות (נטו): {float(existing_income_offset):,.0f} ₪"
            )
            breakdown_lines.append(f"- יעד קצבה נדרש: {float(effective_target):,.0f} ₪")
            yield "\n".join(breakdown_lines) + "\n\n"

            if effective_target <= 0:
                yield "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת"
                return

            tool_args = {
                "target_monthly_pension": float(effective_target),
                "target_is_net": True,
            }
            if inferred_age is not None:
                tool_args["retirement_age"] = int(inferred_age)
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
            media_type="text/plain; charset=utf-8",
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
        media_type="text/plain; charset=utf-8",
    )
