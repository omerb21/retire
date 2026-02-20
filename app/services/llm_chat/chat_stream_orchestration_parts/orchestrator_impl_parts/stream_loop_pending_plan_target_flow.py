import json
import re
from datetime import datetime, timezone

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.client import Client
from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    store_pending_approval_request,
)
from app.services.llm_chat.intent_classifier import ChatIntent
from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
    compute_effective_plan_target,
)
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    evaluate_blocked_balances_policy_for_build_target_plan,
)
from .stream_loop_pending_plan_target_store import (
    _clear_pending_plan_target,
    _load_pending_plan_target,
    _store_pending_plan_target,
)


def _maybe_handle_pending_plan_target_flow(
    *,
    request,
    db: Session,
    stream_request_id: str,
    computed_data,
    original_user_msg: str,
    resolved_intent,
    tools_enabled: bool,
    effective_portfolio,
    target_net_for_plan,
    lowered_user_msg: str,
    is_plan_request_tokens: bool,
    inferred_ret_age_for_plan_gate,
    wants_execute_target_plan_text: bool,
    commutation_intent_local: bool,
    explicit_transform_local: bool,
    max_capital_requested_local: bool,
    no_tools_requested_local: bool,
    is_qa_mode_local: bool,
    has_target_plan_keywords: bool,
    is_post_conversion_locked,
    infer_pending_retirement_fields_for_marker,
    infer_retirement_age_for_plan_args,
    build_recent_state_banner,
    load_latest_pension_portfolio_snapshot_models,
    pre_retirement_plan_resolution,
    execute_tool_call,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
    extract_target_net_ils,
 ) -> StreamingResponse | None:
    _PENDING_PLAN_TARGET_TTL_SECONDS = 5 * 60

    if (
        (resolved_intent != ChatIntent.REPORT)
        and (is_plan_request_tokens or (inferred_ret_age_for_plan_gate is not None))
        and (target_net_for_plan is None)
        and (not wants_execute_target_plan_text)
        and (not commutation_intent_local)
        and (not explicit_transform_local)
        and (not max_capital_requested_local)
    ):
        try:
            if request.client_id is not None:
                _store_pending_plan_target(
                    db=db,
                    client_id=request.client_id,
                    ttl_seconds=_PENDING_PLAN_TARGET_TTL_SECONDS,
                    infer_pending_retirement_fields_for_marker=infer_pending_retirement_fields_for_marker,
                )
        except Exception:
            pass

        def _prompt_for_target_net():
            yield (
                "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
                "כתוב: יעד נטו: <מספר>."
            )

        return StreamingResponse(
            _prompt_for_target_net(),
            media_type="text/plain",
        )

    pending_plan_target = None
    try:
        if request.client_id is not None:
            pending_plan_target = _load_pending_plan_target(db=db, client_id=request.client_id)
    except Exception:
        pending_plan_target = None

    def _extract_target_net_reply(user_msg: str) -> int | None:
        if not isinstance(user_msg, str) or not user_msg.strip():
            return None
        cleaned = user_msg.replace(",", "").replace(".", "").strip()
        if re.fullmatch(r"\d{4,6}", cleaned):
            try:
                return int(cleaned)
            except Exception:
                return None
        try:
            return extract_target_net_ils(user_msg)
        except Exception:
            return None

    target_net_reply = _extract_target_net_reply(original_user_msg or "")

    if (
        (resolved_intent != ChatIntent.REPORT)
        and request.client_id is not None
        and (target_net_reply is not None)
        and (pending_plan_target is not None)
        and (not bool(pending_plan_target.get("_expired")))
        and (not commutation_intent_local)
        and (not explicit_transform_local)
    ):

        def _generate_target_plan_tools_first_from_pending(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            banner = build_recent_state_banner()
            if banner:
                yield banner + "\n\n"

            portfolio_for_plan = effective_portfolio

            try:
                loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    portfolio_for_plan, _snapshot_at = loaded
            except Exception:
                pass

            requested_target = float(target_net_reply)
            breakdown = compute_effective_plan_target(
                db=db,
                client_id=int(request.client_id),
                desired_total=requested_target,
                target_is_net=True,
            )
            if breakdown.effective_plan_target <= 0:
                yield "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת."
                return

            plan_args = {
                "target_monthly_pension": float(requested_target),
                "target_is_net": True,
            }
            client_obj = None
            try:
                client_obj = db.query(Client).filter(Client.id == request.client_id).first()
            except Exception:
                client_obj = None
            inferred_age = infer_retirement_age_for_plan_args(
                client_obj=client_obj,
                pending_payload=pending_plan_target,
            )
            if inferred_age is not None and plan_args.get("retirement_age") is None:
                plan_args["retirement_age"] = int(inferred_age)

            policy_status, plan_args, policy_text = evaluate_blocked_balances_policy_for_build_target_plan(
                db=db,
                client_id=int(request.client_id),
                portfolio=portfolio_for_plan,
                plan_args=plan_args,
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
                        client_id=int(request.client_id),
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
                        client_id=int(request.client_id),
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

            breakdown_lines: list[str] = []
            breakdown_lines.append("✅ חישוב דטרמיניסטי:")
            breakdown_lines.append(f"- יעד חודשי מבוקש (נטו): {breakdown.desired_net_total:,.0f} ₪")
            if breakdown.other_income_offset_net > 0:
                breakdown_lines.append(
                    f"- קיזוז הכנסות נוספות (נטו): {breakdown.other_income_offset_net:,.0f} ₪"
                )
            breakdown_lines.append(
                f"- יעד קצבה לתכנית (נטו, אחרי קיזוז הכנסות נוספות): {breakdown.effective_plan_target:,.0f} ₪"
            )
            yield "\n".join(breakdown_lines) + "\n\n"

            plan_result = execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                plan_args,
                request.client_id,
                db,
                pension_portfolio=portfolio_for_plan,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            try:
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass

            try:
                _clear_pending_plan_target(db=db, client_id=request.client_id)
            except Exception:
                pass

            yield sanitize_user_visible_text(
                "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
            )

        return StreamingResponse(
            _generate_target_plan_tools_first_from_pending(stream_request_id),
            media_type="text/plain",
        )

    if (
        request.client_id is not None
        and pending_plan_target is not None
        and bool(pending_plan_target.get("_expired"))
        and (target_net_reply is not None)
    ):
        try:
            _store_pending_plan_target(
                db=db,
                client_id=request.client_id,
                ttl_seconds=_PENDING_PLAN_TARGET_TTL_SECONDS,
                infer_pending_retirement_fields_for_marker=infer_pending_retirement_fields_for_marker,
            )
        except Exception:
            pass

        def _prompt_for_target_net_again():
            yield (
                "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
                "כתוב: יעד נטו: <מספר>."
            )

        return StreamingResponse(
            _prompt_for_target_net_again(),
            media_type="text/plain",
        )

    if (
        tools_enabled
        and (resolved_intent != ChatIntent.REPORT)
        and request.client_id is not None
        and (not no_tools_requested_local)
        and (not is_qa_mode_local)
        and (target_net_for_plan is not None)
        and has_target_plan_keywords
    ):
        def _generate_target_plan_tools_first(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            banner = build_recent_state_banner()
            if banner:
                yield banner + "\n\n"

            portfolio_for_plan = effective_portfolio

            try:
                loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    portfolio_for_plan, _snapshot_at = loaded
            except Exception:
                pass

            requested_target = float(target_net_for_plan)
            breakdown = compute_effective_plan_target(
                db=db,
                client_id=int(request.client_id),
                desired_total=requested_target,
                target_is_net=True,
            )
            if breakdown.effective_plan_target <= 0:
                yield "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת."
                return

            plan_args = {
                "target_monthly_pension": float(requested_target),
                "target_is_net": True,
            }
            client_obj = None
            try:
                client_obj = db.query(Client).filter(Client.id == request.client_id).first()
            except Exception:
                client_obj = None
            inferred_age = infer_retirement_age_for_plan_args(
                client_obj=client_obj,
                pending_payload=None,
            )
            if inferred_age is not None and plan_args.get("retirement_age") is None:
                plan_args["retirement_age"] = int(inferred_age)

            policy_status, plan_args, policy_text = evaluate_blocked_balances_policy_for_build_target_plan(
                db=db,
                client_id=int(request.client_id),
                portfolio=portfolio_for_plan,
                plan_args=plan_args,
            )
            if isinstance(policy_text, str) and policy_text.strip():
                yield policy_text.strip() + "\n\n"
            if policy_status == "ask_current_employer_termination":
                return
            if policy_status == "needs_termination_approval":
                termination_args = {"confirmed": True}
                try:
                    store_pending_approval_request(
                        db=db,
                        client_id=int(request.client_id),
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

            breakdown_lines: list[str] = []
            breakdown_lines.append("✅ חישוב דטרמיניסטי:")
            breakdown_lines.append(f"- יעד חודשי מבוקש (נטו): {breakdown.desired_net_total:,.0f} ₪")
            if breakdown.other_income_offset_net > 0:
                breakdown_lines.append(
                    f"- קיזוז הכנסות נוספות (נטו): {breakdown.other_income_offset_net:,.0f} ₪"
                )
            breakdown_lines.append(
                f"- יעד קצבה לתכנית (נטו, אחרי קיזוז הכנסות נוספות): {breakdown.effective_plan_target:,.0f} ₪"
            )
            yield "\n".join(breakdown_lines) + "\n\n"

            plan_result = execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                plan_args,
                request.client_id,
                db,
                pension_portfolio=portfolio_for_plan,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )
            try:
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            yield sanitize_user_visible_text(
                "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
            )

        return StreamingResponse(
            _generate_target_plan_tools_first(stream_request_id),
            media_type="text/plain",
        )

    return None
