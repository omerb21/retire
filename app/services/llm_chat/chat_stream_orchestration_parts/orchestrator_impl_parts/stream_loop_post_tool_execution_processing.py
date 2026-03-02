import json

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    build_pension_portfolio_update_after_transform,
    clear_pending_approval_request,
    get_gross_for_tax_chaining,
    maybe_clear_pension_portfolio_after_transform,
)
from app.services.llm_chat.message_utils import find_last_user_message
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
from app.services.llm_chat.orchestration_utils import (
    build_tool_result_system_message_for_stream,
    format_tool_output_for_user_stream,
    get_tool_display_name_hebrew,
    sanitize_user_visible_text,
)
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    is_net_pension_request,
)
from app.utils.llm_chat_log import log_llm_event

from ..stream_tool_execution import _execute_tool_call
from .stream_loop_forced_document_reply import _stream_maybe_emit_forced_document_reply
from .stream_loop_mandatory_fixation_chain import (
    _stream_maybe_run_mandatory_fixation_chain,
)
from .stream_loop_missing_required_tools_guardrail import (
    _maybe_append_missing_required_tools_guardrail,
)
from .stream_loop_tax_autochain_output import _stream_maybe_emit_tax_autochain_result


def _stream_handle_post_tool_execution_processing(
    *,
    logger,
    req_id: str,
    request: ChatRequest,
    db,
    tool_db,
    tool_name: str | None,
    tool_args,
    tool_result,
    current_pension_portfolio,
    required_tools: set[str],
    executed_tools: set[str],
    is_tax_doc_request: bool,
    is_qa_mode: bool,
    qa_summary_required: bool,
    report_open_path: str | None,
    forced_fixation_chain_done: bool,
    force_max_exemption_val: bool,
    history_messages: list[ChatMessage],
):
    if tool_name:
        executed_tools.add(tool_name)

    portfolio_update_marker = build_pension_portfolio_update_after_transform(
        tool_name=tool_name,
        tool_result=tool_result,
        tool_args=tool_args,
        current_pension_portfolio=current_pension_portfolio,
    )
    if portfolio_update_marker:
        yield "\n\n" + portfolio_update_marker

    missing_tools_after = _maybe_append_missing_required_tools_guardrail(
        required_tools=required_tools,
        executed_tools=executed_tools,
        is_tax_doc_request=is_tax_doc_request,
        history_messages=history_messages,
    )

    if is_qa_mode and tool_name == "GENERATE_FULL_REPORT":
        qa_summary_required = True
        try:
            parsed_tool = json.loads(tool_result)
            report_open_path = parsed_tool.get("open_path")
        except Exception:
            report_open_path = report_open_path

    current_pension_portfolio = maybe_clear_pension_portfolio_after_transform(
        tool_name=tool_name,
        tool_result=tool_result,
        current_pension_portfolio=current_pension_portfolio,
    )

    if tool_name == "TRANSFORM_FUNDS_TO_ASSETS" and request.client_id is not None:
        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

    yield from _stream_maybe_emit_forced_document_reply(
        tool_name=tool_name,
        tool_result=tool_result,
        history_messages=history_messages,
    )

    user_tool_output = format_tool_output_for_user_stream(tool_name, tool_result)

    tool_display = get_tool_display_name_hebrew(tool_name)
    yield f"\n\n🔧 **פלט כלי ({tool_display}):**\n{sanitize_user_visible_text(user_tool_output)}"

    log_llm_event(
        request_id=req_id,
        event_type="tool_result",
        payload={"tool_name": tool_name, "result": tool_result},
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    history_messages.append(
        ChatMessage(
            role="system",
            content=build_tool_result_system_message_for_stream(tool_name, tool_result),
        )
    )

    gross_for_tax = None
    tax_result = None
    try:
        _is_net = is_net_pension_request(
            (find_last_user_message(request.messages) or "")
        )
        gross_for_tax = get_gross_for_tax_chaining(
            is_net=_is_net,
            tool_name=tool_name,
            tool_result=tool_result,
        )
    except Exception:
        gross_for_tax = None

    try:
        if gross_for_tax is not None and gross_for_tax > 0:
            _user_text_for_enrich = find_last_user_message(request.messages) or ""
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
                user_text=_user_text_for_enrich,
                last_tool_result=env,
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
                getattr(core_decision, "decision_code", None) == DecisionCode.TOOL_CALL
                and getattr(core_decision, "tool_name", None) == "GET_TAX_PROJECTION"
            ):
                core_args = getattr(core_decision, "tool_args", None)
                tax_args = core_args if isinstance(core_args, dict) else {}
                tax_result = _execute_tool_call(
                    "GET_TAX_PROJECTION",
                    tax_args,
                    request.client_id,
                    tool_db,
                    pension_portfolio=current_pension_portfolio,
                    force_max_exemption=force_max_exemption_val,
                    request_id=req_id,
                )
    except Exception:
        tax_result = None

    yield from _stream_maybe_emit_tax_autochain_result(
        logger=logger,
        req_id=req_id,
        gross_for_tax=gross_for_tax,
        tax_result=tax_result,
        request=request,
        history_messages=history_messages,
    )

    forced_fixation_chain_done = yield from _stream_maybe_run_mandatory_fixation_chain(
        forced_fixation_chain_done=forced_fixation_chain_done,
        request=request,
        db=db,
        tool_db=tool_db,
        req_id=req_id,
        tool_name=tool_name,
        current_pension_portfolio=current_pension_portfolio,
        force_max_exemption_val=force_max_exemption_val,
        history_messages=history_messages,
    )

    return (
        qa_summary_required,
        report_open_path,
        current_pension_portfolio,
        forced_fixation_chain_done,
    )
