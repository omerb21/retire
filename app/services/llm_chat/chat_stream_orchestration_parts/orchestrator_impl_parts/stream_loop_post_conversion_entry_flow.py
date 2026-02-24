def _run_post_conversion_entry_flow(
    *,
    request,
    db,
    logger,
    stream_request_id: str,
    original_user_msg: str,
    messages,
    computed_data,
    load_effective_client_state,
    is_post_conversion_locked_helper,
    should_show_post_conversion_messages_helper,
    build_post_conversion_lock_message_helper,
    build_post_conversion_plan_message_helper,
    maybe_handle_restore_snapshot_approval_request,
    store_pending_approval_request,
    is_no_tools_request,
    maybe_handle_post_conversion_lock_early_cutoff,
    load_pending_approval_ui_action_if_match,
    is_transform_request,
    maybe_handle_user_approved_exec_flow,
    extract_user_approval_for_tool_call,
    load_pending_approval_request,
    clear_pending_approval_request,
    load_latest_pension_portfolio_snapshot_models,
    execute_tool_call,
    get_tool_display_name_hebrew,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
    append_transform_next_step_hint,
    coerce_float_safe,
    compute_existing_income_offset_monthly,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
):
    effective_client_state = None
    if request.client_id is not None:
        try:
            effective_client_state = load_effective_client_state(db, request.client_id)
        except Exception:
            effective_client_state = None

    def _is_post_conversion_locked() -> bool:
        return is_post_conversion_locked_helper(
            effective_client_state=effective_client_state
        )

    def _should_show_post_conversion_messages() -> bool:
        return should_show_post_conversion_messages_helper(
            effective_client_state=effective_client_state
        )

    def _build_post_conversion_lock_message() -> str:
        return build_post_conversion_lock_message_helper()

    def _build_post_conversion_plan_message() -> str:
        return build_post_conversion_plan_message_helper()

    restore_snapshot_response = maybe_handle_restore_snapshot_approval_request(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        store_pending_approval_request=store_pending_approval_request,
        is_no_tools_request=is_no_tools_request,
    )
    if restore_snapshot_response is not None:
        return (
            restore_snapshot_response,
            effective_client_state,
            _is_post_conversion_locked,
            _should_show_post_conversion_messages,
            _build_post_conversion_lock_message,
            _build_post_conversion_plan_message,
        )

    if _should_show_post_conversion_messages() and isinstance(original_user_msg, str):
        # The post-conversion lock must not prevent returning an approval UI_ACTION
        # (or its deterministic replay) for execute-target-plan.
        post_conversion_response = maybe_handle_post_conversion_lock_early_cutoff(
            request=request,
            db=db,
            logger=logger,
            stream_request_id=stream_request_id,
            original_user_msg=original_user_msg,
            effective_client_state=effective_client_state,
            load_pending_approval_ui_action_if_match=load_pending_approval_ui_action_if_match,
            is_transform_request=is_transform_request,
        )
        if post_conversion_response is not None:
            return (
                post_conversion_response,
                effective_client_state,
                _is_post_conversion_locked,
                _should_show_post_conversion_messages,
                _build_post_conversion_lock_message,
                _build_post_conversion_plan_message,
            )

    user_approved_exec_response = maybe_handle_user_approved_exec_flow(
        request=request,
        db=db,
        messages=messages,
        computed_data=computed_data,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
        should_show_post_conversion_messages=_should_show_post_conversion_messages,
        build_post_conversion_lock_message=_build_post_conversion_lock_message,
        extract_user_approval_for_tool_call=extract_user_approval_for_tool_call,
        load_pending_approval_request=load_pending_approval_request,
        clear_pending_approval_request=clear_pending_approval_request,
        load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
        execute_tool_call=execute_tool_call,
        get_tool_display_name_hebrew=get_tool_display_name_hebrew,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        sanitize_user_visible_text=sanitize_user_visible_text,
        append_transform_next_step_hint=append_transform_next_step_hint,
        coerce_float_safe=coerce_float_safe,
        compute_existing_income_offset_monthly=compute_existing_income_offset_monthly,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
    )
    if user_approved_exec_response is not None:
        return (
            user_approved_exec_response,
            effective_client_state,
            _is_post_conversion_locked,
            _should_show_post_conversion_messages,
            _build_post_conversion_lock_message,
            _build_post_conversion_plan_message,
        )

    return (
        None,
        effective_client_state,
        _is_post_conversion_locked,
        _should_show_post_conversion_messages,
        _build_post_conversion_lock_message,
        _build_post_conversion_plan_message,
    )
