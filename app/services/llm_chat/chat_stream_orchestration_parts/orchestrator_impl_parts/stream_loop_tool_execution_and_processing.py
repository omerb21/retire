from app.database import SessionLocal
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    store_latest_target_pension_plan,
    store_latest_target_pension_plan_data,
)
from app.services.llm_chat.message_utils import (
    extract_latest_approval_request,
    get_tool_call_approval_signature,
)
from app.services.llm_chat.orchestration_core.core_types import (
    DecisionCode,
    OrchestrationDeps,
    OrchestrationInput,
    ToolResultEnvelope,
)
from app.services.llm_chat.orchestration_core.orchestrate import orchestrate
from app.services.llm_chat.orchestration_core.snapshot_enrichment import (
    enrich_state_snapshot,
)
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text
from app.services.llm_chat.pending_approvals import store_pending_approval_ui_action
from app.utils.llm_chat_log import log_llm_event

from ..stream_tool_execution import _execute_tool_call
from .stream_loop_post_tool_execution_processing import (
    _stream_handle_post_tool_execution_processing,
)


def _stream_execute_tool_and_process_result(
    *,
    logger,
    req_id: str,
    request: ChatRequest,
    db,
    tool_name: str | None,
    tool_args,
    current_pension_portfolio,
    force_max_exemption_val: bool,
    full_response: str,
    qa_summary_required: bool,
    report_open_path: str | None,
    forced_fixation_chain_done: bool,
    required_tools: set[str],
    executed_tools: set[str],
    is_tax_doc_request: bool,
    is_qa_mode: bool,
    history_messages: list[ChatMessage],
):
    try:
        tool_db = SessionLocal()
        try:
            tool_result = _execute_tool_call(
                tool_name,
                tool_args,
                request.client_id,
                tool_db,
                pension_portfolio=current_pension_portfolio,
                force_max_exemption=force_max_exemption_val,
                agent_reply=full_response,
                request_id=req_id,
            )

            if isinstance(tool_result, str) and tool_result.strip():
                full_response = tool_result

            if (
                tool_name == "BUILD_TARGET_PENSION_PLAN"
                and request.client_id is not None
            ):
                try:
                    store_latest_target_pension_plan(
                        db=tool_db,
                        client_id=request.client_id,
                        tool_result=tool_result,
                    )
                except Exception:
                    pass
                try:
                    store_latest_target_pension_plan_data(
                        db=tool_db,
                        client_id=request.client_id,
                        tool_result=tool_result,
                    )
                except Exception:
                    pass

            if (
                isinstance(tool_result, str)
                and "###UI_ACTION###" in tool_result
                and "approval_request" in tool_result
            ):
                if tool_name in {
                    "TRANSFORM_FUNDS_TO_ASSETS",
                    "EXECUTE_RETIREMENT_SCENARIO",
                }:
                    request_kind = (
                        "transform_tool"
                        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
                        else "execute_retirement_scenario"
                    )
                    try:
                        store_pending_approval_ui_action(
                            db=tool_db,
                            client_id=request.client_id,
                            request_kind=request_kind,
                            tool_name=tool_name,
                            tool_args=tool_args if isinstance(tool_args, dict) else {},
                            ui_action=tool_result,
                            trace_id=req_id,
                        )
                    except Exception:
                        pass

                already_sent = False
                try:
                    pending = extract_latest_approval_request(request.messages)
                    if pending is not None:
                        pending_tool, pending_args = pending
                        pending_sig = get_tool_call_approval_signature(
                            pending_tool, pending_args
                        )
                        current_sig = get_tool_call_approval_signature(
                            tool_name,
                            tool_args if isinstance(tool_args, dict) else {},
                        )
                        already_sent = bool(
                            pending_sig and current_sig and pending_sig == current_sig
                        )
                except Exception:
                    already_sent = False

                env = ToolResultEnvelope(
                    tool_name=str(tool_name or ""),
                    tool_args=tool_args if isinstance(tool_args, dict) else {},
                    tool_result=tool_result,
                    status="ok",
                    error_message=None,
                    trace_id=req_id,
                    tool_call_id=None,
                )
                enriched = enrich_state_snapshot(
                    {},
                    user_text="",
                    last_tool_result=env,
                    facts={"approval_request_already_sent": already_sent},
                )

                core_input = OrchestrationInput(
                    user_text="",
                    client_id=getattr(request, "client_id", None),
                    session_id=getattr(request, "session_id", None),
                    conversation_id=getattr(request, "conversation_id", None),
                    trace_id=getattr(request, "trace_id", None),
                    feature_flags={},
                    request_meta=None,
                    state_snapshot=enriched,
                    last_tool_result=env,
                )
                core_deps = OrchestrationDeps(
                    llm_generate=lambda messages, client_id=None: ""
                )
                core_decision, _ = orchestrate(core_input, core_deps)
                if (
                    getattr(core_decision, "decision_code", None)
                    == DecisionCode.RESPOND_ONLY
                ):
                    final_text = str(getattr(core_decision, "final_text", "") or "")
                    if already_sent:
                        log_llm_event(
                            request_id=req_id,
                            event_type="final_answer",
                            payload=(
                                "נדרש אישור לפני הפעלת כלי (כבר נשלחה בקשת אישור). ממתין לאישור בחלונית."
                            ),
                            client_id=request.client_id,
                            extra={"endpoint": "stream"},
                        )
                    else:
                        log_llm_event(
                            request_id=req_id,
                            event_type="final_answer",
                            payload=tool_result,
                            client_id=request.client_id,
                            extra={"endpoint": "stream"},
                        )
                    yield final_text
                    return (
                        True,
                        qa_summary_required,
                        report_open_path,
                        current_pension_portfolio,
                        forced_fixation_chain_done,
                        tool_result,
                    )

            (
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            ) = yield from _stream_handle_post_tool_execution_processing(
                logger=logger,
                req_id=req_id,
                request=request,
                db=db,
                tool_db=tool_db,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                current_pension_portfolio=current_pension_portfolio,
                required_tools=required_tools,
                executed_tools=executed_tools,
                is_tax_doc_request=is_tax_doc_request,
                is_qa_mode=is_qa_mode,
                qa_summary_required=qa_summary_required,
                report_open_path=report_open_path,
                forced_fixation_chain_done=forced_fixation_chain_done,
                force_max_exemption_val=force_max_exemption_val,
                history_messages=history_messages,
            )

            return (
                False,
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
                tool_result,
            )

        finally:
            tool_db.close()

    except Exception as e:
        logger.error("Stream Tool Execution Failed: %s", e, exc_info=True)
        yield f"\n\n(Error executing tool: {sanitize_user_visible_text(str(e))})"
        return (
            True,
            qa_summary_required,
            report_open_path,
            current_pension_portfolio,
            forced_fixation_chain_done,
            None,
        )
