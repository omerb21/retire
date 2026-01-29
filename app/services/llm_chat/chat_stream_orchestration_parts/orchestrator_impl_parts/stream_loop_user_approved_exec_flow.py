import json

from fastapi.responses import StreamingResponse


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
            media_type="text/plain; charset=utf-8",
        )

    def _generate_user_approved_exec(req_id: str):
        if computed_data is not None:
            computed_json = json.dumps(
                {"type": "computed_data", "data": computed_data.model_dump()},
                ensure_ascii=False,
            )
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        after_plan_args = None
        if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS" and isinstance(approved_args, dict):
            maybe_after = approved_args.get("_after_build_target_pension_plan_args")
            if isinstance(maybe_after, dict) and maybe_after:
                after_plan_args = dict(maybe_after)

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

        if after_plan_args is not None and request.client_id is not None:
            yield append_transform_next_step_hint(tool_name=approved_tool, rendered_output=rendered)

            if after_plan_args.get("_pre_retirement_plan_resolution") is True:
                requested_target = coerce_float_safe(after_plan_args.get("target_monthly_pension"))
                target_is_net_val = bool(after_plan_args.get("target_is_net", True))
                retirement_age_val = after_plan_args.get("retirement_age")
                retirement_age_int = None
                if retirement_age_val is not None:
                    try:
                        retirement_age_int = int(retirement_age_val)
                    except Exception:
                        retirement_age_int = None
                existing_income_offset = compute_existing_income_offset_monthly(
                    db=db,
                    client_id=request.client_id,
                    target_is_net=bool(target_is_net_val),
                )
                eff_target = max(float(requested_target) - float(existing_income_offset), 0.0)
                if eff_target <= 0:
                    yield "\n\n" + "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת"
                    return
                after_plan_args["target_monthly_pension"] = float(eff_target)
                after_plan_args.pop("_pre_retirement_plan_resolution", None)

            plan_result = execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                after_plan_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
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

            yield sanitize_user_visible_text(
                "\n\n🔧 **פלט כלי ("
                + get_tool_display_name_hebrew("BUILD_TARGET_PENSION_PLAN")
                + "):**\n"
                + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
            )
            return

        yield append_transform_next_step_hint(tool_name=approved_tool, rendered_output=rendered)

    return StreamingResponse(
        _generate_user_approved_exec(stream_request_id),
        media_type="text/plain; charset=utf-8",
    )
