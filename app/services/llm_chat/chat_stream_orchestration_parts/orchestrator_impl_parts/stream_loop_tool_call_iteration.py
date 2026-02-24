from app.services.llm_chat.intent_classifier import ChatIntent
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text


def _stream_handle_tool_call_iteration(
    *,
    logger,
    stream_request_id: str,
    req_id: str,
    full_response: str,
    request,
    db,
    history_messages,
    original_user_msg: str,
    is_portfolio_analysis: bool,
    analysis_default_retirement_age,
    no_tools_requested: bool,
    is_qa_mode: bool,
    is_doc_request: bool,
    is_tax_doc_request: bool,
    wants_ignore_blocked: bool,
    explicit_termination: bool,
    termination_already_executed: bool,
    termination_change: bool,
    current_pension_portfolio,
    wants_capital_transform: bool,
    force_max_exemption_val: bool,
    qa_summary_required: bool,
    report_open_path,
    forced_fixation_chain_done: bool,
    required_tools,
    executed_tools,
    resolved_intent,
    exec_only_active: bool,
    stream_prepare_tool_call_and_maybe_request_commutation_approval,
    load_latest_pension_portfolio_snapshot_models,
    generate_cashflow,
    stream_execute_tool_and_process_result,
    is_tool_error_text,
    execution_only_blocked,
):
    try:
        (
            should_continue,
            should_break,
            should_return,
            tool_name,
            tool_args,
            current_pension_portfolio,
        ) = yield from stream_prepare_tool_call_and_maybe_request_commutation_approval(
            full_response=full_response,
            request=request,
            db=db,
            req_id=req_id,
            history_messages=history_messages,
            original_user_msg=original_user_msg,
            is_portfolio_analysis=is_portfolio_analysis,
            analysis_default_retirement_age=analysis_default_retirement_age,
            no_tools_requested=no_tools_requested,
            is_qa_mode=is_qa_mode,
            is_doc_request=is_doc_request,
            is_tax_doc_request=is_tax_doc_request,
            wants_ignore_blocked=wants_ignore_blocked,
            explicit_termination=explicit_termination,
            termination_already_executed=termination_already_executed,
            termination_change=termination_change,
            current_pension_portfolio=current_pension_portfolio,
            wants_capital_transform=wants_capital_transform,
            force_max_exemption_val=force_max_exemption_val,
        )
        if should_continue:
            return (
                "continue",
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            )
        if should_break:
            return (
                "break",
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            )
        if should_return:
            return (
                "return",
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            )

        if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
            portfolio_for_cashflow = getattr(request, "pension_portfolio", None)
            if not isinstance(portfolio_for_cashflow, list):
                portfolio_for_cashflow = []
            try:
                loaded = load_latest_pension_portfolio_snapshot_models(
                    db, request.client_id
                )
                if loaded is not None:
                    portfolio_for_cashflow, _snap_at = loaded
            except Exception:
                pass

            yield from generate_cashflow(
                computed_data=None,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=portfolio_for_cashflow,
                force_max_exemption=force_max_exemption_val,
                stream_request_id=req_id,
            )
            return (
                "return",
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            )

        (
            should_break,
            qa_summary_required,
            report_open_path,
            current_pension_portfolio,
            forced_fixation_chain_done,
            last_tool_result,
        ) = yield from stream_execute_tool_and_process_result(
            logger=logger,
            req_id=req_id,
            request=request,
            db=db,
            tool_name=tool_name,
            tool_args=tool_args,
            current_pension_portfolio=current_pension_portfolio,
            force_max_exemption_val=force_max_exemption_val,
            full_response=full_response,
            qa_summary_required=qa_summary_required,
            report_open_path=report_open_path,
            forced_fixation_chain_done=forced_fixation_chain_done,
            required_tools=required_tools,
            executed_tools=executed_tools,
            is_tax_doc_request=is_tax_doc_request,
            is_qa_mode=is_qa_mode,
            history_messages=history_messages,
        )
        if should_break:
            return (
                "break",
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            )

        # IMPORTANT: After we stream any tool output, we end the stream immediately.
        # This prevents the model from appending post-tool narrative that may include
        # unprovenanced numbers and get blocked by the numeric provenance guardrail.
        #
        # Exception: in QA mode, after generating a full report, we must continue
        # streaming to allow the model to emit the final QA summary.
        if resolved_intent == ChatIntent.ANALYSIS and (not qa_summary_required):
            if exec_only_active:
                yield execution_only_blocked("policy_violation")
                return (
                    "return",
                    qa_summary_required,
                    report_open_path,
                    current_pension_portfolio,
                    forced_fixation_chain_done,
                )
            if not is_tool_error_text(last_tool_result):
                yield (
                    "\n\n"
                    + "הפקתי את תוצאות הניתוח מהמערכת. להסבר מילולי בלי מספרים כתוב: הסבר במילים.\n"
                )
            return (
                "return",
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            )

        return (
            "none",
            qa_summary_required,
            report_open_path,
            current_pension_portfolio,
            forced_fixation_chain_done,
        )

    except Exception as e:
        logger.error("Stream Tool Execution Failed: %s", e, exc_info=True)
        if exec_only_active and resolved_intent != ChatIntent.REPORT:
            yield execution_only_blocked("tool_execution_failed")
            return (
                "return",
                qa_summary_required,
                report_open_path,
                current_pension_portfolio,
                forced_fixation_chain_done,
            )
        yield f"\n\n(Error executing tool: {sanitize_user_visible_text(str(e))})"
        return (
            "break",
            qa_summary_required,
            report_open_path,
            current_pension_portfolio,
            forced_fixation_chain_done,
        )
