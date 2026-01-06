import json
from typing import Any

from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    build_forced_document_reply,
    build_pension_portfolio_update_after_transform,
    clear_pending_approval_request,
    format_transform_result_for_user,
    load_latest_target_pension_plan,
)
from app.services.llm_chat.message_utils import extract_latest_target_pension_plan_payload
from app.services.llm_chat.orchestration_utils import (
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
)

from .stream_top_level_helpers import (
    _build_transform_accounts_from_target_plan_payload,
    _store_pending_approval_request,
)
from .stream_tool_execution import _execute_tool_call


def generate_forced_approval(
    *,
    computed_data,
    explicit_termination,
    termination_already_executed,
    request,
    db,
    effective_portfolio,
    force_max_exemption,
    stream_request_id,
    wants_execute_target_plan,
    wants_fixation_execute,
) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    # If the user explicitly asked to execute termination and it wasn't done yet,
    # we must request approval BEFORE running.
    if explicit_termination and (not termination_already_executed):
        recent_user_text = "\n".join(
            [
                str(getattr(m, "content", ""))
                for m in (request.messages or [])
                if getattr(m, "role", None) == "user"
            ][-8:]
        )
        tool_args: dict[str, Any] = {"confirmed": True}
        tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
        termination_date_override = extract_process_termination_date_override(recent_user_text)
        if termination_date_override:
            tool_args["termination_date"] = termination_date_override

        tool_result = _execute_tool_call(
            "PROCESS_TERMINATION",
            tool_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=stream_request_id,
        )

        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

        out = sanitize_user_visible_text(
            format_tool_output_for_user_stream("PROCESS_TERMINATION", tool_result)
        )
        yield out
        return

    if wants_execute_target_plan:
        payload = extract_latest_target_pension_plan_payload(request.messages)
        if payload is None:
            payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
        if not isinstance(payload, dict):
            yield "\n\nלא נמצאה תכנית יעד אחרונה לביצוע. קודם צריך לבנות תכנית יעד קצבה ואז לבקש לבצע אותה בפועל."
            return

        accounts = _build_transform_accounts_from_target_plan_payload(payload)
        if not accounts:
            yield "\n\nלא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע אותה בפועל."
            return

        transform_args: dict[str, Any] = {
            "accounts": accounts,
            "use_provided_accounts_only": True,
            "ignore_blocked_balances": True,
            "skip_non_convertible_accounts": True,
        }

        try:
            _store_pending_approval_request(
                db=db,
                client_id=request.client_id,
                tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                tool_args=transform_args,
            )
        except Exception:
            pass

        yield build_approval_request_ui_action(
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=transform_args,
            reason="נדרש אישור לפני ביצוע המרות לפי תכנית היעד במערכת.",
            risk_level="high",
            rag_sources=None,
        )
        return

    if wants_fixation_execute:
        tool_args = {"save_result": True}

        tool_result = _execute_tool_call(
            "CALCULATE_FIXATION_OF_RIGHTS",
            tool_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=stream_request_id,
        )

        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

        out = sanitize_user_visible_text(
            format_tool_output_for_user_stream("CALCULATE_FIXATION_OF_RIGHTS", tool_result)
        )
        yield out


def generate_execute_target_after_termination(
    *,
    computed_data,
    request,
    db,
    effective_portfolio,
    force_max_exemption,
    stream_request_id,
) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    payload = extract_latest_target_pension_plan_payload(request.messages)
    if payload is None:
        payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
    if not isinstance(payload, dict):
        yield "עזיבת עבודה כבר בוצעה. לא נמצאה תכנית יעד אחרונה לביצוע. קודם צריך לבנות תכנית יעד קצבה ואז לבקש לבצע אותה."
        return

    accounts = _build_transform_accounts_from_target_plan_payload(payload)
    if not accounts:
        yield "עזיבת עבודה כבר בוצעה. לא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע."
        return

    transform_args = {
        "accounts": accounts,
        "use_provided_accounts_only": True,
        "ignore_blocked_balances": True,
        "skip_non_convertible_accounts": True,
    }
    transform_result = _execute_tool_call(
        "TRANSFORM_FUNDS_TO_ASSETS",
        transform_args,
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        user_approved=True,
        request_id=stream_request_id,
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
    if portfolio_update_marker:
        yield portfolio_update_marker
    yield sanitize_user_visible_text(
        format_tool_output_for_user_stream(
            "TRANSFORM_FUNDS_TO_ASSETS",
            transform_result,
        )
    )


def generate_approval_exec(
    *,
    computed_data,
    approved_tool_name,
    approved_tool_args,
    request,
    db,
    effective_portfolio,
    force_max_exemption,
    stream_request_id,
    is_portfolio_analysis,
) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    tool_result = _execute_tool_call(
        approved_tool_name,
        approved_tool_args,
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        user_approved=True,
        request_id=stream_request_id,
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
    if portfolio_update_marker:
        yield portfolio_update_marker

    forced_document_reply = build_forced_document_reply(
        tool_name=approved_tool_name,
        tool_result=tool_result,
    )
    if forced_document_reply:
        yield "\n\n" + sanitize_user_visible_text(forced_document_reply)
        return

    if approved_tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
        yield format_transform_result_for_user(tool_result=tool_result)
        return

    out = sanitize_user_visible_text(
        format_tool_output_for_user_stream(approved_tool_name, tool_result)
    )
    if is_portfolio_analysis and isinstance(out, str) and out.strip():
        if "הערכה" not in out and "הערכה גסה" not in out and "ראשונית" not in out:
            out = (
                "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                + out
            )
    yield out
