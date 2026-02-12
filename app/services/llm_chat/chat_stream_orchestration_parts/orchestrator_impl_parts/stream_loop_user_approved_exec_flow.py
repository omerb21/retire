import json

from fastapi.responses import StreamingResponse

from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    clear_pending_build_target_plan_after_termination,
    load_pending_build_target_plan_after_termination,
)


def _has_positive_component_amounts(raw: object) -> bool:
    if not isinstance(raw, dict) or not raw:
        return False
    for _k, v in raw.items():
        try:
            if float(v or 0) > 0:
                return True
        except Exception:
            continue
    return False


def _accounts_are_thin(accounts: object) -> bool:
    if not isinstance(accounts, list) or not accounts:
        return False

    def _get_account_number(acc: dict) -> str:
        return str(
            acc.get("account_number")
            or acc.get("מספר_חשבון")
            or acc.get("מספר חשבון")
            or acc.get("מספר-חשבון")
            or ""
        ).strip()

    for acc in accounts:
        if not isinstance(acc, dict):
            continue

        account_number = _get_account_number(acc)
        if not account_number:
            continue

        raw_balance = acc.get("balance")
        if raw_balance is None:
            raw_balance = acc.get("יתרה")
        if raw_balance is None:
            raw_balance = acc.get("current_balance")

        try:
            if float(raw_balance or 0) > 0:
                continue
        except Exception:
            pass

        if _has_positive_component_amounts(acc.get("specific_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_components")):
            continue

        return True

    return False


def _maybe_handle_user_approved_exec_flow(
    *,
    request,
    db,
    messages,
    computed_data,
    stream_request_id: str,
    original_user_msg: str,
    should_show_post_conversion_messages,
    build_post_conversion_lock_message,
    extract_user_approval_for_tool_call,
    load_pending_approval_request,
    clear_pending_approval_request,
    load_latest_pension_portfolio_snapshot_models,
    execute_tool_call,
    get_tool_display_name_hebrew,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
    append_transform_next_step_hint,
    coerce_float_safe,
    compute_existing_income_offset_monthly,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
 ):
    if not (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and original_user_msg.strip().startswith("###USER_APPROVED###")
    ):
        return None

    approved = extract_user_approval_for_tool_call(messages)
    if approved is None:
        return None

    approved_tool, approved_args = approved

    pending_db = None
    try:
        pending_db = load_pending_approval_request(db=db, client_id=request.client_id)
    except Exception:
        pending_db = None
    if pending_db is not None:
        pending_tool_name, pending_tool_args = pending_db
        if (
            isinstance(pending_tool_name, str)
            and isinstance(pending_tool_args, dict)
            and pending_tool_name == approved_tool
            and isinstance(approved_args, dict)
        ):
            merged_args = dict(pending_tool_args)
            merged_args.update(approved_args)
            approved_args = merged_args

    if should_show_post_conversion_messages() and approved_tool in {
        "TRANSFORM_FUNDS_TO_ASSETS",
        "EXECUTE_RETIREMENT_SCENARIO",
    }:
        return StreamingResponse(
            iter([build_post_conversion_lock_message()]),
            media_type="text/plain",
        )

    def _generate_user_approved_exec(req_id: str):
        if computed_data is not None:
            computed_json = json.dumps(
                {"type": "computed_data", "data": computed_data.model_dump()},
                ensure_ascii=False,
            )
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

        effective_portfolio = request.pension_portfolio
        try:
            loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
            if loaded is not None:
                effective_portfolio, _snapshot_at = loaded
        except Exception:
            pass

        if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS" and isinstance(approved_args, dict):
            try:
                if _accounts_are_thin(approved_args.get("accounts")):
                    approved_args["use_provided_accounts_only"] = False
            except Exception:
                pass

        tool_result = execute_tool_call(
            approved_tool,
            approved_args,
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
                try:
                    db.expire_all()
                except Exception:
                    pass

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

                    refreshed_portfolio = effective_portfolio
                    try:
                        loaded_after_term = load_latest_pension_portfolio_snapshot_models(
                            db,
                            request.client_id,
                        )
                        if loaded_after_term is not None:
                            refreshed_portfolio, _snapshot_at_after_term = loaded_after_term
                    except Exception:
                        refreshed_portfolio = effective_portfolio

                    plan_result = execute_tool_call(
                        "BUILD_TARGET_PENSION_PLAN",
                        plan_args,
                        request.client_id,
                        db,
                        pension_portfolio=refreshed_portfolio,
                        force_max_exemption=False,
                        user_approved=True,
                        request_id=req_id,
                    )
                    try:
                        store_latest_target_pension_plan_data(
                            db=db,
                            client_id=request.client_id,
                            tool_result=plan_result,
                        )
                    except Exception:
                        pass
                    try:
                        store_latest_target_pension_plan(
                            db=db,
                            client_id=request.client_id,
                            tool_result=plan_result,
                        )
                    except Exception:
                        pass

                    plan_rendered = (
                        "\n\n"
                        + "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                        + sanitize_user_visible_text(
                            format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                        )
                    )
                    yield plan_rendered

        if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS" and isinstance(approved_args, dict):
            try:
                parsed = json.loads(tool_result)
            except Exception:
                parsed = None

            should_retry = False
            if isinstance(parsed, dict) and parsed.get("success") is True:
                try:
                    total_converted = int(parsed.get("total_converted") or 0)
                except Exception:
                    total_converted = 0
                try:
                    skipped_zero_balance = int(parsed.get("skipped_zero_balance") or 0)
                except Exception:
                    skipped_zero_balance = 0
                if (
                    total_converted == 0
                    and skipped_zero_balance > 0
                    and bool(approved_args.get("use_provided_accounts_only")) is True
                ):
                    should_retry = True

            if should_retry:
                approved_args["use_provided_accounts_only"] = False
                yield "\n\n" + "לא נטענו נתוני חשבון מלאים, מנסה לטעון מה־DB."
                tool_result = execute_tool_call(
                    approved_tool,
                    approved_args,
                    request.client_id,
                    db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=False,
                    user_approved=True,
                    request_id=req_id,
                )

        tool_display = get_tool_display_name_hebrew(approved_tool)
        user_tool_output = format_tool_output_for_user_stream(approved_tool, tool_result)
        rendered = (
            f"🔧 **פלט כלי ({tool_display}):**\n" + sanitize_user_visible_text(user_tool_output)
        )

        yield append_transform_next_step_hint(tool_name=approved_tool, rendered_output=rendered)

    return StreamingResponse(
        _generate_user_approved_exec(stream_request_id),
        media_type="text/plain",
    )
