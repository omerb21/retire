from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    _is_target_pension_plan_request_text,
    infer_desired_income_is_net_explicit,
    infer_tax_document_type,
    is_cashflow_missing_income_followup,
    is_data_awareness_request,
    is_document_request,
    is_full_report_request,
    is_list_all_financial_entities_request,
    is_max_capital_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_no_termination_request,
    is_no_tools_request,
    is_pension_commutation_request,
    is_portfolio_analysis_request,
    is_portfolio_breakdown_request,
    is_process_termination_request,
    is_qa_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_tax_documents_request,
    is_termination_change_request,
    is_transform_request,
)
from app.services.llm_chat.orchestration_utils_parts.message_builders import (
    build_tax_result_system_message_for_chat,
    build_tax_result_system_message_for_stream,
    build_tool_result_system_message_for_chat,
    build_tool_result_system_message_for_stream,
)
from app.services.llm_chat.orchestration_utils_parts.portfolio_helpers import (
    build_partial_pension_transform_accounts_from_portfolio,
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
)
from app.services.llm_chat.orchestration_utils_parts.protocol import (
    apply_max_exemption_if_requested,
    build_tool_call_message_content,
    parse_tool_call_from_reply,
    validate_tool_call_protocol_for_execution,
)
from app.services.llm_chat.orchestration_utils_parts.snapshot_helpers import (
    compute_default_retirement_date_for_tool_call,
    compute_retirement_date_from_birth_date,
    normalize_retirement_date_if_jan1_placeholder,
    resolve_target_retirement_age,
)
from app.services.llm_chat.orchestration_utils_parts.text_formatters import (
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
)
from app.services.llm_chat.orchestration_utils_parts.tool_call_helpers import (
    extract_desired_monthly_income_from_text,
    extract_explicit_gender_and_age_from_text,
    extract_explicit_retirement_age_from_text,
    extract_explicit_retirement_date_from_text,
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    extract_relative_retirement_years_from_text,
    parse_partial_pension_conversion_request,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_targeted_component_conversion_request,
)
from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    get_tool_display_name_hebrew,
    normalize_tool_name,
)
