from fastapi.responses import StreamingResponse


def _build_streaming_response_generate_loop(
    *,
    messages,
    computed_data,
    resolved_intent,
    request,
    db,
    no_tools_requested: bool,
    conceptual_tools_disabled: bool,
    explicit_transform: bool,
    is_doc_request: bool,
    is_tax_doc_request: bool,
    is_qa_mode: bool,
    lowered_user_msg: str,
    original_user_msg: str,
    effective_portfolio,
    wants_capital_transform: bool,
    stream_request_id: str,
    tools_disabled_reason,
    wants_ignore_blocked: bool,
    exec_only_active: bool,
    is_portfolio_analysis: bool,
    is_cashflow_request: bool,
    is_comparison_request: bool,
    is_net_request: bool,
    analysis_default_retirement_age,
    explicit_termination: bool,
    termination_already_executed: bool,
    termination_change: bool,
    execution_only_blocked,
    build_restore_snapshot_banner,
    stream_handle_explicit_transform,
    chat_intent_report,
    stream_generate_preamble,
    build_history_messages_for_stream,
    load_stream_intents_playbook_text,
    get_retirement_kb_for_stream,
    stream_collect_llm_response_with_retry_or_yield_error,
    collect_llm_response_with_retry,
    logger,
    get_llm_service,
    get_retry_settings,
    maybe_apply_non_tool_response_guardrails,
    stream_finalize_non_tool_response,
    build_allowed_sources_for_numeric_provenance,
    compute_final_out_with_numeric_provenance_guardrail,
    postprocess_no_tools_user_visible_text,
    validate_execution_only_output,
    build_exec_only_rewrite_prompt,
    build_execution_only_fallback,
    enforce_behavioral_limits,
    sanitize_words_only_output,
    sanitize_words_only_conceptual,
    stream_handle_tool_call_iteration,
    stream_prepare_tool_call_and_maybe_request_commutation_approval,
    load_latest_pension_portfolio_snapshot_models,
    generate_cashflow,
    stream_execute_tool_and_process_result,
    is_tool_error_text,
    log_llm_event,
    force_max_exemption: bool,
 ) -> StreamingResponse:
    def generate(force_max_exemption_val: bool, req_id: str):
        (
            did_return,
            current_pension_portfolio,
            report_open_path,
            qa_summary_required,
            qa_summary_satisfied,
            executed_tools,
            forced_fixation_chain_done,
            required_tools,
            tool_call_marker,
            max_steps,
            current_step,
        ) = yield from stream_generate_preamble(
            computed_data=computed_data,
            resolved_intent=resolved_intent,
            request=request,
            no_tools_requested=bool(no_tools_requested),
            conceptual_tools_disabled=bool(conceptual_tools_disabled),
            explicit_transform=bool(explicit_transform),
            is_doc_request=bool(is_doc_request),
            is_tax_doc_request=bool(is_tax_doc_request),
            is_qa_mode=bool(is_qa_mode),
            lowered_user_msg=lowered_user_msg,
            original_user_msg=original_user_msg,
            effective_portfolio=effective_portfolio,
            wants_capital_transform=bool(wants_capital_transform),
            db=db,
            req_id=req_id,
            build_restore_snapshot_banner=build_restore_snapshot_banner,
            stream_handle_explicit_transform=stream_handle_explicit_transform,
            chat_intent_report=chat_intent_report,
        )
        if did_return:
            return

        history_messages = build_history_messages_for_stream(
            messages=messages,
            exec_only_active=bool(exec_only_active),
            resolved_intent=resolved_intent,
            tools_disabled_reason=tools_disabled_reason,
            wants_ignore_blocked=bool(wants_ignore_blocked),
            load_stream_intents_playbook_text=load_stream_intents_playbook_text,
            get_retirement_kb_for_stream=get_retirement_kb_for_stream,
        )

        while current_step < max_steps:
            current_step += 1

            should_break, full_response = yield from stream_collect_llm_response_with_retry_or_yield_error(
                collect_llm_response_with_retry=collect_llm_response_with_retry,
                history_messages=history_messages,
                client_id=request.client_id,
                stream_request_id=stream_request_id,
                current_step=current_step,
                logger=logger,
                get_llm_service=get_llm_service,
                get_retry_settings=get_retry_settings,
            )
            if should_break:
                break

            if tool_call_marker not in full_response:
                should_continue, has_pass_fail = maybe_apply_non_tool_response_guardrails(
                    full_response=full_response,
                    request=request,
                    db=db,
                    history_messages=history_messages,
                    is_qa_mode=is_qa_mode,
                    no_tools_requested=no_tools_requested,
                    required_tools=required_tools,
                    executed_tools=executed_tools,
                    is_tax_doc_request=is_tax_doc_request,
                    qa_summary_required=qa_summary_required,
                    is_cashflow_request=is_cashflow_request,
                    is_comparison_request=is_comparison_request,
                    is_net_request=is_net_request,
                    is_doc_request=is_doc_request,
                )
                if should_continue:
                    continue

                log_llm_event(
                    request_id=req_id,
                    event_type="final_answer",
                    payload=full_response,
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )
                if qa_summary_required and has_pass_fail:
                    qa_summary_satisfied = True

                did_return = yield from stream_finalize_non_tool_response(
                    logger=logger,
                    req_id=req_id,
                    stream_request_id=stream_request_id,
                    request=request,
                    history_messages=history_messages,
                    full_response=full_response,
                    resolved_intent=resolved_intent,
                    tools_disabled_reason=tools_disabled_reason,
                    no_tools_requested=bool(no_tools_requested),
                    conceptual_tools_disabled=bool(conceptual_tools_disabled),
                    exec_only_active=bool(exec_only_active),
                    original_user_msg=original_user_msg,
                    is_portfolio_analysis=bool(is_portfolio_analysis),
                    build_allowed_sources_for_numeric_provenance=build_allowed_sources_for_numeric_provenance,
                    compute_final_out_with_numeric_provenance_guardrail=compute_final_out_with_numeric_provenance_guardrail,
                    postprocess_no_tools_user_visible_text=postprocess_no_tools_user_visible_text,
                    validate_execution_only_output=validate_execution_only_output,
                    build_exec_only_rewrite_prompt=build_exec_only_rewrite_prompt,
                    get_llm_service=get_llm_service,
                    build_execution_only_fallback=build_execution_only_fallback,
                    enforce_behavioral_limits=enforce_behavioral_limits,
                    sanitize_words_only_output=sanitize_words_only_output,
                    sanitize_words_only_conceptual=sanitize_words_only_conceptual,
                )
                if did_return:
                    return
                break

            tool_directive, qa_summary_required, report_open_path, current_pension_portfolio, forced_fixation_chain_done = (
                yield from stream_handle_tool_call_iteration(
                    logger=logger,
                    stream_request_id=stream_request_id,
                    req_id=req_id,
                    full_response=full_response,
                    request=request,
                    db=db,
                    history_messages=history_messages,
                    original_user_msg=original_user_msg,
                    is_portfolio_analysis=bool(is_portfolio_analysis),
                    analysis_default_retirement_age=analysis_default_retirement_age,
                    no_tools_requested=bool(no_tools_requested),
                    is_qa_mode=bool(is_qa_mode),
                    is_doc_request=bool(is_doc_request),
                    is_tax_doc_request=bool(is_tax_doc_request),
                    wants_ignore_blocked=bool(wants_ignore_blocked),
                    explicit_termination=bool(explicit_termination),
                    termination_already_executed=bool(termination_already_executed),
                    termination_change=bool(termination_change),
                    current_pension_portfolio=current_pension_portfolio,
                    wants_capital_transform=bool(wants_capital_transform),
                    force_max_exemption_val=bool(force_max_exemption_val),
                    qa_summary_required=bool(qa_summary_required),
                    report_open_path=report_open_path,
                    forced_fixation_chain_done=bool(forced_fixation_chain_done),
                    required_tools=required_tools,
                    executed_tools=executed_tools,
                    resolved_intent=resolved_intent,
                    exec_only_active=bool(exec_only_active),
                    stream_prepare_tool_call_and_maybe_request_commutation_approval=stream_prepare_tool_call_and_maybe_request_commutation_approval,
                    load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
                    generate_cashflow=generate_cashflow,
                    stream_execute_tool_and_process_result=stream_execute_tool_and_process_result,
                    is_tool_error_text=is_tool_error_text,
                    execution_only_blocked=execution_only_blocked,
                )
            )
            if tool_directive == "continue":
                continue
            if tool_directive == "break":
                break
            if tool_directive == "return":
                return

        if qa_summary_required and not qa_summary_satisfied:
            if report_open_path:
                yield (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח. "
                    f"open_path: {report_open_path}"
                )
            else:
                yield "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח."

        if not no_tools_requested:
            missing_tools_final = required_tools.difference(executed_tools)
            if missing_tools_final:
                yield (
                    "\n\nFAIL - לא הושלמו שלבי החובה לבקשה. חסרים הכלים: "
                    + ", ".join(sorted(missing_tools_final))
                )

    return StreamingResponse(
        generate(force_max_exemption, stream_request_id),
        media_type="text/plain",
    )
