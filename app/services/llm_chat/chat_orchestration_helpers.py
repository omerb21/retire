import json
from app.services.llm_chat.chat_orchestration_helpers_parts.formatting import (
    format_transform_result_for_user,
)
from app.services.llm_chat.chat_orchestration_helpers_parts.portfolio_updates import (
    build_pension_portfolio_update_after_commutation,
    build_pension_portfolio_update_after_transform,
    maybe_clear_pension_portfolio_after_transform,
)
from app.services.llm_chat.chat_orchestration_helpers_parts.scenario_storage import (
    _extract_target_plan_payload_from_tool_result,
    clear_pending_approval_request,
    load_latest_target_pension_plan,
    load_pending_approval_request,
    store_latest_target_pension_plan,
    store_pending_approval_request,
)
from app.services.llm_chat.chat_orchestration_helpers_parts.target_plan_conversion import (
    _clean_account_name_for_transform,
    build_transform_accounts_from_target_plan_payload,
)
from app.services.llm_chat.chat_orchestration_helpers_parts.tax_autochain import (
    get_gross_for_tax_chaining,
    run_tax_projection_autochain,
)
from app.services.llm_chat.chat_orchestration_helpers_parts.ui_actions import (
    build_approval_request_ui_action,
    build_forced_document_reply,
)
