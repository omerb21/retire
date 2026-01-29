import json
from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatResponse
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text
from app.guards.tool_intent_guard import is_conceptual_no_execute_request

from ..steps.types import _PreparedOrchestrationInputs


def _handle_post_deterministics_and_finalize(
    *,
    request,
    db,
    request_id: str,
    logger,
    log_llm_event_fn,
    effective_portfolio,
    computed_data,
    original_user_msg,
    messages,
    force_max_exemption: bool,
    is_portfolio_analysis: bool,
    is_doc_request: bool,
    is_qa_mode: bool,
    no_tools_requested: bool,
    is_cashflow_request: bool,
    is_comparison_request: bool,
    is_net_request: bool,
    commutation_intent: bool,
    explicit_transform: bool,
    explicit_termination: bool,
    termination_change: bool,
    wants_execute_target_plan: bool,
    wants_fixation_execute: bool,
    wants_capital_transform: bool,
    max_capital_request: bool,
    wants_execute_max_capital: bool,
    explicit_cashflow_request: bool,
    wants_cashflow_refresh: bool,
) -> _PreparedOrchestrationInputs | ChatResponse:
    from app.models.client import Client
    from app.models import CurrentEmployer, EmployerGrant, GrantType
    from app.services.llm_chat.chat_orchestration_parts.chat_helpers import (
        _digits_only,
        _extract_commutation_account_number,
        _is_ignore_blocked_text,
        _item_to_dict,
        _user_wants_full_balance,
    )
    from app.services.llm_chat.chat_orchestration_parts.tool_calling import _execute_tool_call
    from app.services.llm_chat.chat_orchestration_helpers import (
        build_approval_request_ui_action,
        build_forced_document_reply,
        build_pension_portfolio_update_after_transform,
        format_transform_result_for_user,
        build_transform_accounts_from_target_plan_payload,
        clear_pending_approval_request,
        load_latest_target_pension_plan,
        load_latest_target_pension_plan_data,
        load_pending_approval_request,
        store_pending_approval_request,
        store_pending_plan_target_marker,
    )
    from app.services.llm_chat.message_utils import (
        extract_latest_approval_request,
        extract_latest_target_pension_plan_payload,
        extract_user_approval_for_tool_call,
        extract_user_cancel_for_tool_call,
        find_last_user_message,
        is_user_approval_intent_text,
    )
    from app.services.llm_chat.orchestration_utils import (
        compute_default_retirement_date_for_tool_call,
        extract_desired_monthly_income_from_text,
        extract_process_termination_choice_overrides,
        extract_process_termination_date_override,
        format_tool_output_for_user_stream,
        infer_desired_income_is_net_explicit,
        is_cashflow_missing_income_followup,
        is_no_termination_request,
    )

    forced_termination_result: str | None = None

    analysis_default_retirement_age: int | None = None
    if is_portfolio_analysis and request.client_id is not None:
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

            analysis_default_retirement_age = max(int(legal_ret_age), int(client_age or legal_ret_age))
        except Exception:
            analysis_default_retirement_age = None

    termination_already_executed = False
    if request.client_id is not None:
        current_employer = (
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == request.client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )
        if current_employer is not None and current_employer.end_date is not None:
            grants_count = (
                db.query(EmployerGrant)
                .filter(
                    EmployerGrant.employer_id == current_employer.id,
                    EmployerGrant.grant_type == GrantType.severance,
                )
                .count()
            )
            confirmed = False
            try:
                other_grants = current_employer.other_grants or {}
                if isinstance(other_grants, dict):
                    confirmed = bool(other_grants.get("termination_confirmed"))
            except Exception:
                confirmed = False
            termination_already_executed = confirmed or (grants_count > 0)

    if (
        explicit_termination
        and request.client_id is not None
        and (not is_qa_mode)
        and is_conceptual_no_execute_request(original_user_msg)
    ):
        return ChatResponse(
            reply=(
                "כותרת: עזיבת עבודה – הסבר עקרוני (ללא ביצוע)\n\n"
                "לא נעשתה פעולה במערכת.\n\n"
                "מה בודקים ומחליטים בעזיבת עבודה (עקרונית):\n"
                "- תאריך סיום עבודה\n"
                "- סכום פיצויים והפרדה לפטור/חייב\n"
                "- בחירת טיפול בפיצויים: רצף קצבה / משיכה / שילוב\n"
            ),
            computed_data=computed_data,
        )

    if (
        explicit_termination
        and request.client_id is not None
        and (not no_tools_requested)
        and (not is_qa_mode)
    ):
        recent_user_text = "\n".join(
            [
                str(getattr(m, "content", ""))
                for m in (request.messages or [])
                if getattr(m, "role", None) == "user"
            ][-8:]
        )
        tool_args: dict[str, Any] = {
            "confirmed": True,
        }
        tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
        termination_date_override = extract_process_termination_date_override(recent_user_text)
        if termination_date_override:
            tool_args["termination_date"] = termination_date_override

        if not termination_already_executed:
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="PROCESS_TERMINATION",
                    tool_args=tool_args,
                )
            except Exception:
                pass
            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="PROCESS_TERMINATION",
                    tool_args=tool_args,
                    reason="נדרש אישור לפני ביצוע עזיבת עבודה במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

        forced_termination_result = None

    if (
        request.client_id is not None
        and (not no_tools_requested)
        and (not is_qa_mode)
        and (wants_execute_target_plan or wants_fixation_execute)
    ):
        if wants_execute_target_plan:
            payload = extract_latest_target_pension_plan_payload(request.messages)
            if payload is None:
                payload = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)
            if payload is None:
                payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
            if not isinstance(payload, dict):
                try:
                    store_pending_plan_target_marker(
                        db=db,
                        client_id=request.client_id,
                        ttl_seconds=300,
                        source="execute_target_plan_prompt",
                    )
                except Exception:
                    pass
                return ChatResponse(
                    reply=(
                        "כדי לבצע תכנית בפועל צריך קודם לבנות תכנית יעד עם מספר.\n"
                        "כתוב: יעד נטו: <מספר>.\n"
                        "לדוגמה: יעד נטו: 28000"
                    ),
                    computed_data=computed_data,
                )

            result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            execution_plan = result.get("execution_plan") if isinstance(result.get("execution_plan"), dict) else None

            ignore_blocked_balances_val = True
            try:
                args_payload = payload.get("args") if isinstance(payload.get("args"), dict) else {}
                raw_ignore = args_payload.get("ignore_blocked_balances")
                if raw_ignore is not None:
                    ignore_blocked_balances_val = bool(raw_ignore)
            except Exception:
                ignore_blocked_balances_val = True

            transform_args: dict[str, Any] = {
                "use_provided_accounts_only": True,
                "ignore_blocked_balances": bool(ignore_blocked_balances_val),
                "skip_non_convertible_accounts": True,
            }

            if execution_plan is not None:
                transform_args["execution_plan"] = execution_plan
                raw_accounts = execution_plan.get("accounts") if isinstance(execution_plan, dict) else None
                transform_args["accounts"] = raw_accounts if isinstance(raw_accounts, list) else []
            else:
                accounts = build_transform_accounts_from_target_plan_payload(payload)
                if not accounts:
                    return ChatResponse(
                        reply="לא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע אותה בפועל.",
                        computed_data=computed_data,
                    )
                transform_args["accounts"] = accounts
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    tool_args=transform_args,
                )
            except Exception:
                pass
            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    tool_args=transform_args,
                    reason="נדרש אישור לפני ביצוע המרות לפי תכנית היעד במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

        if wants_fixation_execute:
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="CALCULATE_FIXATION_OF_RIGHTS",
                    tool_args={"save_result": True},
                )
            except Exception:
                pass
            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="CALCULATE_FIXATION_OF_RIGHTS",
                    tool_args={"save_result": True},
                    reason="נדרש אישור לפני ביצוע קיבוע זכויות במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

    approval = extract_user_approval_for_tool_call(request.messages)
    cancelled = extract_user_cancel_for_tool_call(request.messages)

    if approval is None and request.client_id is not None and (not no_tools_requested):
        last_user_text = find_last_user_message(request.messages)
        if is_user_approval_intent_text(last_user_text):
            pending = extract_latest_approval_request(request.messages)
            if pending is not None:
                approval = pending
            else:
                try:
                    pending_db = load_pending_approval_request(
                        db=db,
                        client_id=request.client_id,
                    )
                except Exception:
                    pending_db = None
                if pending_db is not None:
                    approval = pending_db

            if approval is None:
                raw = (last_user_text or "").strip().lower()
                if raw in {
                    "אשר",
                    "מאשר",
                    "אני מאשר",
                    "מאשרת",
                    "אני מאשרת",
                    "approve",
                    "approved",
                    "ok",
                    "כן",
                }:
                    return ChatResponse(
                        reply=(
                            "לא נמצאה בקשת אישור פעילה לביצוע. "
                            "כדי לבצע פעולה במערכת צריך קודם לקבל בקשת אישור (כפתור אשר), "
                            "או לבקש שוב במפורש לבצע את הפעולה."
                        ),
                        computed_data=computed_data,
                    )
    if (
        approval
        and request.client_id is not None
        and (not no_tools_requested)
        and (not explicit_transform)
    ):
        approved_tool_name, approved_tool_args = approval

        if (
            approved_tool_name == "PROCESS_TERMINATION"
            and termination_already_executed
            and (not termination_change)
            and wants_execute_target_plan
        ):
            payload = extract_latest_target_pension_plan_payload(request.messages)
            if payload is None:
                payload = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)
            if payload is None:
                payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
            if not isinstance(payload, dict):
                return ChatResponse(
                    reply=(
                        "עזיבת עבודה כבר בוצעה. "
                        "לא נמצאה תכנית יעד אחרונה לביצוע. קודם צריכה להיבנות תכנית יעד קצבה ואז לבקש לבצע אותה."
                    ),
                    computed_data=computed_data,
                )

            result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            execution_plan = (
                result.get("execution_plan")
                if isinstance(result.get("execution_plan"), dict)
                else None
            )
            ignore_blocked_balances_val = True
            try:
                args_payload = payload.get("args") if isinstance(payload.get("args"), dict) else {}
                raw_ignore = args_payload.get("ignore_blocked_balances")
                if raw_ignore is not None:
                    ignore_blocked_balances_val = bool(raw_ignore)
            except Exception:
                ignore_blocked_balances_val = True

            transform_args = {
                "use_provided_accounts_only": True,
                "ignore_blocked_balances": bool(ignore_blocked_balances_val),
                "skip_non_convertible_accounts": True,
            }
            if execution_plan is not None:
                transform_args["execution_plan"] = execution_plan
                transform_args["accounts"] = []
            else:
                accounts = build_transform_accounts_from_target_plan_payload(payload)
                if not accounts:
                    return ChatResponse(
                        reply=(
                            "עזיבת עבודה כבר בוצעה. "
                            "לא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע."
                        ),
                        computed_data=computed_data,
                    )
                transform_args["accounts"] = accounts
            transform_result = _execute_tool_call(
                "TRANSFORM_FUNDS_TO_ASSETS",
                transform_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=True,
                request_id=request_id,
            )

            try:
                clear_pending_approval_request(db=db, client_id=request.client_id)
            except Exception:
                pass

            portfolio_update_marker = build_pension_portfolio_update_after_transform(
                tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                tool_result=transform_result,
                tool_args=transform_args,
                current_pension_portfolio=effective_portfolio,
            )

            reply_text = format_transform_result_for_user(tool_result=transform_result)
            if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
                reply_text = f"{portfolio_update_marker}{reply_text}"
            return ChatResponse(
                reply=sanitize_user_visible_text(reply_text),
                computed_data=computed_data,
            )

        if approved_tool_name == "PROCESS_TERMINATION":
            overrides = extract_process_termination_choice_overrides(original_user_msg)
            if overrides and isinstance(approved_tool_args, dict):
                approved_tool_args = dict(approved_tool_args)
                approved_tool_args.update(overrides)
        tool_result = _execute_tool_call(
            approved_tool_name,
            approved_tool_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=request_id,
        )

        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

        portfolio_update_marker = build_pension_portfolio_update_after_transform(
            tool_name=approved_tool_name,
            tool_result=tool_result,
            tool_args=approved_tool_args,
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

        sanitized = sanitize_user_visible_text(reply_text)
        if is_portfolio_analysis and isinstance(sanitized, str) and sanitized.strip():
            if "הערכה" not in sanitized and "הערכה גסה" not in sanitized and "ראשונית" not in sanitized:
                sanitized = (
                    "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                    + sanitized
                )

        return ChatResponse(reply=sanitized, computed_data=computed_data)

    if cancelled and request.client_id is not None and (not no_tools_requested):
        cancelled_tool_name, _cancelled_tool_args = cancelled
        return ChatResponse(
            reply=f"בוצעה ביטול להפעלת הכלי: {cancelled_tool_name}. לא בוצע שינוי במערכת.",
            computed_data=computed_data,
        )

    wants_ignore_blocked = any(
        _is_ignore_blocked_text(getattr(m, "content", ""))
        for m in (request.messages or [])
        if getattr(m, "role", None) == "user"
    )

    wants_ignore_blocked = wants_ignore_blocked or any(
        is_no_termination_request(getattr(m, "content", ""))
        for m in (request.messages or [])
        if getattr(m, "role", None) == "user"
    )

    if wants_ignore_blocked:
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    "המשתמש אישר להתעלם מיתרות חסומות/יתרות לטיפול במסך עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                    "אל תשאל שוב לאישור על זה. אל תבצע עזיבת עבודה בשיחה זו, והמשך עם שאר הכלים הרלוונטיים בלבד."
                ),
            )
        )

    if is_portfolio_analysis:
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    "הנחיה: המשתמש ביקש ניתוח תיק. חובה להחזיר ניתוח מיד (Advisory Mode). "
                    "אסור לבצע אימות/בדיקת חוקיות של סכום הפיצויים מול נוסחה או מול 'חובת מעסיק'. "
                    "ברירת מחדל: אסור לפרט מדרגות מס. חריג: אם המשתמש ביקש פרמטרים/מדרגות/תקרות והרצת GET_TAX_PARAMS — מותר לצטט מספרים רק מתוך תוצאת הכלי. "
                    "כאשר אתה מדבר עם המשתמש על הפעולה, השתמש במונח 'עזיבת עבודה' בלבד. "
                    "אם מציגים תרחישים אוטומטיים: הם הערכה גסה/ראשונית בלבד, והצג אותם כ'תרחיש 1/2/3'."
                ),
            )
        )

    current_pension_portfolio = effective_portfolio

    from .context_explicit_transform import _maybe_handle_explicit_transform

    handled = _maybe_handle_explicit_transform(
        request=request,
        db=db,
        request_id=request_id,
        logger=logger,
        log_llm_event_fn=log_llm_event_fn,
        original_user_msg=original_user_msg,
        current_pension_portfolio=current_pension_portfolio,
        computed_data=computed_data,
        messages=messages,
        explicit_transform=explicit_transform,
        no_tools_requested=no_tools_requested,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        wants_ignore_blocked=wants_ignore_blocked,
        wants_capital_transform=wants_capital_transform,
    )
    if handled is not None:
        return handled

    log_llm_event_fn(
        request_id=request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
    )

    return _PreparedOrchestrationInputs(
        messages=messages,
        original_user_msg=original_user_msg,
        current_pension_portfolio=current_pension_portfolio,
        computed_data=computed_data,
        is_qa_mode=is_qa_mode,
        no_tools_requested=no_tools_requested,
        is_doc_request=is_doc_request,
        is_cashflow_request=is_cashflow_request,
        is_comparison_request=is_comparison_request,
        is_net_request=is_net_request,
        is_portfolio_analysis=is_portfolio_analysis,
        analysis_default_retirement_age=analysis_default_retirement_age,
        force_max_exemption=force_max_exemption,
        wants_ignore_blocked=wants_ignore_blocked,
        explicit_termination=explicit_termination,
        termination_change=termination_change,
        termination_already_executed=termination_already_executed,
        wants_execute_target_plan=wants_execute_target_plan,
        wants_fixation_execute=wants_fixation_execute,
    )
