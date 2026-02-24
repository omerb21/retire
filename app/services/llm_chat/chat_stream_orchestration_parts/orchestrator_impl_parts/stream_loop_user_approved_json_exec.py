import json
from datetime import datetime, timezone

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
    build_default_termination_plan_preview,
    clear_current_employer_termination_plan_preview,
    clear_pending_build_target_plan_after_termination,
    clear_pending_current_employer_severance_termination_question,
    get_current_employer_severance_amount_ssot,
    load_pending_build_target_plan_after_termination,
    load_current_employer_termination_plan_preview,
    load_pending_current_employer_severance_termination_question,
    store_current_employer_severance_execution_decision,
    store_current_employer_termination_plan_preview,
)

from ..stream_tool_execution import _execute_tool_call
from ..stream_top_level_helpers import _load_latest_pension_portfolio_snapshot_models

from .stream_loop_transform_next_step_hint import (
    _append_transform_next_step_hint,
    _extract_first_json_object,
)


def _maybe_handle_user_approved_json_exec(
    *, request, db, stream_request_id: str, original_user_msg: str
):
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
            media_type="text/plain",
        )

    approved_tool, approved_args = approved

    # HARD GATE: PROCESS_TERMINATION approvals may not bypass the termination-plan preview.
    # If there is no approved preview in DB, return the preview text and stop (no tool execution).
    if approved_tool == "PROCESS_TERMINATION" and request.client_id is not None:

        def _is_not_expired(raw: object) -> bool:
            if not isinstance(raw, str) or not raw.strip():
                return True
            try:
                dt = datetime.fromisoformat(raw.strip())
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt > datetime.now(timezone.utc)
            except Exception:
                return False

        def _return_preview(*, args_template_in: dict | None) -> StreamingResponse:
            plan_args = {}
            try:
                pending_question = (
                    load_pending_current_employer_severance_termination_question(
                        db=db,
                        client_id=int(request.client_id),
                    )
                )
                if isinstance(pending_question, dict) and isinstance(
                    pending_question.get("plan_args"), dict
                ):
                    plan_args = dict(pending_question.get("plan_args") or {})
            except Exception:
                plan_args = {}

            current_employer_amount = 0.0
            try:
                current_employer_amount = float(
                    get_current_employer_severance_amount_ssot(
                        db=db, client_id=int(request.client_id)
                    )
                    or 0
                )
            except Exception:
                current_employer_amount = 0.0

            preview_text, default_template = build_default_termination_plan_preview(
                current_employer_amount=current_employer_amount,
                context=None,
            )
            try:
                template_to_store = (
                    dict(args_template_in)
                    if isinstance(args_template_in, dict) and args_template_in
                    else dict(default_template)
                )
                store_current_employer_termination_plan_preview(
                    db=db,
                    client_id=int(request.client_id),
                    payload={
                        "plan_args": plan_args,
                        "termination_arguments_template": template_to_store,
                        "awaiting_user_confirmation": True,
                        "approved": False,
                        "declined": False,
                        "used": False,
                    },
                )
            except Exception:
                pass

            try:
                store_current_employer_severance_execution_decision(
                    db=db,
                    client_id=int(request.client_id),
                    decision="yes",
                )
            except Exception:
                pass

            try:
                clear_pending_current_employer_severance_termination_question(
                    db=db,
                    client_id=int(request.client_id),
                )
            except Exception:
                pass

            try:
                clear_pending_approval_request(db=db, client_id=request.client_id)
            except Exception:
                pass

            return StreamingResponse(
                iter([preview_text]),
                media_type="text/plain",
            )

        approval_id_in = (
            approved_args.get("approval_id")
            if isinstance(approved_args, dict)
            else None
        )
        preview_id_in = (
            approved_args.get("preview_id") if isinstance(approved_args, dict) else None
        )
        if not (isinstance(approval_id_in, str) and approval_id_in.strip()):
            return _return_preview(args_template_in=None)
        if not (isinstance(preview_id_in, str) and preview_id_in.strip()):
            return _return_preview(args_template_in=None)

        preview_payload = None
        try:
            preview_payload = load_current_employer_termination_plan_preview(
                db=db,
                client_id=int(request.client_id),
            )
        except Exception:
            preview_payload = None

        preview_approved = False
        args_template = None
        stored_preview_id = None
        preview_used = False
        preview_not_expired = True
        if isinstance(preview_payload, dict):
            preview_approved = bool(preview_payload.get("approved")) is True
            args_template = preview_payload.get("termination_arguments_template")
            stored_preview_id = preview_payload.get("preview_id")
            preview_used = bool(preview_payload.get("used")) is True
            preview_not_expired = _is_not_expired(preview_payload.get("expires_at"))

        if not (isinstance(stored_preview_id, str) and stored_preview_id.strip()):
            return _return_preview(
                args_template_in=(
                    args_template if isinstance(args_template, dict) else None
                )
            )
        if stored_preview_id.strip() != preview_id_in.strip():
            return _return_preview(
                args_template_in=(
                    args_template if isinstance(args_template, dict) else None
                )
            )

        if (
            preview_approved
            and (not preview_used)
            and preview_not_expired
            and isinstance(args_template, dict)
            and args_template
        ):
            # SSOT: ignore any user-supplied args in ###USER_APPROVED###; execute exactly the approved template.
            approved_args = dict(args_template)
            approved_args["approval_id"] = approval_id_in.strip()
            approved_args["preview_id"] = preview_id_in.strip()

        if not (preview_approved and (not preview_used) and preview_not_expired):
            return _return_preview(
                args_template_in=(
                    args_template if isinstance(args_template, dict) else None
                )
            )

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
            if isinstance(pending_payload, dict)
            and isinstance(pending_payload.get("arguments"), dict)
            else None
        )
        pending_args_hash = (
            pending_payload.get("args_hash")
            if isinstance(pending_payload, dict)
            else None
        )

        if (
            isinstance(pending_args, dict)
            and isinstance(pending_args_hash, str)
            and pending_args_hash.strip()
        ):
            if _args_conflict(pending_args, approved_args):
                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain",
                )

            merged_args = dict(pending_args)
            merged_args.update(dict(approved_args))
            merged_hash = compute_args_hash(merged_args)
            if merged_hash != pending_args_hash.strip():
                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain",
                )

            has_valid_pending_match = True
        else:
            return StreamingResponse(
                iter(_approval_refusal_lines()),
                media_type="text/plain",
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
                    media_type="text/plain",
                )
            if _args_conflict(pending_tool_args, approved_args):
                if (
                    approved_tool == "PROCESS_TERMINATION"
                    and request.client_id is not None
                ):
                    try:
                        preview_payload2 = (
                            load_current_employer_termination_plan_preview(
                                db=db,
                                client_id=int(request.client_id),
                            )
                        )
                    except Exception:
                        preview_payload2 = None
                    args_template2 = (
                        preview_payload2.get("termination_arguments_template")
                        if isinstance(preview_payload2, dict)
                        else None
                    )
                    preview_text2, default_template2 = (
                        build_default_termination_plan_preview(
                            current_employer_amount=0.0,
                            context=None,
                        )
                    )
                    try:
                        template_to_store2 = (
                            dict(args_template2)
                            if isinstance(args_template2, dict) and args_template2
                            else dict(default_template2)
                        )
                        store_current_employer_termination_plan_preview(
                            db=db,
                            client_id=int(request.client_id),
                            payload={
                                "plan_args": {},
                                "termination_arguments_template": template_to_store2,
                                "awaiting_user_confirmation": True,
                                "approved": False,
                                "declined": False,
                                "used": False,
                            },
                        )
                    except Exception:
                        pass
                    try:
                        clear_pending_approval_request(
                            db=db, client_id=request.client_id
                        )
                    except Exception:
                        pass
                    return StreamingResponse(
                        iter([preview_text2]),
                        media_type="text/plain",
                    )

                return StreamingResponse(
                    iter(_approval_refusal_lines()),
                    media_type="text/plain",
                )
            else:
                merged_args = dict(pending_tool_args)
                merged_args.update(dict(approved_args))
                if compute_args_hash(merged_args) != compute_args_hash(
                    pending_tool_args
                ):
                    return StreamingResponse(
                        iter(_approval_refusal_lines()),
                        media_type="text/plain",
                    )
                else:
                    has_valid_pending_match = True
        else:
            return StreamingResponse(
                iter(_approval_refusal_lines()),
                media_type="text/plain",
            )

    # SSOT enforcement for termination: once we have a valid pending approval match,
    # execute exactly the approved preview template arguments.
    if (
        approved_tool == "PROCESS_TERMINATION"
        and request.client_id is not None
        and bool(has_valid_pending_match)
    ):
        try:
            preview_payload = load_current_employer_termination_plan_preview(
                db=db,
                client_id=int(request.client_id),
            )
        except Exception:
            preview_payload = None

        try:
            preview_approved = (
                isinstance(preview_payload, dict)
                and bool(preview_payload.get("approved")) is True
            )
        except Exception:
            preview_approved = False

        args_template = (
            preview_payload.get("termination_arguments_template")
            if isinstance(preview_payload, dict)
            else None
        )
        if preview_approved and isinstance(args_template, dict) and args_template:
            tmp_args = dict(args_template)
            if isinstance(merged_args, dict) and isinstance(
                merged_args.get("approval_id"), str
            ):
                tmp_args["approval_id"] = str(merged_args.get("approval_id")).strip()
            if isinstance(merged_args, dict) and isinstance(
                merged_args.get("preview_id"), str
            ):
                tmp_args["preview_id"] = str(merged_args.get("preview_id")).strip()
            merged_args = tmp_args

    if not can_execute_tool(
        tool_name=approved_tool,
        request_kind=request_kind,
        has_pending_approval=bool(has_valid_pending_match),
        user_intent="approve",
    ):
        return StreamingResponse(
            iter(_approval_refusal_lines()),
            media_type="text/plain",
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
            media_type="text/plain",
        )

    def _generate_user_approved_exec(req_id: str):
        should_clear_pending = True
        try:
            effective_portfolio = request.pension_portfolio
            try:
                loaded = _load_latest_pension_portfolio_snapshot_models(
                    db, request.client_id
                )
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

            followup_plan_text: str | None = None

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
                        raw_json = tool_result.split("###SEVERANCE_RESET###", 1)[
                            0
                        ].strip()
                        parsed_term = json.loads(raw_json)
                    except Exception:
                        parsed_term = None

                term_success = (
                    isinstance(parsed_term, dict) and parsed_term.get("success") is True
                )

                if term_success:
                    try:
                        clear_current_employer_termination_plan_preview(
                            db=db,
                            client_id=int(request.client_id),
                        )
                    except Exception:
                        pass

                if term_success and isinstance(pending_build, dict):
                    plan_args = pending_build.get("plan_args")
                    if (
                        isinstance(plan_args, dict)
                        and plan_args.get("target_monthly_pension") is not None
                    ):
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
                            loaded_after_term = (
                                _load_latest_pension_portfolio_snapshot_models(
                                    db,
                                    request.client_id,
                                )
                            )
                            if loaded_after_term is not None:
                                refreshed_portfolio, _snapshot_at_after = (
                                    loaded_after_term
                                )
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

                        followup_plan_text = sanitize_user_visible_text(
                            "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                            + format_tool_output_for_user_stream(
                                "BUILD_TARGET_PENSION_PLAN", plan_result
                            )
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
                    loaded_after = _load_latest_pension_portfolio_snapshot_models(
                        db, request.client_id
                    )
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
        user_tool_output = format_tool_output_for_user_stream(
            approved_tool, tool_result
        )
        using_open_msg = ""
        if using_open_approval:
            using_open_msg = "ℹ️ קיבלתי. משתמש בבקשת אישור פתוחה קיימת עבור הפעולה הזו (עם הפרמטרים המקוריים).\n\n"
        rendered = (
            using_open_msg
            + f"🔧 **פלט כלי ({tool_display}):**\n"
            + sanitize_user_visible_text(user_tool_output)
        )
        yield _append_transform_next_step_hint(
            tool_name=approved_tool, rendered_output=rendered
        )

        if isinstance(followup_plan_text, str) and followup_plan_text.strip():
            yield "\n\n" + followup_plan_text

    return StreamingResponse(
        _generate_user_approved_exec(stream_request_id),
        media_type="text/plain",
    )
