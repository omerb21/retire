import json
from typing import Optional


def _normalize_open_url(raw: str) -> str:
    url = str(raw or "").strip()
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/api/v1/"):
        return url
    if url.startswith("api/v1/"):
        return "/" + url
    if url.startswith("/fixation/"):
        return "/api/v1" + url
    if url.startswith("fixation/"):
        return "/api/v1/" + url
    if url.startswith("/documents/"):
        return "/api/v1" + url
    if url.startswith("documents/"):
        return "/api/v1/" + url
    if url.startswith("/files"):
        return "/api/v1" + url
    if url.startswith("files"):
        return "/api/v1/" + url
    return url


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
                normalized_url = _normalize_open_url(download_url)
                raw_doc_type = parsed_result.get("document_type")
                doc_type = str(raw_doc_type or "").strip()

                is_fixation_package = (
                    tool_name == "GENERATE_TAX_DEDUCTION_DOCUMENTS"
                    and doc_type
                    in {"fixation_package", "kibua_zechuyot", "package", "161d_package"}
                ) or (
                    isinstance(normalized_url, str)
                    and normalized_url.startswith("/api/v1/fixation/")
                    and normalized_url.endswith("/package")
                )

                if is_fixation_package and client_id is not None:
                    normalized_url = f"/api/v1/fixation/{client_id}/package"

                actions: list[dict[str, str]] = [
                    {
                        "type": "open_url",
                        "url": normalized_url,
                        "label": "פתח להורדה",
                    }
                ]

                if (not is_fixation_package) and client_id is not None:
                    actions.append(
                        {
                            "type": "navigate",
                            "path": f"/clients/{client_id}/reports",
                            "label": "פתח עמוד דוחות",
                        }
                    )

                return (
                    f"###UI_ACTION###{json.dumps({'type': 'ui_actions', 'actions': actions}, ensure_ascii=False)}###END_UI_ACTION###\n"
                    f"{status_message}"
                )
    except Exception:
        return None

    return None
