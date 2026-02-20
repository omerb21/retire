def _run_stream_loop_tail_flow(
    *,
    request,
    db,
    messages,
    original_user_msg: str,
    resolved_intent,
    tools_disabled_reason,
    ui_action_short_circuit_allowed: bool,
    exec_only_active: bool,
    advice_compensation_mode: bool,
    plan_phrase_detected: bool,
    tools_enabled: bool,
    computed_data,
    effective_portfolio,
    stream_request_id: str,
    logger,
    ChatIntentClass,
    is_net_pension_request,
    is_document_request,
    is_tax_documents_request,
    is_qa_request,
    is_no_tools_request,
    is_max_exemption_request,
    is_pension_commutation_request,
    is_transform_request,
    is_process_termination_request,
    is_termination_change_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_portfolio_analysis_request,
    extract_target_net_ils,
    is_cashflow_missing_income_followup,
    maybe_handle_requested_cashflow_calc,
    build_recent_state_banner,
    load_latest_pension_portfolio_snapshot_models,
    generate_cashflow,
    maybe_handle_full_report_no_approval,
    latest_snapshot_operation_type,
    stream_execute_tool_no_approval,
    should_show_post_conversion_messages,
    maybe_handle_post_conversion_lock_early_block,
    maybe_handle_post_conversion_lock_late_block,
    load_pending_approval_ui_action_if_match,
    build_post_conversion_lock_message,
    build_post_conversion_plan_message,
    run_deterministic_routing_block,
    maybe_handle_target_plan_deterministic,
    extract_commutation_account_number,
    generate_commutation_need_account,
    maybe_handle_cashflow_deterministic,
    maybe_handle_max_capital_request,
    maybe_handle_fixation_documents_deterministic,
    maybe_handle_commutation_deterministic,
    compute_analysis_default_retirement_age,
    maybe_handle_termination_deterministic,
    maybe_handle_approval_or_cancel_flow,
    apply_wants_ignore_blocked_and_portfolio_analysis_messages,
    log_llm_event,
    build_streaming_response_generate_loop,
    build_restore_snapshot_banner,
    stream_handle_explicit_transform,
    stream_generate_preamble,
    build_history_messages_for_stream,
    load_stream_intents_playbook_text,
    get_retirement_kb_for_stream,
    stream_collect_llm_response_with_retry_or_yield_error,
    collect_llm_response_with_retry,
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
    stream_execute_tool_and_process_result,
    is_tool_error_text,
    execution_only_blocked,
):
    is_net_request = is_net_pension_request(original_user_msg)
    is_doc_request = is_document_request(original_user_msg)
    is_tax_doc_request = is_tax_documents_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = (resolved_intent == ChatIntentClass.NO_TOOLS) or is_no_tools_request(original_user_msg)
    if advice_compensation_mode:
        no_tools_requested = False
    force_max_exemption = is_max_exemption_request(original_user_msg)
    commutation_intent = is_pension_commutation_request(original_user_msg)
    explicit_transform = (not commutation_intent) and is_transform_request(original_user_msg)
    explicit_termination = is_process_termination_request(original_user_msg)
    termination_change = is_termination_change_request(original_user_msg)
    is_cashflow_request = is_retirement_cashflow_request(original_user_msg)
    is_comparison_request = is_retirement_comparison_request(original_user_msg)
    is_portfolio_analysis = is_portfolio_analysis_request(original_user_msg)

    conceptual_tools_disabled = (
        (tools_disabled_reason in {"conceptual", "conceptual_form"})
        and (resolved_intent != ChatIntentClass.REPORT)
        and (not exec_only_active)
    )

    lowered_user_msg = (original_user_msg or "").lower()
    target_net_for_cashflow = extract_target_net_ils(original_user_msg or "")
    wants_capital_transform = (
        (
            ("להון" in lowered_user_msg)
            or ("to capital" in lowered_user_msg)
            or ("הונית" in lowered_user_msg)
            or ("הוני" in lowered_user_msg)
            or ("מקסימום הון" in lowered_user_msg)
        )
        and (
            "המר" in lowered_user_msg
            or "המרה" in lowered_user_msg
            or "convert" in lowered_user_msg
            or "משיכה" in lowered_user_msg
            or "משוך" in lowered_user_msg
        )
    )
    wants_execute_target_plan = (
        "בצע" in lowered_user_msg
        and ("תכנית" in lowered_user_msg or "תוכנית" in lowered_user_msg or "מתווה" in lowered_user_msg)
    )
    wants_fixation_execute = (
        "בצע" in lowered_user_msg and ("קיבוע" in lowered_user_msg) and ("זכויות" in lowered_user_msg)
    )

    wants_fixation_documents = bool(
        is_tax_doc_request and any(token in lowered_user_msg for token in ("קיבוע", "זכויות", "161ד", "161d"))
    )

    explicit_cashflow_request = ("תזרים" in lowered_user_msg) or ("cashflow" in lowered_user_msg)

    wants_cashflow_refresh = is_cashflow_missing_income_followup(original_user_msg)

    requested_cashflow_calc = bool(
        explicit_cashflow_request
        or wants_cashflow_refresh
        or ("תחשב לי תזרים" in lowered_user_msg)
        or ("תחשב לי תזרים פרישה" in lowered_user_msg)
        or ("חישוב תזרים" in lowered_user_msg)
        or ("תזרים פרישה" in lowered_user_msg)
        or is_comparison_request
        or is_net_request
        or (target_net_for_cashflow is not None)
    )

    if plan_phrase_detected and (not explicit_cashflow_request) and (not wants_cashflow_refresh):
        requested_cashflow_calc = False

    requested_cashflow_calc_response = maybe_handle_requested_cashflow_calc(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        requested_cashflow_calc=bool(requested_cashflow_calc),
        resolved_intent=resolved_intent,
        ChatIntentClass=ChatIntentClass,
        tools_enabled=bool(tools_enabled),
        is_qa_mode=bool(is_qa_mode),
        no_tools_requested=bool(no_tools_requested),
        commutation_intent=bool(commutation_intent),
        conceptual_tools_disabled=bool(conceptual_tools_disabled),
        effective_portfolio=effective_portfolio,
        force_max_exemption=bool(force_max_exemption),
        stream_request_id=stream_request_id,
        build_recent_state_banner=build_recent_state_banner,
        load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
        generate_cashflow=generate_cashflow,
    )
    if requested_cashflow_calc_response is not None:
        return requested_cashflow_calc_response

    full_report_no_approval_response = maybe_handle_full_report_no_approval(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        lowered_user_msg=lowered_user_msg,
        resolved_intent=resolved_intent,
        ChatIntentClass=ChatIntentClass,
        is_doc_request=bool(is_doc_request),
        is_tax_doc_request=bool(is_tax_doc_request),
        is_qa_mode=bool(is_qa_mode),
        no_tools_requested=bool(no_tools_requested),
        conceptual_tools_disabled=bool(conceptual_tools_disabled),
        ui_action_short_circuit_allowed=bool(ui_action_short_circuit_allowed),
        latest_snapshot_operation_type=latest_snapshot_operation_type,
        stream_execute_tool_no_approval=stream_execute_tool_no_approval,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        force_max_exemption=bool(force_max_exemption),
        stream_request_id=stream_request_id,
        is_portfolio_analysis=bool(is_portfolio_analysis),
    )
    if full_report_no_approval_response is not None:
        return full_report_no_approval_response

    if should_show_post_conversion_messages() and isinstance(original_user_msg, str):
        post_conversion_lock_early_response = maybe_handle_post_conversion_lock_early_block(
            request=request,
            db=db,
            logger=logger,
            stream_request_id=stream_request_id,
            original_user_msg=original_user_msg,
            wants_execute_target_plan=bool(wants_execute_target_plan),
            explicit_transform=bool(explicit_transform),
            is_transform_request=is_transform_request,
            load_pending_approval_ui_action_if_match=load_pending_approval_ui_action_if_match,
            build_post_conversion_lock_message=build_post_conversion_lock_message,
            build_post_conversion_plan_message=build_post_conversion_plan_message,
        )
        if post_conversion_lock_early_response is not None:
            return post_conversion_lock_early_response

    # ── Explicit GET_CLIENT_SNAPSHOT shortcut ──────────────────────────
    # Must run *before* deterministic routing so the request never falls
    # through to the LLM or to unrelated deterministic handlers.
    try:
        from app.services.llm_chat.explicit_tool_shortcuts import (
            is_explicit_client_snapshot_request as _is_snap_req,
            wants_json_only as _wants_json,
            build_client_snapshot_tool_result as _build_snap,
        )

        if isinstance(original_user_msg, str) and _is_snap_req(original_user_msg):
            import json as _json
            from fastapi.responses import StreamingResponse as _SR

            _snap_result = _build_snap(client_id=request.client_id, db=db)
            try:
                from app.services.agent_execution.tool_execution_context import mark_tool_ok_seen

                mark_tool_ok_seen()
            except Exception:
                pass
            _snap_json = _json.dumps(_snap_result, ensure_ascii=False)

            # ── Agent Eyes trace events ──
            try:
                from app.services.agent_trace_logger import log_trace_event as _lt
                from app.services.agent_eyes.event_collector import emit_event as _ee

                _lt(
                    event_type="execution_path",
                    payload={
                        "path_id": "chat.stream.explicit_tool_shortcut",
                        "reason": "user_explicitly_requested_GET_CLIENT_SNAPSHOT",
                    },
                    client_id=request.client_id,
                    endpoint="/api/v1/llm/pension-chat-stream",
                )
                _ee(
                    "execution_path",
                    {
                        "path_id": "chat.stream.explicit_tool_shortcut",
                        "reason": "user_explicitly_requested_GET_CLIENT_SNAPSHOT",
                    },
                    client_id=request.client_id,
                    endpoint="/api/v1/llm/pension-chat-stream",
                )

                _tc_payload = {
                    "tool_name": "GET_CLIENT_SNAPSHOT",
                    "tool_call_id": None,
                    "args": {},
                    "client_id": request.client_id,
                    "shortcut": True,
                }
                try:
                    import uuid as _uuid

                    _tc_payload["tool_call_id"] = _uuid.uuid4().hex
                except Exception:
                    _tc_payload["tool_call_id"] = None
                _lt(event_type="tool_call", payload=_tc_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _ee("tool_call", _tc_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")

                _tr_payload = {
                    "tool_name": "GET_SYSTEM_STATE_SNAPSHOT",
                    "tool_call_id": _tc_payload.get("tool_call_id"),
                    "status": "ok",
                    "success": True,
                    "result_length": len(_snap_json),
                    "shortcut": True,
                }
                _lt(event_type="tool_result", payload=_tr_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _ee("tool_result", _tr_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")

                _tr_payload = {
                    "tool_name": "GET_CLIENT_SNAPSHOT",
                    "tool_call_id": _tc_payload.get("tool_call_id"),
                    "status": "ok",
                    "success": True,
                    "result_length": len(_snap_json),
                    "shortcut": True,
                }
                _lt(event_type="tool_result", payload=_tr_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _ee("tool_result", _tr_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
            except Exception:
                pass

            # Return clean JSON or the raw tool JSON string
            _reply = _snap_json

            def _snap_gen():
                yield _reply

            return _SR(_snap_gen(), media_type="text/plain")
    except Exception:
        pass
    # ── End explicit GET_CLIENT_SNAPSHOT shortcut ────────────────────

    deterministic_routing_response, analysis_default_retirement_age, termination_already_executed = (
        run_deterministic_routing_block(
            request=request,
            db=db,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            original_user_msg=original_user_msg,
            lowered_user_msg=lowered_user_msg,
            is_doc_request=bool(is_doc_request),
            is_tax_doc_request=bool(is_tax_doc_request),
            is_qa_mode=bool(is_qa_mode),
            no_tools_requested=bool(no_tools_requested),
            commutation_intent=bool(commutation_intent),
            wants_fixation_documents=bool(wants_fixation_documents),
            conceptual_tools_disabled=bool(conceptual_tools_disabled),
            explicit_termination=bool(explicit_termination),
            termination_change=bool(termination_change),
            wants_execute_target_plan=bool(wants_execute_target_plan),
            wants_fixation_execute=bool(wants_fixation_execute),
            force_max_exemption=bool(force_max_exemption),
            stream_request_id=stream_request_id,
            is_portfolio_analysis=bool(is_portfolio_analysis),
            maybe_handle_target_plan_deterministic=maybe_handle_target_plan_deterministic,
            extract_commutation_account_number=extract_commutation_account_number,
            generate_commutation_need_account=generate_commutation_need_account,
            maybe_handle_cashflow_deterministic=maybe_handle_cashflow_deterministic,
            maybe_handle_max_capital_request=maybe_handle_max_capital_request,
            maybe_handle_fixation_documents_deterministic=maybe_handle_fixation_documents_deterministic,
            maybe_handle_commutation_deterministic=maybe_handle_commutation_deterministic,
            compute_analysis_default_retirement_age=compute_analysis_default_retirement_age,
            maybe_handle_termination_deterministic=maybe_handle_termination_deterministic,
            maybe_handle_approval_or_cancel_flow=maybe_handle_approval_or_cancel_flow,
        )
    )
    if deterministic_routing_response is not None:
        try:
            from app.services.agent_trace_logger import log_trace_event
            log_trace_event(
                event_type="execution_path",
                payload={
                    "path_id": "chat.stream.deterministic",
                    "reason": "deterministic_routing_block_matched",
                },
                client_id=request.client_id,
                endpoint="/api/v1/llm/pension-chat-stream",
            )
        except Exception:
            pass
        return deterministic_routing_response

    if should_show_post_conversion_messages() and isinstance(original_user_msg, str):
        post_conversion_lock_late_response = maybe_handle_post_conversion_lock_late_block(
            request=request,
            db=db,
            logger=logger,
            stream_request_id=stream_request_id,
            original_user_msg=original_user_msg,
            wants_execute_target_plan=bool(wants_execute_target_plan),
            explicit_transform=bool(explicit_transform),
            is_transform_request=is_transform_request,
            load_pending_approval_ui_action_if_match=load_pending_approval_ui_action_if_match,
            build_post_conversion_lock_message=build_post_conversion_lock_message,
            build_post_conversion_plan_message=build_post_conversion_plan_message,
        )
        if post_conversion_lock_late_response is not None:
            return post_conversion_lock_late_response

    wants_ignore_blocked = apply_wants_ignore_blocked_and_portfolio_analysis_messages(
        request=request,
        messages=messages,
        is_portfolio_analysis=is_portfolio_analysis,
    )

    log_llm_event(
        request_id=stream_request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    try:
        from app.services.agent_trace_logger import log_trace_event
        log_trace_event(
            event_type="execution_path",
            payload={
                "path_id": "chat.stream.tool_loop",
                "reason": "no_deterministic_match",
            },
            client_id=request.client_id,
            endpoint="/api/v1/llm/pension-chat-stream",
        )
    except Exception:
        pass

    return build_streaming_response_generate_loop(
        messages=messages,
        computed_data=computed_data,
        resolved_intent=resolved_intent,
        request=request,
        db=db,
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
        stream_request_id=stream_request_id,
        tools_disabled_reason=tools_disabled_reason,
        wants_ignore_blocked=bool(wants_ignore_blocked),
        exec_only_active=bool(exec_only_active),
        is_portfolio_analysis=bool(is_portfolio_analysis),
        is_cashflow_request=bool(is_cashflow_request),
        is_comparison_request=bool(is_comparison_request),
        is_net_request=bool(is_net_request),
        analysis_default_retirement_age=analysis_default_retirement_age,
        explicit_termination=bool(explicit_termination),
        termination_already_executed=bool(termination_already_executed),
        termination_change=bool(termination_change),
        execution_only_blocked=execution_only_blocked,
        build_restore_snapshot_banner=build_restore_snapshot_banner,
        stream_handle_explicit_transform=stream_handle_explicit_transform,
        chat_intent_report=ChatIntentClass.REPORT,
        stream_generate_preamble=stream_generate_preamble,
        build_history_messages_for_stream=build_history_messages_for_stream,
        load_stream_intents_playbook_text=load_stream_intents_playbook_text,
        get_retirement_kb_for_stream=get_retirement_kb_for_stream,
        stream_collect_llm_response_with_retry_or_yield_error=stream_collect_llm_response_with_retry_or_yield_error,
        collect_llm_response_with_retry=collect_llm_response_with_retry,
        logger=logger,
        get_llm_service=get_llm_service,
        get_retry_settings=get_retry_settings,
        maybe_apply_non_tool_response_guardrails=maybe_apply_non_tool_response_guardrails,
        stream_finalize_non_tool_response=stream_finalize_non_tool_response,
        build_allowed_sources_for_numeric_provenance=build_allowed_sources_for_numeric_provenance,
        compute_final_out_with_numeric_provenance_guardrail=compute_final_out_with_numeric_provenance_guardrail,
        postprocess_no_tools_user_visible_text=postprocess_no_tools_user_visible_text,
        validate_execution_only_output=validate_execution_only_output,
        build_exec_only_rewrite_prompt=build_exec_only_rewrite_prompt,
        build_execution_only_fallback=build_execution_only_fallback,
        enforce_behavioral_limits=enforce_behavioral_limits,
        sanitize_words_only_output=sanitize_words_only_output,
        sanitize_words_only_conceptual=sanitize_words_only_conceptual,
        stream_handle_tool_call_iteration=stream_handle_tool_call_iteration,
        stream_prepare_tool_call_and_maybe_request_commutation_approval=stream_prepare_tool_call_and_maybe_request_commutation_approval,
        load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
        generate_cashflow=generate_cashflow,
        stream_execute_tool_and_process_result=stream_execute_tool_and_process_result,
        is_tool_error_text=is_tool_error_text,
        log_llm_event=log_llm_event,
        force_max_exemption=bool(force_max_exemption),
    )
