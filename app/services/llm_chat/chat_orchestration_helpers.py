import json
from typing import Any, Callable, Optional

from app.services.llm_chat.message_utils import extract_gross_income_for_tax


def maybe_clear_pension_portfolio_after_transform(
    *,
    tool_name: str | None,
    tool_result: str,
    current_pension_portfolio: Optional[list[Any]],
) -> Optional[list[Any]]:
    if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
        return current_pension_portfolio

    try:
        parsed_transform = json.loads(tool_result)
        if (
            isinstance(parsed_transform, dict)
            and parsed_transform.get("success") is True
            and parsed_transform.get("source_data_cleared") is True
        ):
            return None
    except Exception:
        return current_pension_portfolio

    return current_pension_portfolio


def build_forced_document_reply(*, tool_name: str | None, tool_result: str) -> Optional[str]:
    if not (isinstance(tool_name, str) and tool_name.startswith("GENERATE_")):
        return None

    try:
        parsed_result = json.loads(tool_result)
        if isinstance(parsed_result, dict) and parsed_result.get("success") is True:
            download_url = parsed_result.get("download_url")
            open_path = parsed_result.get("open_path")
            client_id = parsed_result.get("client_id")
            status_message = (
                parsed_result.get("status_message")
                or parsed_result.get("message")
                or "המסמך הופק בהצלחה."
            )
            if isinstance(open_path, str) and open_path.strip():
                actions: list[dict[str, str]] = [
                    {
                        "type": "navigate",
                        "path": open_path.strip(),
                        "label": "פתח דוח",
                    }
                ]

                return (
                    f"###UI_ACTION###{json.dumps({'type': 'ui_actions', 'actions': actions}, ensure_ascii=False)}###END_UI_ACTION###\n"
                    f"{status_message}"
                )

            if isinstance(download_url, str) and download_url.strip():
                actions: list[dict[str, str]] = [
                    {
                        "type": "open_url",
                        "url": download_url.strip(),
                        "label": "פתח להורדה",
                    }
                ]

                if client_id is not None:
                    actions.append(
                        {
                            "type": "navigate",
                            "path": f"/clients/{client_id}/reports",
                            "label": "פתח עמוד דוחות",
                        }
                    )

                return (
                    f"###UI_ACTION###{json.dumps({'type': 'ui_actions', 'actions': actions}, ensure_ascii=False)}###END_UI_ACTION###\n"
                    f"{status_message}\n\nקישור להורדה: {download_url.strip()}"
                )
    except Exception:
        return None

    return None


def get_gross_for_tax_chaining(*, is_net: bool, tool_name: str | None, tool_result: str) -> Optional[float]:
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
