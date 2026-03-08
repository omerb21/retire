import json

from fastapi.responses import StreamingResponse

from app.services.llm_chat.chat_orchestration_helpers import (
    clear_pending_approval_request,
    load_pending_approval_request,
)
from app.services.llm_chat.chat_orchestration_helpers_parts.scenario_storage import (
    clear_execution_veto,
    load_execution_veto,
    store_execution_veto,
)
from app.services.llm_chat.message_utils import (
    extract_latest_approval_request,
    extract_user_approval_for_tool_call,
    extract_user_cancel_for_tool_call,
    find_last_user_message,
    is_user_approval_intent_text,
)
from app.services.llm_chat.orchestration_utils import (
    extract_process_termination_choice_overrides,
    sanitize_user_visible_text,
)
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    clear_pending_build_target_plan_after_termination,
)
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    decide_stream_planning_execution_policy,
    is_explicit_execution_veto_turn,
    should_clear_execution_veto_for_current_turn,
)

from ..stream_approval_generators import (
    generate_approval_exec,
    generate_execute_target_after_termination,
)


def _emit_planning_execution_gate_trace(
    *,
    stream_request_id: str,
    event_type: str,
    decision,
    tool_name: str | None,
) -> None:
    try:
        from app.services.agent_trace_logger import log_trace_event

        log_trace_event(
            trace_id=stream_request_id,
            event_type=event_type,
            payload={
                "planning_only": bool(decision.planning_only),
                "explicit_execution_intent": bool(decision.explicit_execution_intent),
                "explicit_execution_veto": bool(decision.explicit_execution_veto),
                "reason_code": str(decision.reason_code or ""),
                "tool_name": tool_name,
            },
        )
    except Exception:
        pass


def _planning_only_gate_response() -> StreamingResponse:
    return StreamingResponse(
        iter(
            [
                sanitize_user_visible_text(
                    "הפנייה הנוכחית נשארת במצב תכנון בלבד. לא אבצע פעולה ביצועית ולא אמשיך אישור קיים. "
                    "כדי לעבור לביצוע בפועל כתוב במפורש מה לבצע."
                )
            ]
        ),
        media_type="text/plain",
    )


def _maybe_handle_approval_or_cancel_flow(
    *,
    request,
    db,
    no_tools_requested: bool,
    computed_data,
    termination_already_executed: bool,
    termination_change: bool,
    wants_execute_target_plan: bool,
    original_user_msg: str,
    effective_portfolio,
    force_max_exemption: bool,
    stream_request_id: str,
    is_portfolio_analysis: bool,
    is_doc_request: bool,
    is_qa_mode: bool,
):
    approval = extract_user_approval_for_tool_call(request.messages)
    cancelled = extract_user_cancel_for_tool_call(request.messages)
    last_user_text = find_last_user_message(request.messages)
    execution_gate = decide_stream_planning_execution_policy(last_user_text)
    pending_db = None
    veto_active = False
    if request.client_id is not None:
        try:
            if should_clear_execution_veto_for_current_turn(last_user_text):
                clear_execution_veto(
                    db=db,
                    client_id=int(request.client_id),
                    scope="termination_execution",
                    trace_id=stream_request_id,
                )
            elif is_explicit_execution_veto_turn(last_user_text):
                store_execution_veto(
                    db=db,
                    client_id=int(request.client_id),
                    veto_active=True,
                    scope="termination_execution",
                    reason_code="explicit_execution_veto_turn",
                    source_text=last_user_text,
                    trace_id=stream_request_id,
                )
        except Exception:
            pass

        try:
            loaded_veto = load_execution_veto(
                db=db,
                client_id=int(request.client_id),
                trace_id=stream_request_id,
            )
        except Exception:
            loaded_veto = None
        veto_active = (
            isinstance(loaded_veto, dict)
            and loaded_veto.get("veto_active") is True
            and str(loaded_veto.get("scope") or "") == "termination_execution"
        )

        try:
            pending_db = load_pending_approval_request(
                db=db,
                client_id=request.client_id,
            )
        except Exception:
            pending_db = None

        if (
            pending_db is not None
            and isinstance(last_user_text, str)
            and last_user_text
        ):
            try:
                if "###USER_APPROVED###" in last_user_text:
                    after = last_user_text.split("###USER_APPROVED###", 1)[1].strip()
                    raw_json = after.strip("`").strip()
                    raw_json = raw_json.splitlines()[0] if raw_json else ""
                    parsed = json.loads(raw_json) if raw_json else None
                    if isinstance(parsed, dict):
                        raw_tool = parsed.get("tool_name")
                        raw_args = parsed.get("arguments")
                        pending_tool_name, pending_tool_args = pending_db
                        if (
                            isinstance(raw_tool, str)
                            and isinstance(raw_args, dict)
                            and isinstance(pending_tool_name, str)
                            and isinstance(pending_tool_args, dict)
                            and raw_tool == pending_tool_name
                        ):
                            merged_args = dict(pending_tool_args)
                            merged_args.update(raw_args)
                            approval = (pending_tool_name, merged_args)
                if "###USER_CANCELLED###" in last_user_text:
                    after = last_user_text.split("###USER_CANCELLED###", 1)[1].strip()
                    raw_json = after.strip("`").strip()
                    raw_json = raw_json.splitlines()[0] if raw_json else ""
                    parsed = json.loads(raw_json) if raw_json else None
                    if isinstance(parsed, dict):
                        raw_tool = parsed.get("tool_name")
                        raw_args = parsed.get("arguments")
                        pending_tool_name, pending_tool_args = pending_db
                        if (
                            isinstance(raw_tool, str)
                            and isinstance(raw_args, dict)
                            and isinstance(pending_tool_name, str)
                            and isinstance(pending_tool_args, dict)
                            and raw_tool == pending_tool_name
                        ):
                            merged_args = dict(pending_tool_args)
                            merged_args.update(raw_args)
                            cancelled = (pending_tool_name, merged_args)
            except Exception:
                pass

        if (
            pending_db is not None
            and (
                execution_gate.planning_only
                or execution_gate.explicit_execution_veto
                or (
                    veto_active
                    and str(pending_db[0] if isinstance(pending_db, tuple) else "")
                    == "PROCESS_TERMINATION"
                )
            )
            and cancelled is None
        ):
            pending_tool_name = pending_db[0] if isinstance(pending_db, tuple) else None
            _emit_planning_execution_gate_trace(
                stream_request_id=stream_request_id,
                event_type="planning_execution_gate_blocked_approval_replay",
                decision=execution_gate,
                tool_name=str(pending_tool_name or ""),
            )
            return _planning_only_gate_response()

        if approval is not None and pending_db is not None:
            approved_tool_name, approved_tool_args = approval
            pending_tool_name, pending_tool_args = pending_db
            if (
                isinstance(approved_tool_name, str)
                and isinstance(pending_tool_name, str)
                and approved_tool_name == pending_tool_name
                and isinstance(approved_tool_args, dict)
                and isinstance(pending_tool_args, dict)
            ):
                if len(approved_tool_args.keys()) < len(pending_tool_args.keys()):
                    merged_args = dict(pending_tool_args)
                    merged_args.update(approved_tool_args)
                    approval = (approved_tool_name, merged_args)

        if cancelled is not None and pending_db is not None:
            cancelled_tool_name, cancelled_tool_args = cancelled
            pending_tool_name, pending_tool_args = pending_db
            if (
                isinstance(cancelled_tool_name, str)
                and isinstance(pending_tool_name, str)
                and cancelled_tool_name == pending_tool_name
                and isinstance(cancelled_tool_args, dict)
                and isinstance(pending_tool_args, dict)
            ):
                if len(cancelled_tool_args.keys()) < len(pending_tool_args.keys()):
                    merged_args = dict(pending_tool_args)
                    merged_args.update(cancelled_tool_args)
                    cancelled = (cancelled_tool_name, merged_args)

    if approval is None and request.client_id is not None:
        last_user_text = find_last_user_message(request.messages)
        if is_user_approval_intent_text(last_user_text):
            pending = extract_latest_approval_request(request.messages)
            if pending is not None:
                approval = pending
            else:
                pending_db = pending_db
                if pending_db is not None:
                    approval = pending_db
            if approval is None and pending_db is None:
                return StreamingResponse(
                    iter(
                        [
                            "לא נמצאה בקשת אישור פעילה לביצוע. כדי לבצע פעולה במערכת צריך קודם לקבל בקשת אישור (כפתור אשר), או לבקש שוב במפורש לבצע את הפעולה."
                        ]
                    ),
                    media_type="text/plain",
                )

    if approval and request.client_id is not None:
        approved_tool_name, approved_tool_args = approval

        if (
            execution_gate.planning_only
            or execution_gate.explicit_execution_veto
            or (veto_active and approved_tool_name == "PROCESS_TERMINATION")
            or (not execution_gate.explicit_execution_intent)
        ):
            _emit_planning_execution_gate_trace(
                stream_request_id=stream_request_id,
                event_type="planning_execution_gate_blocked_execution_consume",
                decision=execution_gate,
                tool_name=str(approved_tool_name or ""),
            )
            return _planning_only_gate_response()

        if (
            approved_tool_name == "PROCESS_TERMINATION"
            and termination_already_executed
            and (not termination_change)
            and wants_execute_target_plan
        ):
            return StreamingResponse(
                generate_execute_target_after_termination(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    force_max_exemption=force_max_exemption,
                    stream_request_id=stream_request_id,
                ),
                media_type="text/plain",
            )

        if approved_tool_name == "PROCESS_TERMINATION":
            overrides = extract_process_termination_choice_overrides(original_user_msg)
            if overrides and isinstance(approved_tool_args, dict):
                approved_tool_args = dict(approved_tool_args)
                approved_tool_args.update(overrides)

        if is_doc_request and not is_qa_mode:
            allowed_doc_tools = {
                "GENERATE_FULL_REPORT",
                "GENERATE_TAX_DEDUCTION_DOCUMENTS",
                "TRANSFORM_FUNDS_TO_ASSETS",
            }
            if approved_tool_name not in allowed_doc_tools:
                return StreamingResponse(
                    iter(
                        [
                            "אזהרה: המשתמש ביקש דוח/מסמך (ללא QA). הכלי המאושר אינו מותר במצב זה."
                        ]
                    ),
                    media_type="text/plain",
                )

        if is_qa_mode and approved_tool_name not in {
            "GET_PENSION_PRODUCTS",
            "TRANSFORM_FUNDS_TO_ASSETS",
            "GENERATE_FULL_REPORT",
        }:
            return StreamingResponse(
                iter(["אזהרה: במצב QA הכלי המאושר אינו מותר."]),
                media_type="text/plain",
            )

        return StreamingResponse(
            generate_approval_exec(
                computed_data=computed_data,
                approved_tool_name=approved_tool_name,
                approved_tool_args=approved_tool_args,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                stream_request_id=stream_request_id,
                is_portfolio_analysis=is_portfolio_analysis,
            ),
            media_type="text/plain",
        )

    if cancelled and request.client_id is not None:
        cancelled_tool_name, _cancelled_tool_args = cancelled
        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass
        try:
            clear_pending_build_target_plan_after_termination(
                db=db,
                client_id=int(request.client_id),
            )
        except Exception:
            pass
        return StreamingResponse(
            iter(
                [
                    f"בוצעה ביטול להפעלת הכלי: {cancelled_tool_name}. לא בוצע שינוי במערכת."
                ]
            ),
            media_type="text/plain",
        )

    return None
