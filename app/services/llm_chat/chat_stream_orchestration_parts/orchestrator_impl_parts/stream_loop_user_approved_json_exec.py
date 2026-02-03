import json

from fastapi.responses import StreamingResponse

from app.services.llm_chat.guards.tool_execution_guard import can_execute_tool

from app.services.llm_chat.chat_orchestration_helpers import (
    clear_pending_approval_request,
    load_pending_approval_request,
    store_approval_execution_receipt,
    was_approval_execution_recently_recorded,
)
from app.services.llm_chat.pending_approvals import (
    compute_args_hash,
    load_pending_approval_payload_if_match,
    load_pending_approval_payload_if_match_and_args_hash,
)
from app.services.state.effective_client_state_loader import load_effective_client_state
from app.services.pension_portfolio.snapshot_loader import load_current_effective_state

from app.services.llm_chat.orchestration_utils import (
    format_tool_output_for_user_stream,
    get_tool_display_name_hebrew,
    sanitize_user_visible_text,
)
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    clear_pending_build_target_plan_after_termination,
    load_pending_build_target_plan_after_termination,
)

from ..stream_tool_execution import _execute_tool_call
from ..stream_top_level_helpers import _load_latest_pension_portfolio_snapshot_models

from .stream_loop_transform_next_step_hint import _append_transform_next_step_hint, _extract_first_json_object


def _maybe_handle_user_approved_json_exec(*, request, db, stream_request_id: str, original_user_msg: str):
    if not (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and "###USER_APPROVED###" in original_user_msg
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
        parsed = _extract_first_json_object(user_msg.split(marker, 1)[1])
        if parsed is None:
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

    def _args_conflict(pending_args: dict, approved_args_in: dict) -> bool:
        try:
            for k, v in (approved_args_in or {}).items():
                if k in pending_args and pending_args.get(k) != v:
                    return True
        except Exception:
            return True
        return False

    merged_args: dict = dict(approved_args)
    has_valid_pending_match = False
    using_open_approval = False

    request_kind: str | None = None
    if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS":
        request_kind = "execute_target_plan"
    elif approved_tool == "EXECUTE_RETIREMENT_SCENARIO":
        request_kind = "execute_retirement_scenario"

    if request_kind is not None:
        pending_payload = load_pending_approval_payload_if_match(
            db=db,
            client_id=request.client_id,
            request_kind=request_kind,
            tool_name=approved_tool,
        )

        pending_args = (
            pending_payload.get("arguments")
            if isinstance(pending_payload, dict) and isinstance(pending_payload.get("arguments"), dict)
            else None
        )
        pending_args_hash = (
            pending_payload.get("args_hash")
            if isinstance(pending_payload, dict)
            else None
        )

        if isinstance(pending_args, dict) and isinstance(pending_args_hash, str) and pending_args_hash.strip():
            if _args_conflict(pending_args, approved_args):
                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain; charset=utf-8",
                )

            merged_args = dict(pending_args)
            merged_args.update(dict(approved_args))
            merged_hash = compute_args_hash(merged_args)
            if merged_hash != pending_args_hash.strip():
                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain; charset=utf-8",
                )

            has_valid_pending_match = True
        else:
            return StreamingResponse(
                iter(_approval_refusal_lines()),
                media_type="text/plain; charset=utf-8",
            )
    else:
        try:
            pending_basic = load_pending_approval_request(
                db=db,
                client_id=request.client_id,
            )
        except Exception:
            pending_basic = None

        if pending_basic is not None:
            pending_tool_name, pending_tool_args = pending_basic
            if (
                not isinstance(pending_tool_name, str)
                or not isinstance(pending_tool_args, dict)
                or pending_tool_name != approved_tool
            ):
                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain; charset=utf-8",
                )
            if _args_conflict(pending_tool_args, approved_args):
                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain; charset=utf-8",
                )
            else:
                merged_args = dict(pending_tool_args)
                merged_args.update(dict(approved_args))
                if compute_args_hash(merged_args) != compute_args_hash(pending_tool_args):
                    return StreamingResponse(
                        iter(_approval_refusal_lines()),
                        media_type="text/plain; charset=utf-8",
                    )
                else:
                    has_valid_pending_match = True
        else:
            return StreamingResponse(
                iter(_approval_refusal_lines()),
                media_type="text/plain; charset=utf-8",
            )

    if not can_execute_tool(
        tool_name=approved_tool,
        request_kind=request_kind,
        has_pending_approval=bool(has_valid_pending_match),
        user_intent="approve",
    ):
        return StreamingResponse(
            iter(_approval_refusal_lines()),
            media_type="text/plain; charset=utf-8",
        )

    if (not has_valid_pending_match) and was_approval_execution_recently_recorded(
        db=db,
        client_id=request.client_id,
        tool_name=approved_tool,
        tool_args=merged_args,
    ):
        return StreamingResponse(
            iter(
                [
                    "הפעולה הזו כבר אושרה ובוצעה לאחרונה. אם ברצונך לבצע שוב, בקש ביצוע חדש כדי לקבל אישור חדש.",
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
                merged_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            if approved_tool == "PROCESS_TERMINATION" and request.client_id is not None:
                pending_build = None
                try:
                    pending_build = load_pending_build_target_plan_after_termination(
                        db=db,
                        client_id=int(request.client_id),
                    )
                except Exception:
                    pending_build = None

                parsed_term = None
                if isinstance(tool_result, str) and tool_result.strip():
                    try:
                        raw_json = tool_result.split("###SEVERANCE_RESET###", 1)[0].strip()
                        parsed_term = json.loads(raw_json)
                    except Exception:
                        parsed_term = None

                term_success = isinstance(parsed_term, dict) and parsed_term.get("success") is True

                if term_success and isinstance(pending_build, dict):
                    plan_args = pending_build.get("plan_args")
                    if isinstance(plan_args, dict) and plan_args.get("target_monthly_pension") is not None:
                        try:
                            clear_pending_build_target_plan_after_termination(
                                db=db,
                                client_id=int(request.client_id),
                            )
                        except Exception:
                            pass

                        plan_args = dict(plan_args)
                        plan_args["ignore_blocked_balances"] = True

                        try:
                            db.expire_all()
                        except Exception:
                            pass

                        refreshed_portfolio = effective_portfolio
                        try:
                            loaded_after_term = _load_latest_pension_portfolio_snapshot_models(
                                db,
                                request.client_id,
                            )
                            if loaded_after_term is not None:
                                refreshed_portfolio, _snapshot_at_after = loaded_after_term
                        except Exception:
                            refreshed_portfolio = effective_portfolio
                        plan_result = _execute_tool_call(
                            "BUILD_TARGET_PENSION_PLAN",
                            plan_args,
                            request.client_id,
                            db,
                            pension_portfolio=refreshed_portfolio,
                            force_max_exemption=False,
                            user_approved=True,
                            request_id=req_id,
                        )

                        yield "\n\n" + sanitize_user_visible_text(
                            "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                            + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                        )

            parsed = _extract_first_json_object(tool_result)
            if isinstance(parsed, dict) and parsed.get("success") is False:
                should_clear_pending = False
            else:
                try:
                    store_approval_execution_receipt(
                        db=db,
                        client_id=request.client_id,
                        tool_name=approved_tool,
                        tool_args=merged_args,
                    )
                except Exception:
                    pass

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
        using_open_msg = ""
        if using_open_approval:
            using_open_msg = "ℹ️ קיבלתי. משתמש בבקשת אישור פתוחה קיימת עבור הפעולה הזו (עם הפרמטרים המקוריים).\n\n"
        rendered = (
            using_open_msg
            + f"🔧 **פלט כלי ({tool_display}):**\n"
            + sanitize_user_visible_text(user_tool_output)
        )
        yield _append_transform_next_step_hint(tool_name=approved_tool, rendered_output=rendered)

    return StreamingResponse(
        _generate_user_approved_exec(stream_request_id),
        media_type="text/plain; charset=utf-8",
    )
