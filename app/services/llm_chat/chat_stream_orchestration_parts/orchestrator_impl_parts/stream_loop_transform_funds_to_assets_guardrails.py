from app.schemas.llm_chat import ChatMessage
from app.services.llm_chat.orchestration_utils import (
    is_pension_commutation_request,
    is_process_termination_request,
)
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)

from .stream_loop_transform_tool_args_accounts_override import (
    _maybe_override_transform_tool_args_accounts,
)


def _maybe_guardrail_transform_funds_to_assets(
    *,
    tool_name: str | None,
    wants_ignore_blocked: bool,
    is_doc_request: bool,
    is_qa_mode: bool,
    original_user_msg: str,
    current_pension_portfolio,
    request,
    db,
    tool_args,
    wants_capital_transform: bool,
    history_messages: list[ChatMessage],
):
    if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
        # Guardrail: if the user is asking about current-employer severance / work termination,
        # do not transform the whole portfolio. The correct action is PROCESS_TERMINATION.
        # This prevents accidental portfolio conversion when the user asked to withdraw an exempt grant
        # during work termination.
        if (
            (not wants_ignore_blocked)
            and (not is_doc_request)
            and (not is_qa_mode)
            and is_process_termination_request(original_user_msg)
        ):
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש עזיבת עבודה/פיצויים/מענק. "
                        "אסור לבצע המרת תיק לנכסים. "
                        "כעת אל תחזיר TOOL_CALL ל-TRANSFORM_FUNDS_TO_ASSETS. "
                        "במקום זאת החזר TOOL_CALL ל-PROCESS_TERMINATION בלבד (עם confirmed=true)."
                    ),
                )
            )
            return current_pension_portfolio, tool_args, True

        # Guardrail: pension commutation (היוון קצבה) must not be routed to TRANSFORM_FUNDS_TO_ASSETS.
        if (
            (not is_doc_request)
            and (not is_qa_mode)
            and is_pension_commutation_request(original_user_msg)
        ):
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש היוון קצבה. "
                        "אסור לבצע TRANSFORM_FUNDS_TO_ASSETS. "
                        "כעת אל תחזיר TOOL_CALL להמרת תיק. "
                        "במקום זאת החזר TOOL_CALL ל-EXECUTE_PENSION_COMMUTATION בלבד (עם confirmed=true) "
                        "ועם pension_fund_id, commutation_amount, commutation_date, commutation_type."
                    ),
                )
            )
            return current_pension_portfolio, tool_args, True

        # Deterministic override: if the user asked to convert a specific component bucket
        # (e.g., "תגמולים לפני 2000"), do NOT allow a full-portfolio tool call.
        if (not current_pension_portfolio) and request.client_id is not None:
            loaded = load_latest_pension_portfolio_snapshot_models(
                db, request.client_id
            )
            if loaded is not None:
                current_pension_portfolio, _effective_snapshot_at = loaded

        _maybe_override_transform_tool_args_accounts(
            current_pension_portfolio=current_pension_portfolio,
            original_user_msg=original_user_msg,
            tool_args=tool_args,
        )

        if wants_ignore_blocked:
            tool_args["ignore_blocked_balances"] = True
            tool_args["skip_non_convertible_accounts"] = True

        if wants_capital_transform:
            tool_args.setdefault("default_conversion_type", "capital_asset")
            tool_args["commute_pension_components"] = True

    return current_pension_portfolio, tool_args, False
