def _build_runtime_wrappers(
    *,
    original_user_msg: str,
    db,
    today,
    infer_pending_retirement_fields_for_marker_impl,
    infer_retirement_age_for_plan_args_impl,
    is_tool_error_text_impl,
    cashflow_missing_target_prompt_impl,
    cashflow_missing_age_gender_prompt_impl,
    cashflow_missing_retirement_date_prompt_impl,
    has_any_digit_impl,
    is_explain_in_words_request_impl,
    is_general_retirement_help_request_impl,
    is_general_retirement_intro_request_impl,
 ):
    def _infer_pending_retirement_fields_for_marker(
        *, client_id: int | None
    ) -> tuple[int | None, str | None]:
        return infer_pending_retirement_fields_for_marker_impl(
            original_user_msg=original_user_msg,
            db=db,
            client_id=client_id,
            today=today,
        )

    def _infer_retirement_age_for_plan_args(
        *, client_obj, pending_payload: dict | None
    ) -> int | None:
        return infer_retirement_age_for_plan_args_impl(
            original_user_msg=original_user_msg,
            client_obj=client_obj,
            pending_payload=pending_payload,
            today=today,
        )

    def _is_tool_error_text(value: str | None) -> bool:
        return is_tool_error_text_impl(value)

    def _cashflow_missing_target_prompt() -> str:
        return cashflow_missing_target_prompt_impl()

    def _cashflow_missing_age_gender_prompt() -> str:
        return cashflow_missing_age_gender_prompt_impl()

    def _cashflow_missing_retirement_date_prompt() -> str:
        return cashflow_missing_retirement_date_prompt_impl()

    def _has_any_digit(text: str) -> bool:
        return has_any_digit_impl(text)

    def _is_explain_in_words_request(user_msg: str) -> bool:
        return is_explain_in_words_request_impl(user_msg)

    def _is_general_retirement_help_request(user_msg: str) -> bool:
        return is_general_retirement_help_request_impl(user_msg)

    def _is_general_retirement_intro_request(user_msg: str) -> bool:
        return is_general_retirement_intro_request_impl(user_msg)

    return (
        _infer_pending_retirement_fields_for_marker,
        _infer_retirement_age_for_plan_args,
        _is_tool_error_text,
        _cashflow_missing_target_prompt,
        _cashflow_missing_age_gender_prompt,
        _cashflow_missing_retirement_date_prompt,
        _has_any_digit,
        _is_explain_in_words_request,
        _is_general_retirement_help_request,
        _is_general_retirement_intro_request,
    )
