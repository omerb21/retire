import json
from typing import Any

from fastapi.responses import StreamingResponse


def _maybe_handle_system_results_report_request(
    *,
    request,
    db,
    stream_request_id: str,
    original_user_msg: str,
    tools_enabled: bool,
    effective_portfolio,
    latest_snapshot_operation_type,
    is_document_request,
    is_tax_documents_request,
    is_qa_request,
    is_no_tools_request,
    SessionLocal,
    execute_tool_call,
 ):
    if not (tools_enabled and request.client_id is not None):
        return None

    lowered_for_report = (original_user_msg or "").lower()
    is_system_results_report_request = (
        (("דוח" in lowered_for_report) and ("תוצאות" in lowered_for_report))
        or (("report" in lowered_for_report) and ("results" in lowered_for_report))
    )
    if not (
        is_system_results_report_request
        and is_document_request(original_user_msg)
        and (not is_tax_documents_request(original_user_msg))
        and (not is_qa_request(original_user_msg))
        and (not is_no_tools_request(original_user_msg))
    ):
        return None

    latest_op = latest_snapshot_operation_type()
    if latest_op is not None and latest_op != "TRANSFORM_FUNDS_TO_ASSETS":
        ui_payload: dict[str, Any] = {
            "type": "ui_actions",
            "actions": [
                {
                    "type": "navigate",
                    "path": f"/clients/{request.client_id}/pension-portfolio",
                    "label": "פתח תיק",
                }
            ],
            "status_message": "כדי להפיק דוח חייבים קודם לבצע המרה (TRANSFORM) כך שהנתונים יהיו במצב יציב.",
        }
        ui_action = "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
        return StreamingResponse(iter([ui_action]), media_type="text/plain; charset=utf-8")

    def _generate_system_results_report_only(req_id: str):
        tool_db = SessionLocal()
        try:
            tool_result = execute_tool_call(
                "GENERATE_FULL_REPORT",
                {"output_format": "html", "report_type": "full"},
                request.client_id,
                tool_db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )
        finally:
            tool_db.close()

        status_message: str | None = None
        open_path: str | None = None
        download_url: str | None = None
        try:
            parsed_tool = json.loads(tool_result)
            if isinstance(parsed_tool, dict):
                open_path = parsed_tool.get("open_path")
                download_url = parsed_tool.get("download_url")
                status_message = parsed_tool.get("status_message") or parsed_tool.get("message")
        except Exception:
            pass

        actions: list[dict[str, str]] = []
        if isinstance(open_path, str) and open_path.strip():
            actions.append({"type": "open_url", "url": open_path.strip(), "label": "פתח דוח"})
        elif isinstance(download_url, str) and download_url.strip():
            actions.append({"type": "open_url", "url": download_url.strip(), "label": "פתח להורדה"})
            actions.append(
                {
                    "type": "open_url",
                    "url": f"/clients/{request.client_id}/reports",
                    "label": "פתח עמוד דוחות",
                }
            )
        else:
            actions.append(
                {
                    "type": "open_url",
                    "url": f"/clients/{request.client_id}/reports",
                    "label": "פתח עמוד דוחות",
                }
            )

        ui_payload: dict[str, Any] = {"type": "ui_actions", "actions": actions}
        if isinstance(status_message, str) and status_message.strip():
            ui_payload["status_message"] = status_message.strip()

        yield "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
        yield "פתחתי את הדוח בטאב חדש."

    return StreamingResponse(
        _generate_system_results_report_only(stream_request_id),
        media_type="text/plain; charset=utf-8",
    )
