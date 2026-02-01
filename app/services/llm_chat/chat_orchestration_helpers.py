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
    clear_pending_plan_target_marker,
    clear_pending_approval_request,
    clear_undo_snapshot,
    load_latest_retirement_cashflow_analysis,
    load_latest_target_pension_plan,
    load_latest_target_pension_plan_data,
    load_pending_plan_target_marker,
    load_pending_approval_request,
    load_undo_snapshot,
    store_approval_execution_receipt,
    store_latest_retirement_cashflow_analysis,
    store_latest_target_pension_plan,
    store_latest_target_pension_plan_data,
    store_pending_approval_request,
    store_pending_plan_target_marker,
    store_undo_snapshot,
    was_approval_execution_recently_recorded,
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


def execute_pending_approval_request(
    *,
    db,
    client_id: int,
    execute_tool_call_fn,
    pension_portfolio,
    force_max_exemption: bool,
    request_id: str | None,
) -> tuple[str, dict, str] | None:
    try:
        pending = load_pending_approval_request(db=db, client_id=client_id)
    except Exception:
        pending = None
    if pending is None:
        return None

    tool_name, tool_args = pending
    tool_result = execute_tool_call_fn(
        tool_name,
        tool_args,
        client_id,
        db,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
        user_approved=True,
        request_id=request_id,
    )

    try:
        clear_pending_approval_request(db=db, client_id=client_id)
    except Exception:
        pass

    return tool_name, tool_args, tool_result
