import json

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    build_pension_portfolio_update_after_transform,
    clear_pending_approval_request,
    maybe_clear_pension_portfolio_after_transform,
)
from app.utils.llm_chat_log import log_llm_event
from app.services.llm_chat.orchestration_utils import (
    build_tool_result_system_message_for_stream,
    format_tool_output_for_user_stream,
    get_tool_display_name_hebrew,
    sanitize_user_visible_text,
)

from .stream_loop_missing_required_tools_guardrail import _maybe_append_missing_required_tools_guardrail
from .stream_loop_forced_document_reply import _stream_maybe_emit_forced_document_reply
from .stream_loop_tax_force_chaining import _maybe_run_tax_force_chaining
from .stream_loop_tax_autochain_output import _stream_maybe_emit_tax_autochain_result
from .stream_loop_mandatory_fixation_chain import _stream_maybe_run_mandatory_fixation_chain


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

    gross_for_tax, tax_result = _maybe_run_tax_force_chaining(
        logger=logger,
        req_id=req_id,
        request=request,
        tool_db=tool_db,
        tool_name=tool_name,
        tool_result=tool_result,
        current_pension_portfolio=current_pension_portfolio,
        force_max_exemption_val=force_max_exemption_val,
    )

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
