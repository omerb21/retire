import json
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.services.llm_chat.chat_orchestration_helpers import (
    build_forced_document_reply,
    build_pension_portfolio_update_after_commutation,
    build_pension_portfolio_update_after_transform,
    build_approval_request_ui_action,
    clear_pending_approval_request,
)
from app.services.llm_chat.orchestration_utils import (
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
)
from app.services.llm_chat.chat_orchestration_helpers import format_transform_result_for_user

from .stream_tool_execution import _execute_tool_call
from .stream_top_level_helpers import _store_pending_approval_request


def _stream_execute_tool_no_approval(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    computed_data: Any,
    client_id: int,
    db: Session,
    effective_portfolio: Any,
    force_max_exemption: bool,
    stream_request_id: str,
    is_portfolio_analysis: bool,
) -> StreamingResponse:
    def generate_exec():
        if computed_data is not None:
            computed_json = json.dumps(
                {"type": "computed_data", "data": computed_data.model_dump()},
                ensure_ascii=False,
            )
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        tool_result = _execute_tool_call(
            tool_name,
            tool_args,
            client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=stream_request_id,
        )

        try:
            clear_pending_approval_request(db=db, client_id=client_id)
        except Exception:
            pass

        portfolio_update_marker = build_pension_portfolio_update_after_transform(
            tool_name=tool_name,
            tool_result=tool_result,
            tool_args=tool_args,
            current_pension_portfolio=effective_portfolio,
        )
        if portfolio_update_marker:
            yield portfolio_update_marker

        commutation_update_marker = build_pension_portfolio_update_after_commutation(
            tool_name=tool_name,
            tool_result=tool_result,
            tool_args=tool_args,
            current_pension_portfolio=effective_portfolio,
        )
        if commutation_update_marker:
            yield commutation_update_marker

        forced_document_reply = build_forced_document_reply(
            tool_name=tool_name,
            tool_result=tool_result,
        )
        if forced_document_reply:
            yield "\n\n" + sanitize_user_visible_text(forced_document_reply)
            return

        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            yield format_transform_result_for_user(tool_result=tool_result)
            return

        out = sanitize_user_visible_text(
            format_tool_output_for_user_stream(tool_name, tool_result)
        )
        if is_portfolio_analysis and isinstance(out, str) and out.strip():
            if "הערכה" not in out and "הערכה גסה" not in out and "ראשונית" not in out:
                out = (
                    "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                    + out
                )
        yield out

    return StreamingResponse(generate_exec(), media_type="text/plain; charset=utf-8")



def _stream_request_approval(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    reason: str,
    risk_level: str = "high",
    computed_data: Any,
    client_id: int,
    db: Session,
) -> StreamingResponse:
    def generate_approval():
        if computed_data is not None:
            computed_json = json.dumps(
                {"type": "computed_data", "data": computed_data.model_dump()},
                ensure_ascii=False,
            )
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        try:
            _store_pending_approval_request(
                db=db,
                client_id=client_id,
                tool_name=tool_name,
                tool_args=tool_args,
            )
        except Exception:
            pass

        yield build_approval_request_ui_action(
            tool_name=tool_name,
            tool_args=tool_args,
            reason=reason,
            risk_level=risk_level,
            rag_sources=None,
        )

    return StreamingResponse(
        generate_approval(),
        media_type="text/plain; charset=utf-8",
    )
