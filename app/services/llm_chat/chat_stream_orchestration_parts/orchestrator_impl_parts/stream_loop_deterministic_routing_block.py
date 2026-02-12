from fastapi.responses import StreamingResponse


def _run_deterministic_routing_block(
    *,
    request,
    db,
    computed_data,
    effective_portfolio,
    original_user_msg: str,
    lowered_user_msg: str,
    is_doc_request: bool,
    is_tax_doc_request: bool,
    is_qa_mode: bool,
    no_tools_requested: bool,
    commutation_intent: bool,
    wants_fixation_documents: bool,
    conceptual_tools_disabled: bool,
    explicit_termination: bool,
    termination_change: bool,
    wants_execute_target_plan: bool,
    wants_fixation_execute: bool,
    force_max_exemption: bool,
    stream_request_id: str,
    is_portfolio_analysis: bool,
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
 ):
    if not conceptual_tools_disabled:
        target_plan_response = maybe_handle_target_plan_deterministic(
            request=request,
            db=db,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            original_user_msg=original_user_msg,
            lowered_user_msg=lowered_user_msg,
            is_doc_request=is_doc_request,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            wants_execute_target_plan=wants_execute_target_plan,
            stream_request_id=stream_request_id,
        )
        if target_plan_response is not None:
            return target_plan_response, None, False

    if commutation_intent and request.client_id is not None:
        account_number = extract_commutation_account_number(original_user_msg)
        if not account_number:
            return (
                StreamingResponse(
                    generate_commutation_need_account(computed_data=computed_data),
                    media_type="text/plain",
                ),
                None,
                False,
            )

    if not conceptual_tools_disabled:
        cashflow_response = maybe_handle_cashflow_deterministic(
            request=request,
            db=db,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            original_user_msg=original_user_msg,
            lowered_user_msg=lowered_user_msg,
            is_doc_request=is_doc_request,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            commutation_intent=commutation_intent,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
        )
        if cashflow_response is not None:
            return cashflow_response, None, False

    if not conceptual_tools_disabled:
        max_capital_response = maybe_handle_max_capital_request(
            request=request,
            db=db,
            original_user_msg=original_user_msg,
            lowered_user_msg=lowered_user_msg,
            explicit_termination=explicit_termination,
            is_doc_request=is_doc_request,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
        )
        if max_capital_response is not None:
            return max_capital_response, None, False

    if not conceptual_tools_disabled:
        fixation_documents_response = maybe_handle_fixation_documents_deterministic(
            request=request,
            db=db,
            wants_fixation_documents=wants_fixation_documents,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            computed_data=computed_data,
            effective_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
            is_portfolio_analysis=is_portfolio_analysis,
        )
        if fixation_documents_response is not None:
            return fixation_documents_response, None, False

    # Early deterministic handling for pension commutation requests.
    # Only run this path when the user provided a specific account identifier.
    # If the request is vague (no account number), fall back to the LLM flow.
    commutation_response = maybe_handle_commutation_deterministic(
        commutation_intent=commutation_intent,
        request=request,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        original_user_msg=original_user_msg,
        db=db,
        effective_portfolio=effective_portfolio,
        computed_data=computed_data,
    )
    if commutation_response is not None:
        return commutation_response, None, False

    analysis_default_retirement_age = compute_analysis_default_retirement_age(
        request=request,
        db=db,
        is_portfolio_analysis=is_portfolio_analysis,
    )

    termination_already_executed, termination_response = maybe_handle_termination_deterministic(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        explicit_termination=explicit_termination,
        termination_change=termination_change,
        no_tools_requested=no_tools_requested,
        is_qa_mode=is_qa_mode,
        wants_execute_target_plan=wants_execute_target_plan,
        wants_fixation_execute=wants_fixation_execute,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
    )
    if termination_response is not None:
        return termination_response, analysis_default_retirement_age, termination_already_executed

    approval_response = maybe_handle_approval_or_cancel_flow(
        request=request,
        db=db,
        no_tools_requested=no_tools_requested,
        computed_data=computed_data,
        termination_already_executed=termination_already_executed,
        termination_change=termination_change,
        wants_execute_target_plan=wants_execute_target_plan,
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
    )
    if approval_response is not None:
        return approval_response, analysis_default_retirement_age, termination_already_executed

    return None, analysis_default_retirement_age, termination_already_executed
