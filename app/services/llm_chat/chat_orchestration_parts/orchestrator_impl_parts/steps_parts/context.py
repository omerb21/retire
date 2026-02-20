
import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatResponse
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text


from ..steps.messages_prompt import _build_messages_and_prompt
from ..steps.types import _PreparedOrchestrationInputs
from .context_post_deterministics import _handle_post_deterministics_and_finalize

def _prepare_orchestration_inputs(
    *,
    request,
    db,
    request_id: str,
    logger,
    log_llm_event_fn,
) -> _PreparedOrchestrationInputs | ChatResponse:
    import importlib

    from app.models.client import Client
    from app.models import CurrentEmployer, EmployerGrant, GrantType
    from app.services.llm_chat.chat_orchestration_parts.chat_helpers import (
        _digits_only,
        _extract_commutation_account_number,
        _fmt_money,
        _infer_target_is_net_explicit,
        _is_ignore_blocked_text,
        _is_target_plan_adjust_followup,
        _is_target_plan_adjust_request,
        _item_to_dict,
        _user_requested_target_pension_plan,
        _user_wants_full_balance,
    )
    from app.services.llm_chat.chat_orchestration_parts.tool_calling import _execute_tool_call
    from app.services.llm_chat.chat_orchestration_helpers import (
        build_approval_request_ui_action,
        build_forced_document_reply,
        build_pension_portfolio_update_after_transform,
        format_transform_result_for_user,
        build_transform_accounts_from_target_plan_payload,
        clear_pending_plan_target_marker,
        clear_pending_approval_request,
        execute_pending_approval_request,
        load_latest_target_pension_plan,
        load_pending_plan_target_marker,
        load_pending_approval_request,
        load_undo_snapshot,
        store_latest_target_pension_plan,
        store_latest_target_pension_plan_data,
        store_pending_approval_request,
        store_pending_plan_target_marker,
    )
    from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
    from app.services.llm_chat.message_utils import (
        extract_latest_approval_request,
        extract_latest_target_pension_plan_payload,
        extract_target_pension_from_message,
        extract_user_approval_for_tool_call,
        extract_user_cancel_for_tool_call,
        find_last_user_message,
        is_user_approval_intent_text,
        is_undo_intent_text,
    )
    from app.services.llm_chat.orchestration_utils import (
        build_partial_pension_transform_accounts_from_portfolio,
        build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
        build_portfolio_wide_component_transform_accounts_from_portfolio,
        build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
        build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
        build_transform_accounts_from_portfolio,
        build_targeted_component_transform_accounts_from_portfolio,
        compute_retirement_date_from_birth_date,
        extract_desired_monthly_income_from_text,
        extract_process_termination_choice_overrides,
        extract_process_termination_date_override,
        format_tool_output_for_user_stream,
        infer_desired_income_is_net_explicit,
        is_cashflow_missing_income_followup,
        is_data_awareness_request,
        is_document_request,
        is_list_all_financial_entities_request,
        is_max_capital_request,
        is_max_exemption_request,
        is_net_pension_request,
        is_no_termination_request,
        is_no_tools_request,
        is_pension_commutation_request,
        is_portfolio_analysis_request,
        is_portfolio_breakdown_request,
        is_process_termination_request,
        is_qa_request,
        is_retirement_cashflow_request,
        is_retirement_comparison_request,
        is_tax_documents_request,
        is_termination_change_request,
        is_transform_request,
        parse_partial_pension_conversion_request,
        parse_portfolio_wide_after_settlement_severance_conversion_request,
        parse_portfolio_wide_component_conversion_request,
        parse_portfolio_wide_education_fund_conversion_request,
        parse_portfolio_wide_prev_employers_severance_conversion_request,
        parse_targeted_component_conversion_request,
        resolve_target_retirement_age,
    )

    (
        effective_portfolio,
        effective_snapshot_at,
        messages,
        computed_data,
        original_user_msg,
    ) = _build_messages_and_prompt(request=request, db=db, logger=logger)

    from ..steps.prepare_inputs_parts.case_routing import _set_case_id_safe

    _set_case_id_safe(
        original_user_msg=original_user_msg,
        messages=messages,
        client_id=request.client_id,
    )

    tools_enabled = bool(getattr(request, "tools_enabled", True))

    if request.client_id is not None:
        last_user_text = find_last_user_message(request.messages)
        if is_user_approval_intent_text(last_user_text):
            executed = execute_pending_approval_request(
                db=db,
                client_id=request.client_id,
                execute_tool_call_fn=_execute_tool_call,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                request_id=request_id,
            )
            if executed is None:
                return ChatResponse(
                    reply=(
                        "לא נמצאה בקשת אישור פעילה לביצוע. "
                        "כדי לבצע פעולה במערכת צריך קודם לקבל בקשת אישור (כפתור אשר), "
                        "או לבקש שוב במפורש לבצע את הפעולה."
                    ),
                    computed_data=computed_data,
                )

            approved_tool_name, approved_tool_args, tool_result = executed
            portfolio_update_marker = build_pension_portfolio_update_after_transform(
                tool_name=approved_tool_name,
                tool_result=tool_result,
                tool_args=approved_tool_args if isinstance(approved_tool_args, dict) else {},
                current_pension_portfolio=effective_portfolio,
            )
            forced_document_reply = build_forced_document_reply(
                tool_name=approved_tool_name,
                tool_result=tool_result,
            )

            reply_text = forced_document_reply or tool_result
            if approved_tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
                reply_text = format_transform_result_for_user(tool_result=tool_result)
            else:
                reply_text = format_tool_output_for_user_stream(approved_tool_name, reply_text)
            if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
                reply_text = f"{portfolio_update_marker}{reply_text}"
            return ChatResponse(
                reply=sanitize_user_visible_text(reply_text),
                computed_data=computed_data,
            )

    if request.client_id is not None and is_undo_intent_text(original_user_msg):
        undo = None
        try:
            undo = load_undo_snapshot(db=db, client_id=request.client_id)
        except Exception:
            undo = None

        if undo is None:
            return ChatResponse(
                reply="לא נמצא מצב קודם לשחזור/ביטול. לא בוצע שינוי במערכת.",
                computed_data=computed_data,
            )

        undo_snapshot_id, _undo_payload = undo
        tool_args = {"snapshot_scenario_id": int(undo_snapshot_id)}
        ui_action = build_approval_request_ui_action(
            tool_name="RESTORE_SYSTEM_SNAPSHOT",
            tool_args=tool_args,
            reason="שחזור מצב קודם ידרוס שינויים אחרונים. נדרש אישור.",
            risk_level="high",
            rag_sources=None,
        )
        try:
            store_pending_approval_request(
                db=db,
                client_id=request.client_id,
                tool_name="RESTORE_SYSTEM_SNAPSHOT",
                tool_args=tool_args,
            )
        except Exception:
            pass
        return ChatResponse(reply=ui_action, computed_data=computed_data)

    pending_plan_target = None
    try:
        if request.client_id is not None:
            pending_plan_target = load_pending_plan_target_marker(
                db=db,
                client_id=request.client_id,
            )
    except Exception:
        pending_plan_target = None

    if (
        request.client_id is not None
        and (pending_plan_target is not None)
        and (not bool(pending_plan_target.get("_expired")))
    ):
        raw = (original_user_msg or "").strip()
        cleaned = raw.replace(",", "").replace(".", "").strip()

        target_net_val: int | None = None
        if cleaned.isdigit() and (4 <= len(cleaned) <= 6):
            try:
                target_net_val = int(cleaned)
            except Exception:
                target_net_val = None

        if target_net_val is None:
            lowered = raw.lower()
            if any(tok in lowered for tok in ("יעד", "נטו", "net")):
                try:
                    extracted = float(extract_target_pension_from_message(raw) or 0)
                except Exception:
                    extracted = 0.0
                if extracted > 0:
                    try:
                        target_net_val = int(extracted)
                    except Exception:
                        target_net_val = None

        if target_net_val is not None:
            plan_args = {
                "target_monthly_pension": float(target_net_val),
                "target_is_net": True,
            }

            pending_age = None
            if isinstance(pending_plan_target, dict):
                pending_age = pending_plan_target.get("pending_retirement_age")
            if pending_age is not None:
                try:
                    plan_args["retirement_age"] = int(pending_age)
                except Exception:
                    pass
            plan_result = _execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                plan_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=request_id,
            )

            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            try:
                clear_pending_plan_target_marker(db=db, client_id=request.client_id)
            except Exception:
                pass

            return ChatResponse(
                reply=(
                    "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                    + sanitize_user_visible_text(
                        format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                    )
                ),
                computed_data=computed_data,
            )

        # Marker active but reply not target-net: re-prompt and BLOCK other flows (incl cashflow)
        try:
            store_pending_plan_target_marker(
                db=db,
                client_id=request.client_id,
                ttl_seconds=300,
                source=str((pending_plan_target.get("_meta") or {}).get("source") or "pending_plan_target"),
                pending_retirement_age=(pending_plan_target.get("pending_retirement_age") if isinstance(pending_plan_target, dict) else None),
                pending_retirement_date=(pending_plan_target.get("pending_retirement_date") if isinstance(pending_plan_target, dict) else None),
            )
        except Exception:
            pass
        return ChatResponse(
            reply=(
                "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו.\n"
                "כתוב: יעד נטו: <מספר>."
            ),
            computed_data=computed_data,
        )

    if tools_enabled and request.client_id is not None and (
        _is_target_plan_adjust_request(original_user_msg)
        or _is_target_plan_adjust_followup(original_user_msg, request.messages)
    ):
        payload = extract_latest_target_pension_plan_payload(request.messages)
        if payload is None:
            payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
        if not isinstance(payload, dict):
            return ChatResponse(
                reply=(
                    "כדי לתקן את תכנית יעד הקצבה אני צריך תכנית יעד אחרונה קיימת. "
                    "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של <מספר>' (ואפשר לציין ברוטו/נטו)."
                ),
                computed_data=computed_data,
            )

        plan_res = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        raw_target = plan_res.get("target_monthly_pension")
        try:
            target_val = float(raw_target or 0)
        except Exception:
            target_val = 0.0

        explicit_is_net = _infer_target_is_net_explicit(original_user_msg)
        if explicit_is_net is None:
            prev_is_net = payload.get("args", {}).get("target_is_net") if isinstance(payload.get("args"), dict) else None
            prev_mode = "נטו" if prev_is_net is True else "ברוטו"
            return ChatResponse(
                reply=(
                    "כדי לתקן את התכנית צריך להבהיר: היעד שביקשת הוא **ברוטו** או **נטו**?\n\n"
                    f"(התכנית האחרונה נבנתה במצב: {prev_mode})\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '28000 ברוטו'\n"
                    "- '28000 נטו'"
                ),
                computed_data=computed_data,
            )

        if target_val <= 0:
            return ChatResponse(
                reply=(
                    "לא הצלחתי לקרוא את יעד הקצבה מתוך התכנית האחרונה. "
                    "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של 28000' (ברוטו/נטו)."
                ),
                computed_data=computed_data,
            )

        plan_args = {
            "target_monthly_pension": float(target_val),
            "target_is_net": bool(explicit_is_net),
        }

        resolved_ret_age, _src = resolve_target_retirement_age(
            original_user_msg,
            birth_date,
            date.today(),
            None,
        )
        if resolved_ret_age is not None:
            try:
                plan_args["retirement_age"] = int(resolved_ret_age)
            except Exception:
                pass
        plan_result = _execute_tool_call(
            "BUILD_TARGET_PENSION_PLAN",
            plan_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=request_id,
        )
        try:
            store_latest_target_pension_plan(db=db, client_id=request.client_id, tool_result=plan_result)
        except Exception:
            pass
        try:
            store_latest_target_pension_plan_data(db=db, client_id=request.client_id, tool_result=plan_result)
        except Exception:
            pass
        return ChatResponse(
            reply=(
                "🔧 **פלט כלי (בניית תכנית קצבה - תיקון):**\n"
                + sanitize_user_visible_text(
                    format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                )
            ),
            computed_data=computed_data,
        )

    from ..steps.prepare_inputs_parts.portfolio_breakdown import _maybe_handle_portfolio_breakdown

    if tools_enabled:
        handled_breakdown = _maybe_handle_portfolio_breakdown(
            original_user_msg=original_user_msg,
            effective_portfolio=effective_portfolio,
            effective_snapshot_at=effective_snapshot_at,
            computed_data=computed_data,
        )
        if handled_breakdown is not None:
            return handled_breakdown

    from ..steps.prepare_inputs_parts.data_awareness import _maybe_handle_data_awareness

    if tools_enabled:
        handled_data_awareness = _maybe_handle_data_awareness(
            request=request,
            db=db,
            request_id=request_id,
            original_user_msg=original_user_msg,
            effective_portfolio=effective_portfolio,
            effective_snapshot_at=effective_snapshot_at,
            computed_data=computed_data,
            _execute_tool_call=_execute_tool_call,
        )
        if handled_data_awareness is not None:
            return handled_data_awareness

    from ..steps.prepare_inputs_parts.system_results_report import _maybe_handle_system_results_report

    if tools_enabled:
        handled_system_results_report = _maybe_handle_system_results_report(
            request=request,
            db=db,
            request_id=request_id,
            original_user_msg=original_user_msg,
            effective_portfolio=effective_portfolio,
            computed_data=computed_data,
            _execute_tool_call=_execute_tool_call,
            sanitize_user_visible_text=sanitize_user_visible_text,
            format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        )
        if handled_system_results_report is not None:
            return handled_system_results_report

    # Deterministic handling for target pension plan requests (avoid LLM timeouts/temporary failures).
    explicit_target_plan_request = False
    wants_execute_target_plan_early = False
    try:
        lowered_tmp = (original_user_msg or "").lower()
        wants_execute_target_plan_early = (
            "בצע" in lowered_tmp
            and ("תכנית" in lowered_tmp or "תוכנית" in lowered_tmp or "מתווה" in lowered_tmp)
        )
        if ("תזרים" not in lowered_tmp) and ("cashflow" not in lowered_tmp):
            planning_keywords = (
                "יעד קצבה",
                "תכנית",
                "תוכנית",
                "מתווה",
                "בנה",
                "צור",
                "תכנן",
                "תכנון",
                "build_target_pension_plan",
            )
            if any(k in lowered_tmp for k in planning_keywords):
                extracted_target = float(extract_target_pension_from_message(original_user_msg) or 0)
                explicit_target_plan_request = extracted_target > 0
    except Exception:
        explicit_target_plan_request = False

    if (
        request.client_id is not None
        and explicit_target_plan_request
        and (not wants_execute_target_plan_early)
        and (not is_document_request(original_user_msg))
        and (not is_qa_request(original_user_msg))
        and (not is_no_tools_request(original_user_msg))
    ):

        target_val = 0.0
        try:
            target_val = float(extract_target_pension_from_message(original_user_msg) or 0)
        except Exception:
            target_val = 0.0
        if target_val <= 0:
            return ChatResponse(
                reply="כדי לבנות תכנית יעד קצבה אני צריך יעד חודשי מספרי (למשל: 28000).",
                computed_data=computed_data,
            )

        lowered = (original_user_msg or "").lower()
        explicit_is_net = None
        if any(t in lowered for t in ("ברוטו", "gross", "bruto")):
            explicit_is_net = False
        elif any(t in lowered for t in ("נטו", "ביד", "אחרי מס", "net")):
            explicit_is_net = True

        if explicit_is_net is None:
            return ChatResponse(
                reply=(
                    "כדי לבנות תכנית יעד קצבה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '28000 ברוטו'\n"
                    "- '28000 נטו'"
                ),
                computed_data=computed_data,
            )

        plan_args = {"target_monthly_pension": float(target_val), "target_is_net": bool(explicit_is_net)}

        resolved_ret_age, _src = resolve_target_retirement_age(
            original_user_msg,
            birth_date,
            date.today(),
            None,
        )
        if resolved_ret_age is not None:
            try:
                plan_args["retirement_age"] = int(resolved_ret_age)
            except Exception:
                pass
        plan_result = _execute_tool_call(
            "BUILD_TARGET_PENSION_PLAN",
            plan_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=request_id,
        )
        try:
            store_latest_target_pension_plan(db=db, client_id=request.client_id, tool_result=plan_result)
        except Exception:
            pass
        try:
            store_latest_target_pension_plan_data(db=db, client_id=request.client_id, tool_result=plan_result)
        except Exception:
            pass
        return ChatResponse(
            reply=(
                "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                + sanitize_user_visible_text(
                    format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                )
            ),
            computed_data=computed_data,
        )

    from ..steps.prepare_inputs_parts.list_all_entities import (
        _maybe_handle_list_all_financial_entities,
    )

    handled_list_all = _maybe_handle_list_all_financial_entities(
        request=request,
        db=db,
        request_id=request_id,
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        effective_snapshot_at=effective_snapshot_at,
        computed_data=computed_data,
        _execute_tool_call=_execute_tool_call,
        _fmt_money=_fmt_money,
    )
    if handled_list_all is not None:
        return handled_list_all

    is_doc_request = is_document_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = is_no_tools_request(original_user_msg) or (not tools_enabled)
    force_max_exemption = is_max_exemption_request(original_user_msg)
    is_net_request = is_net_pension_request(original_user_msg)
    is_cashflow_request = is_retirement_cashflow_request(original_user_msg)
    is_comparison_request = is_retirement_comparison_request(original_user_msg)
    commutation_intent = is_pension_commutation_request(original_user_msg)
    explicit_transform = (not commutation_intent) and is_transform_request(original_user_msg)
    explicit_termination = is_process_termination_request(original_user_msg)
    termination_change = is_termination_change_request(original_user_msg)
    is_portfolio_analysis = is_portfolio_analysis_request(original_user_msg)

    lowered_user_msg = (original_user_msg or "").lower()
    wants_capital_transform = (
        (
            ("להון" in lowered_user_msg)
            or ("to capital" in lowered_user_msg)
            or ("הונית" in lowered_user_msg)
            or ("הוני" in lowered_user_msg)
            or ("מקסימום הון" in lowered_user_msg)
        )
        and ("המר" in lowered_user_msg or "המרה" in lowered_user_msg or "convert" in lowered_user_msg or "משיכה" in lowered_user_msg or "משוך" in lowered_user_msg)
    )
    wants_execute_target_plan = (
        "בצע" in lowered_user_msg
        and ("תכנית" in lowered_user_msg or "תוכנית" in lowered_user_msg or "מתווה" in lowered_user_msg)
    )
    wants_fixation_execute = (
        "בצע" in lowered_user_msg
        and ("קיבוע" in lowered_user_msg)
        and ("זכויות" in lowered_user_msg)
    )

    max_capital_request = is_max_capital_request(original_user_msg)
    wants_execute_max_capital = max_capital_request and ("בצע" in lowered_user_msg)

    explicit_cashflow_request = ("תזרים" in lowered_user_msg) or ("cashflow" in lowered_user_msg)
    wants_cashflow_refresh = is_cashflow_missing_income_followup(original_user_msg)

    if commutation_intent and request.client_id is not None:
        account_number = _extract_commutation_account_number(original_user_msg)
        if not account_number:
            return ChatResponse(
                reply=(
                    "כדי לחשב היוון בצורה נכונה אני צריך לזהות *איזו קצבה* אתה רוצה להוון. "
                    "בבקשה ציין אחד מהבאים:\n"
                    "- מספר חשבון/תיק ניכויים של הקצבה\n"
                    "- שם הקצבה כפי שמופיע במסך הקצבאות\n\n"
                    "בנוסף: האם הכוונה היא ל*סכום חד-פעמי* שתרצה לקבל, או ל*הפחתה חודשית מהקצבה*?"
                ),
                computed_data=computed_data,
            )

    if (
        (explicit_cashflow_request or wants_cashflow_refresh)
        and request.client_id is not None
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
        and (not commutation_intent)
    ):
        plan_payload = None
        try:
            plan_payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
        except Exception:
            plan_payload = None
        if plan_payload is None:
            try:
                plan_payload = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)
            except Exception:
                plan_payload = None
        if not isinstance(plan_payload, dict):
            return ChatResponse(
                reply="אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה.",
                computed_data=computed_data,
            )

        desired_income = extract_desired_monthly_income_from_text(original_user_msg)
        desired_income_is_net = infer_desired_income_is_net_explicit(original_user_msg)
        if desired_income is not None and desired_income_is_net is None:
            return ChatResponse(
                reply=(
                    "כדי לבנות תזרים לפי יעד הכנסה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '40 אלף ברוטו'\n"
                    "- '40 אלף נטו'"
                ),
                computed_data=computed_data,
            )

        if desired_income is None:
            return ChatResponse(
                reply=(
                    "כדי לחשב תזרים פרישה אני צריך יעד הכנסה חודשי מפורש (ברוטו או נטו).\n\n"
                    "דוגמאות להעתקה:\n"
                    "יעד נטו: <מספר>\n"
                    "יעד ברוטו: <מספר>\n\n"
                    "דוגמאות מלאות:\n"
                    "יעד נטו: 28000\n"
                    "יעד ברוטו: 31000"
                ),
                computed_data=computed_data,
            )

        explicit_gender, explicit_age = extract_explicit_gender_and_age_from_text(original_user_msg)

        client = None
        try:
            client = db.query(Client).filter(Client.id == request.client_id).first()
        except Exception:
            client = None

        birth_date = getattr(client, "birth_date", None) if client else None
        try:
            from datetime import date

            if birth_date == date(1970, 1, 1):
                birth_date = None
        except Exception:
            birth_date = None
        db_gender = getattr(client, "gender", None) if client else None

        gender_final = explicit_gender or (str(db_gender).strip() if db_gender is not None else None)

        retirement_date = extract_explicit_retirement_date_from_text(original_user_msg)
        resolved_ret_age, _src = resolve_target_retirement_age(
            original_user_msg,
            birth_date,
            date.today(),
            None,
        )
        if (not retirement_date) and (resolved_ret_age is not None) and birth_date:
            try:
                retirement_date = compute_retirement_date_from_birth_date(
                    birth_date,
                    int(resolved_ret_age),
                ).isoformat()
            except Exception:
                retirement_date = retirement_date

        age_final = int(resolved_ret_age) if resolved_ret_age is not None else explicit_age
        if age_final is None and birth_date and retirement_date:
            try:
                from datetime import datetime

                target_date = datetime.strptime(retirement_date, "%Y-%m-%d").date()
                age_years = target_date.year - birth_date.year
                if (target_date.month, target_date.day) < (birth_date.month, birth_date.day):
                    age_years -= 1
                age_final = int(age_years)
            except Exception:
                age_final = None

        if (not retirement_date) or (gender_final is None) or (age_final is None):
            return ChatResponse(
                reply="כדי לחשב צריך לציין מין וגיל",
                computed_data=computed_data,
            )

        tool_args: dict[str, Any] = {
            "retirement_date": retirement_date,
            "desired_monthly_income": float(desired_income),
            "age": int(age_final),
            "gender": gender_final,
        }
        if desired_income_is_net is not None:
            tool_args["desired_income_is_net"] = bool(desired_income_is_net)

        tool_result = _execute_tool_call(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            tool_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=request_id,
        )
        try:
            parsed = json.loads(tool_result) if isinstance(tool_result, str) else {}
        except Exception:
            parsed = {}
        explanation = parsed.get("explanation") if isinstance(parsed, dict) else None
        return ChatResponse(
            reply=sanitize_user_visible_text(
                explanation.strip()
                if isinstance(explanation, str) and explanation.strip()
                else format_tool_output_for_user_stream("RUN_RETIREMENT_CASHFLOW_ANALYSIS", tool_result)
            ),
            computed_data=computed_data,
        )

    if (
        request.client_id is not None
        and max_capital_request
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
    ):
        retirement_age = None
        try:
            client = db.query(Client).filter(Client.id == request.client_id).first()
            client_age = client.get_age() if client and hasattr(client, "get_age") else None
            from app.services.retirement_age_service import (
                DEFAULT_MALE_RETIREMENT_AGE,
                get_retirement_age_simple,
            )

            legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)
            try:
                if client and getattr(client, "birth_date", None) and getattr(client, "gender", None):
                    legal_ret_age = int(get_retirement_age_simple(client.birth_date, client.gender))
            except Exception:
                legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

            retirement_age = max(int(legal_ret_age), int(client_age or legal_ret_age))
        except Exception:
            retirement_age = 67

        scenarios_raw = _execute_tool_call(
            "RUN_RETIREMENT_SCENARIOS",
            {"retirement_age": int(retirement_age)},
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=request_id,
        )
        try:
            parsed = json.loads(scenarios_raw) if scenarios_raw else {}
        except Exception:
            parsed = {}

        scenario_id = None
        for row in (parsed.get("scenarios") if isinstance(parsed, dict) else []) or []:
            if isinstance(row, dict) and row.get("scenario_key") == "scenario_2_max_capital":
                scenario_id = row.get("scenario_id")
                break

        if scenario_id is None:
            return ChatResponse(
                reply="לא הצלחתי ליצור תרחיש 'מקסימום הון' במערכת.",
                computed_data=computed_data,
            )

        if wants_execute_max_capital:
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="EXECUTE_RETIREMENT_SCENARIO",
                    tool_args={"scenario_id": int(scenario_id)},
                )
            except Exception:
                pass

            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="EXECUTE_RETIREMENT_SCENARIO",
                    tool_args={"scenario_id": int(scenario_id)},
                    reason=(
                        "בקשת 'משיכה הונית מלאה' מחייבת שמירת קצבת מינימום 5,500 ₪. "
                        "אצור ואבצע את תרחיש 'מקסימום הון' (שמשאיר קצבת מינימום) רק לאחר אישור."
                    ),
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

        return ChatResponse(
            reply=(
                "יצרתי תרחיש 'מקסימום הון' (עם שמירת קצבת מינימום 5,500 ₪). "
                "אם תרצה לבצע אותו בפועל במערכת, כתוב: 'בצע'."
            ),
            computed_data=computed_data,
        )

    # Early deterministic handling for pension commutation requests.
    # Only run this path when the user provided a specific account identifier.
    # If the request is vague (no account number), fall back to the LLM flow.
    if commutation_intent and request.client_id is not None and (not is_doc_request) and (not is_qa_mode):
        account_number = _extract_commutation_account_number(original_user_msg)
        if account_number:
            # NOTE: We deliberately do not handle vague commutation requests deterministically.
            # If no account number is provided, fall back to the LLM loop.

            fund = None
            try:
                from app.models.pension_fund import PensionFund

                fund = (
                    db.query(PensionFund)
                    .filter(PensionFund.client_id == request.client_id)
                    .filter(PensionFund.deduction_file == account_number)
                    .first()
                )
            except Exception:
                fund = None

            if fund is None:
                target_digits = _digits_only(account_number)
                matched: dict | None = None
                for acc in (effective_portfolio or []):
                    data = _item_to_dict(acc)
                    acc_num = str(
                        data.get("מספר_חשבון")
                        or data.get("account_number")
                        or ""
                    ).strip()
                    if not acc_num:
                        continue
                    if acc_num == account_number:
                        matched = data
                        break
                    if target_digits and _digits_only(acc_num) == target_digits:
                        matched = data
                        break

                if fund is None:
                    return ChatResponse(
                        reply=(
                            "כדי לבצע היוון אני צריך לזהות **קצבה קיימת במערכת** שמתאימה לחשבון שביקשת. "
                            f"לא מצאתי קצבה עם מספר חשבון/תיק ניכויים `{account_number}`.\n\n"
                            "אפשרויות:\n"
                            "1) כתוב את שם הקצבה כפי שהיא מופיעה במסך קצבאות, או את מזהה הקצבה (pension_fund_id).\n"
                            "2) אם הכוונה היא לתכנית בתיק המסלקה בלבד (לא קצבה קיימת), ציין: 'הפוך את החשבון לקצבה ואז בצע היוון'."
                        ),
                        computed_data=computed_data,
                    )

            comm_amount = None
            try:
                if _user_wants_full_balance(original_user_msg):
                    comm_amount = float(getattr(fund, "balance", 0) or 0)
            except Exception:
                comm_amount = None

            if not comm_amount or comm_amount <= 0:
                return ChatResponse(
                    reply=(
                        "מצאתי את הקצבה המתאימה, אבל חסר לי סכום היוון. "
                        "כתוב סכום (למשל 50000 ₪) או 'כל היתרה'."
                    ),
                    computed_data=computed_data,
                )

            from datetime import date

            tax_type = "exempt" if "פטור" in (original_user_msg or "") else "taxable"
            exec_args = {
                "pension_fund_id": int(getattr(fund, "id")),
                "commutation_amount": float(comm_amount),
                "commutation_date": date.today().isoformat(),
                "commutation_type": tax_type,
                "confirmed": True,
            }

            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="EXECUTE_PENSION_COMMUTATION",
                    tool_args=exec_args,
                )
            except Exception:
                pass

            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="EXECUTE_PENSION_COMMUTATION",
                    tool_args=exec_args,
                    reason="נדרש אישור לפני ביצוע היוון קצבה במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

    return _handle_post_deterministics_and_finalize(
        request=request,
        db=db,
        request_id=request_id,
        logger=logger,
        log_llm_event_fn=log_llm_event_fn,
        effective_portfolio=effective_portfolio,
        computed_data=computed_data,
        original_user_msg=original_user_msg,
        messages=messages,
        force_max_exemption=force_max_exemption,
        is_portfolio_analysis=is_portfolio_analysis,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        no_tools_requested=no_tools_requested,
        is_cashflow_request=is_cashflow_request,
        is_comparison_request=is_comparison_request,
        is_net_request=is_net_request,
        commutation_intent=commutation_intent,
        explicit_transform=explicit_transform,
        explicit_termination=explicit_termination,
        termination_change=termination_change,
        wants_execute_target_plan=wants_execute_target_plan,
        wants_fixation_execute=wants_fixation_execute,
        wants_capital_transform=wants_capital_transform,
        max_capital_request=max_capital_request,
        wants_execute_max_capital=wants_execute_max_capital,
        explicit_cashflow_request=explicit_cashflow_request,
        wants_cashflow_refresh=wants_cashflow_refresh,
    )


