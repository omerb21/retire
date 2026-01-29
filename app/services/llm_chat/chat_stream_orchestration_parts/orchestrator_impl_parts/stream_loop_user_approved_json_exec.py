import json

from fastapi.responses import StreamingResponse

from app.services.llm_chat.chat_orchestration_helpers import (
    clear_pending_approval_request,
    load_pending_approval_request,
)
from app.services.llm_chat.pending_approvals import (
    compute_args_hash,
    load_pending_approval_payload_if_match_and_args_hash,
)
from app.services.state.effective_client_state_loader import load_effective_client_state
from app.services.pension_portfolio.snapshot_loader import load_current_effective_state

from app.services.llm_chat.orchestration_utils import (
    format_tool_output_for_user_stream,
    get_tool_display_name_hebrew,
    sanitize_user_visible_text,
)

from ..stream_tool_execution import _execute_tool_call
from ..stream_top_level_helpers import _load_latest_pension_portfolio_snapshot_models

from .stream_loop_transform_next_step_hint import _append_transform_next_step_hint, _extract_first_json_object


def _maybe_handle_user_approved_json_exec(*, request, db, stream_request_id: str, original_user_msg: str):
    if not (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and original_user_msg.strip().startswith("###USER_APPROVED###")
    ):
        return None

    def _approval_refusal_lines() -> list[str]:
        return [
            "אין בקשת אישור פתוחה תואמת לביצוע הפעולה הזו. בקש שוב ביצוע כדי לקבל אישור חדש.",
            "טיפ: לחץ על אשר מתוך חלון האישור, או בקש שוב אישור כדי לקבל JSON עדכני.",
        ]

    def _parse_user_approved_payload(user_msg: str) -> tuple[str, dict] | None:
        marker = "###USER_APPROVED###"
        if not isinstance(user_msg, str) or marker not in user_msg:
            return None
        after = user_msg.split(marker, 1)[1].strip()
        json_str = after.strip("`").strip()
        json_str = json_str.splitlines()[0] if json_str else ""
        if not json_str:
            return None
        try:
            parsed = json.loads(json_str)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        tool_name = parsed.get("tool_name")
        tool_args = parsed.get("arguments")
        if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
            return None
        return tool_name, tool_args

    approved = _parse_user_approved_payload(original_user_msg)
    if approved is None:
        return StreamingResponse(
            iter(_approval_refusal_lines()),
            media_type="text/plain; charset=utf-8",
        )

    approved_tool, approved_args = approved

    effective_mode = ""
    try:
        _st = load_effective_client_state(db, request.client_id)
        effective_mode = str(getattr(_st, "mode", "") or "")
    except Exception:
        effective_mode = ""
    is_locked_now = effective_mode.strip() == "POST_CONVERSION_LOCKED"

    accounts_obj = approved_args.get("accounts") if isinstance(approved_args, dict) else None
    has_nonempty_accounts = isinstance(accounts_obj, list) and len(accounts_obj) > 0

    dangerous_request_kind: str | None = None
    if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS":
        dangerous_request_kind = "execute_target_plan"
    elif approved_tool == "EXECUTE_RETIREMENT_SCENARIO":
        dangerous_request_kind = "execute_retirement_scenario"

    must_require_pending = bool(dangerous_request_kind is not None and (is_locked_now or has_nonempty_accounts))

    if must_require_pending and dangerous_request_kind is not None:
        args_hash = compute_args_hash(approved_args)
        pending = load_pending_approval_payload_if_match_and_args_hash(
            db=db,
            client_id=request.client_id,
            request_kind=dangerous_request_kind,
            tool_name=approved_tool,
            args_hash=args_hash,
        )
        if pending is None:
            return StreamingResponse(
                iter(_approval_refusal_lines()),
                media_type="text/plain; charset=utf-8",
            )

    if approved_tool == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT":
        try:
            pending_basic = load_pending_approval_request(
                db=db,
                client_id=request.client_id,
            )
        except Exception:
            pending_basic = None
        if pending_basic is None:
            return StreamingResponse(
                iter(
                    [
                        "אין בקשת אישור פתוחה תואמת לביצוע הפעולה הזו. בקש שוב ביצוע כדי לקבל אישור חדש."
                    ]
                ),
                media_type="text/plain; charset=utf-8",
            )
        pending_tool_name, pending_tool_args = pending_basic
        if (
            not isinstance(pending_tool_name, str)
            or pending_tool_name != approved_tool
            or (compute_args_hash(pending_tool_args) != compute_args_hash(approved_args))
        ):
            return StreamingResponse(
                iter(
                    [
                        "אין בקשת אישור פתוחה תואמת לביצוע הפעולה הזו. בקש שוב ביצוע כדי לקבל אישור חדש."
                    ]
                ),
                media_type="text/plain; charset=utf-8",
            )

    def _generate_user_approved_exec(req_id: str):
        should_clear_pending = True
        try:
            effective_portfolio = request.pension_portfolio
            try:
                loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    effective_portfolio, _snapshot_at = loaded
            except Exception:
                pass

            tool_result = _execute_tool_call(
                approved_tool,
                approved_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            if must_require_pending:
                parsed = _extract_first_json_object(tool_result)
                if isinstance(parsed, dict) and parsed.get("success") is False:
                    should_clear_pending = False

            if approved_tool == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT":
                try:
                    _refreshed = load_current_effective_state(db, request.client_id)
                except Exception:
                    _refreshed = None

                try:
                    loaded_after = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                    if loaded_after is not None:
                        effective_portfolio, _snapshot_at = loaded_after
                except Exception:
                    pass
        finally:
            try:
                if should_clear_pending:
                    clear_pending_approval_request(db=db, client_id=request.client_id)
            except Exception:
                pass

        tool_display = get_tool_display_name_hebrew(approved_tool)
        user_tool_output = format_tool_output_for_user_stream(approved_tool, tool_result)
        rendered = (
            f"🔧 **פלט כלי ({tool_display}):**\n" + sanitize_user_visible_text(user_tool_output)
        )
        yield _append_transform_next_step_hint(tool_name=approved_tool, rendered_output=rendered)

    return StreamingResponse(
        _generate_user_approved_exec(stream_request_id),
        media_type="text/plain; charset=utf-8",
    )
