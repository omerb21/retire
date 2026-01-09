from __future__ import annotations

from app.schemas.llm_chat import ChatResponse


def _maybe_handle_portfolio_breakdown(
    *,
    original_user_msg,
    effective_portfolio,
    effective_snapshot_at,
    computed_data,
) -> ChatResponse | None:
    from app.services.llm_chat.orchestration_utils import is_portfolio_breakdown_request
    from app.services.llm_chat.portfolio_context import build_pension_portfolio_context

    if is_portfolio_breakdown_request(original_user_msg):
        portfolio = effective_portfolio or []
        breakdown = (
            "\n".join(
                build_pension_portfolio_context(
                    portfolio,
                    user_message=original_user_msg,
                    snapshot_at=effective_snapshot_at,
                )
            ).strip()
            if portfolio
            else ""
        )
        if breakdown:
            return ChatResponse(reply=breakdown, computed_data=computed_data)

    return None
