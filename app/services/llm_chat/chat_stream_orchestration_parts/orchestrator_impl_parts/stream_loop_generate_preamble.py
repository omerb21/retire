import json
from datetime import datetime, timezone
from typing import Any


def _stream_generate_preamble(
    *,
    computed_data,
    resolved_intent,
    request,
    no_tools_requested: bool,
    conceptual_tools_disabled: bool,
    explicit_transform: bool,
    is_doc_request: bool,
    is_tax_doc_request: bool,
    is_qa_mode: bool,
    lowered_user_msg: str,
    original_user_msg: str,
    effective_portfolio,
    wants_capital_transform: bool,
    db,
    req_id: str,
    build_restore_snapshot_banner,
    stream_handle_explicit_transform,
    chat_intent_report,
):
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    now = datetime.now(timezone.utc)
    banner = build_restore_snapshot_banner(now_utc=now)
    if (
        isinstance(banner, str)
        and banner.strip()
        and (resolved_intent != chat_intent_report)
    ):
        yield banner.strip() + "\n\n"

    current_pension_portfolio = effective_portfolio

    if (
        resolved_intent == chat_intent_report
        and request.client_id is not None
        and (not no_tools_requested)
        and (not conceptual_tools_disabled)
    ):
        actions: list[dict[str, str]] = [
            {
                "type": "navigate",
                "path": f"/clients/{request.client_id}/reports?auto_html=1",
                "label": "פתח דוח",
            }
        ]
        ui_payload: dict[str, Any] = {"type": "ui_actions", "actions": actions}
        yield "###UI_ACTION###" + json.dumps(
            ui_payload, ensure_ascii=False
        ) + "###END_UI_ACTION###\n"
        return (True, None, None, None, None, None, None, None, None, None, None)

    if (
        explicit_transform
        and (not no_tools_requested)
        and (not is_doc_request)
        and (not is_qa_mode)
    ):
        yield from stream_handle_explicit_transform(
            lowered_user_msg=lowered_user_msg,
            original_user_msg=original_user_msg,
            current_pension_portfolio=current_pension_portfolio,
            request=request,
            db=db,
            req_id=req_id,
            wants_capital_transform=wants_capital_transform,
        )
        return (True, None, None, None, None, None, None, None, None, None, None)

    report_open_path: str | None = None
    qa_summary_required = False
    qa_summary_satisfied = False
    executed_tools: set[str] = set()
    forced_fixation_chain_done = False

    required_tools: set[str] = set()
    if not no_tools_requested:
        if is_doc_request:
            if is_tax_doc_request:
                required_tools.add("GENERATE_TAX_DEDUCTION_DOCUMENTS")
            else:
                required_tools.add("GENERATE_FULL_REPORT")

    tool_call_marker = "###TOOL_CALL###"
    max_steps = 5
    current_step = 0

    return (
        False,
        current_pension_portfolio,
        report_open_path,
        qa_summary_required,
        qa_summary_satisfied,
        executed_tools,
        forced_fixation_chain_done,
        required_tools,
        tool_call_marker,
        max_steps,
        current_step,
    )
