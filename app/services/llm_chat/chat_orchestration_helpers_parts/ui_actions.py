import json

from typing import Optional


def build_approval_request_ui_action(
    *,
    tool_name: str,
    tool_args: dict,
    reason: str,
    risk_level: str | None,
    rag_sources: list[str] | None,
) -> str:
    actions: list[dict[str, object]] = [
        {
            "type": "approval_request",
            "tool_name": tool_name,
            "arguments": tool_args,
            "reason": reason,
            "risk_level": risk_level or "",
            "rag_sources": rag_sources or [],
            "approve_label": "אשר",
            "cancel_label": "בטל",
        }
    ]

    return (
        f"###UI_ACTION###{json.dumps({'type': 'ui_actions', 'actions': actions}, ensure_ascii=False)}###END_UI_ACTION###\n"
        "נדרש אישור לפני הפעלת כלי.\n"
        f"כלי: {tool_name}\n"
        f"סיבה: {reason}"
    )


def build_forced_document_reply(
    *, tool_name: str | None, tool_result: str
) -> Optional[str]:
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
