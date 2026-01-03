from typing import Callable, Optional

from app.services.llm_chat.message_utils import extract_gross_income_for_tax


def get_gross_for_tax_chaining(
    *, is_net: bool, tool_name: str | None, tool_result: str
) -> Optional[float]:
    if not is_net:
        return None

    if tool_name not in {"BUILD_TARGET_PENSION_PLAN", "RUN_RETIREMENT_CASHFLOW_ANALYSIS"}:
        return None

    return extract_gross_income_for_tax(tool_name, tool_result)


def run_tax_projection_autochain(
    *,
    gross_for_tax: Optional[float],
    execute_tool_call_fn: Callable[[str, dict], str],
) -> Optional[str]:
    if gross_for_tax is None:
        return None

    if gross_for_tax <= 0:
        return None

    return execute_tool_call_fn("GET_TAX_PROJECTION", {"gross_monthly_pension": gross_for_tax})
