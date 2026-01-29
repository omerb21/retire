def _run_pre_context_flows(
    *,
    request,
    db,
    stream_request_id: str,
    original_user_msg: str,
    ClientModel,
    ScenarioModel,
    extract_latest_target_pension_plan_payload,
    load_latest_target_pension_plan_data,
    load_latest_target_pension_plan,
    maybe_handle_general_retirement_responses,
    is_general_retirement_help_request,
    is_general_retirement_intro_request,
    is_explain_in_words_request,
    extract_target_net_ils,
    load_effective_client_state,
    sanitize_user_visible_text,
    load_latest_pension_portfolio_snapshot_models,
    infer_retirement_age_for_plan_args,
    pre_retirement_plan_resolution,
    execute_tool_call,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
    get_tool_display_name_hebrew,
    format_tool_output_for_user_stream,
    infer_pending_retirement_fields_for_marker,
    store_pending_plan_target_marker,
    maybe_handle_plan_phrase_flow,
    maybe_handle_pre_retirement_plan_resolution_yes_no,
    load_pending_pre_retirement_plan_resolution,
    clear_pending_pre_retirement_plan_resolution,
    coerce_float_safe,
    compute_existing_income_offset_monthly,
    build_transform_accounts_from_portfolio,
    store_pending_approval_request,
    build_approval_request_ui_action,
    maybe_handle_text_approval_flow,
    clear_pending_approval_request,
    load_pending_plan_target_marker_direct,
    delete_marker,
    maybe_handle_pending_plan_target_marker_flow,
    prepare_messages_with_context,
    maybe_route_to_reports_page,
    maybe_handle_user_approved_json_exec,
 ):
    general_retirement_response = maybe_handle_general_retirement_responses(
        original_user_msg=original_user_msg,
        request=request,
        db=db,
        is_general_retirement_help_request=is_general_retirement_help_request,
        is_general_retirement_intro_request=is_general_retirement_intro_request,
        is_explain_in_words_request=is_explain_in_words_request,
        extract_latest_target_pension_plan_payload=extract_latest_target_pension_plan_payload,
        load_latest_target_pension_plan_data=load_latest_target_pension_plan_data,
        load_latest_target_pension_plan=load_latest_target_pension_plan,
    )
    if general_retirement_response is not None:
        return general_retirement_response, False, None, None

    client_id = request.client_id

    plan_phrase_response = maybe_handle_plan_phrase_flow(
        original_user_msg=original_user_msg,
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        client_id=client_id,
        ClientModel=ClientModel,
        extract_target_net_ils=extract_target_net_ils,
        load_effective_client_state=load_effective_client_state,
        sanitize_user_visible_text=sanitize_user_visible_text,
        load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
        infer_retirement_age_for_plan_args=infer_retirement_age_for_plan_args,
        pre_retirement_plan_resolution=pre_retirement_plan_resolution,
        execute_tool_call=execute_tool_call,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
        get_tool_display_name_hebrew=get_tool_display_name_hebrew,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        infer_pending_retirement_fields_for_marker=infer_pending_retirement_fields_for_marker,
        store_pending_plan_target_marker=store_pending_plan_target_marker,
    )
    if plan_phrase_response is not None:
        return plan_phrase_response, False, None, None

    plan_phrase_detected = False

    if request.client_id is not None and isinstance(original_user_msg, str):
        lowered_user_msg = original_user_msg.strip().lower()

        yes_no_response = maybe_handle_pre_retirement_plan_resolution_yes_no(
            request=request,
            db=db,
            stream_request_id=stream_request_id,
            lowered_user_msg=lowered_user_msg,
            load_pending_pre_retirement_plan_resolution=load_pending_pre_retirement_plan_resolution,
            clear_pending_pre_retirement_plan_resolution=clear_pending_pre_retirement_plan_resolution,
            load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
            coerce_float_safe=coerce_float_safe,
            compute_existing_income_offset_monthly=compute_existing_income_offset_monthly,
            build_transform_accounts_from_portfolio=build_transform_accounts_from_portfolio,
            execute_tool_call=execute_tool_call,
            sanitize_user_visible_text=sanitize_user_visible_text,
            format_tool_output_for_user_stream=format_tool_output_for_user_stream,
            store_pending_approval_request=store_pending_approval_request,
            build_approval_request_ui_action=build_approval_request_ui_action,
        )
        if yes_no_response is not None:
            return yes_no_response, plan_phrase_detected, None, None

        text_approval_response = maybe_handle_text_approval_flow(
            request=request,
            db=db,
            stream_request_id=stream_request_id,
            lowered_user_msg=lowered_user_msg,
            ScenarioModel=ScenarioModel,
            load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
            execute_tool_call=execute_tool_call,
            clear_pending_approval_request=clear_pending_approval_request,
            get_tool_display_name_hebrew=get_tool_display_name_hebrew,
            format_tool_output_for_user_stream=format_tool_output_for_user_stream,
            sanitize_user_visible_text=sanitize_user_visible_text,
            coerce_float_safe=coerce_float_safe,
            compute_existing_income_offset_monthly=compute_existing_income_offset_monthly,
            store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
            store_latest_target_pension_plan=store_latest_target_pension_plan,
        )
        if text_approval_response is not None:
            return text_approval_response, plan_phrase_detected, None, None

    pending_plan = load_pending_plan_target_marker_direct(
        session=db,
        client_id=client_id,
    )

    target_net = extract_target_net_ils(original_user_msg)

    pending_plan_marker_response = maybe_handle_pending_plan_target_marker_flow(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
        client_id=client_id,
        pending_plan=pending_plan,
        target_net=target_net,
        delete_marker=delete_marker,
        sanitize_user_visible_text=sanitize_user_visible_text,
        ClientModel=ClientModel,
        infer_retirement_age_for_plan_args=infer_retirement_age_for_plan_args,
        execute_tool_call=execute_tool_call,
        get_tool_display_name_hebrew=get_tool_display_name_hebrew,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
    )
    if pending_plan_marker_response is not None:
        return pending_plan_marker_response, plan_phrase_detected, None, None

    try:
        messages, computed_data = prepare_messages_with_context(request=request, db=db)
    except Exception:
        messages = list(request.messages or [])
        computed_data = None

    reports_route_response = maybe_route_to_reports_page(
        request=request,
        original_user_msg=original_user_msg,
    )
    if reports_route_response is not None:
        return reports_route_response, plan_phrase_detected, messages, computed_data

    approved_json_exec_response = maybe_handle_user_approved_json_exec(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
    )
    if approved_json_exec_response is not None:
        return approved_json_exec_response, plan_phrase_detected, messages, computed_data

    return None, plan_phrase_detected, messages, computed_data
