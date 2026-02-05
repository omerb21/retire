import logging

from fastapi.responses import StreamingResponse

from app.services.llm_chat.chat_orchestration_helpers import clear_pending_plan_target_marker
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    load_current_employer_termination_plan_preview,
    load_current_termination_preview_id,
    store_current_employer_termination_plan_preview,
)
from app.services.llm_chat.orchestration_utils_parts.tool_call_helpers import (
    extract_process_termination_choice_overrides,
)

logger = logging.getLogger("app.llm_chat")

def _run_pre_context_flows(
    *,
    request,
    db,
    stream_request_id: str,
    original_user_msg: str,
    ClientModel,
    ScenarioModel,
    extract_latest_target_pension_plan_payload,
    load_latest_target_pension_plan_data,
    load_latest_target_pension_plan,
    maybe_handle_general_retirement_responses,
    is_general_retirement_help_request,
    is_general_retirement_intro_request,
    is_explain_in_words_request,
    extract_target_net_ils,
    load_effective_client_state,
    sanitize_user_visible_text,
    load_latest_pension_portfolio_snapshot_models,
    infer_retirement_age_for_plan_args,
    pre_retirement_plan_resolution,
    execute_tool_call,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
    get_tool_display_name_hebrew,
    format_tool_output_for_user_stream,
    infer_pending_retirement_fields_for_marker,
    store_pending_plan_target_marker,
    maybe_handle_plan_phrase_flow,
    maybe_handle_pre_retirement_plan_resolution_yes_no,
    load_pending_pre_retirement_plan_resolution,
    clear_pending_pre_retirement_plan_resolution,
    coerce_float_safe,
    compute_existing_income_offset_monthly,
    build_transform_accounts_from_portfolio,
    store_pending_approval_request,
    build_approval_request_ui_action,
    maybe_handle_text_approval_flow,
    clear_pending_approval_request,
    load_pending_plan_target_marker_direct,
    delete_marker,
    maybe_handle_pending_plan_target_marker_flow,
    prepare_messages_with_context,
    maybe_route_to_reports_page,
    maybe_handle_user_approved_json_exec,
 ):
    general_retirement_response = maybe_handle_general_retirement_responses(
        original_user_msg=original_user_msg,
        request=request,
        db=db,
        is_general_retirement_help_request=is_general_retirement_help_request,
        is_general_retirement_intro_request=is_general_retirement_intro_request,
        is_explain_in_words_request=is_explain_in_words_request,
        extract_latest_target_pension_plan_payload=extract_latest_target_pension_plan_payload,
        load_latest_target_pension_plan_data=load_latest_target_pension_plan_data,
        load_latest_target_pension_plan=load_latest_target_pension_plan,
    )
    if general_retirement_response is not None:
        return general_retirement_response, False, None, None

    client_id = request.client_id

    plan_phrase_response = maybe_handle_plan_phrase_flow(
        original_user_msg=original_user_msg,
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        client_id=client_id,
        ClientModel=ClientModel,
        extract_target_net_ils=extract_target_net_ils,
        load_effective_client_state=load_effective_client_state,
        sanitize_user_visible_text=sanitize_user_visible_text,
        load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
        infer_retirement_age_for_plan_args=infer_retirement_age_for_plan_args,
        pre_retirement_plan_resolution=pre_retirement_plan_resolution,
        execute_tool_call=execute_tool_call,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
        get_tool_display_name_hebrew=get_tool_display_name_hebrew,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        infer_pending_retirement_fields_for_marker=infer_pending_retirement_fields_for_marker,
        store_pending_plan_target_marker=store_pending_plan_target_marker,
    )
    if plan_phrase_response is not None:
        return plan_phrase_response, False, None, None

    plan_phrase_detected = False

    if request.client_id is not None and isinstance(original_user_msg, str):
        lowered_user_msg = original_user_msg.strip().lower()

        yes_no_response = maybe_handle_pre_retirement_plan_resolution_yes_no(
            request=request,
            db=db,
            stream_request_id=stream_request_id,
            lowered_user_msg=lowered_user_msg,
            load_pending_pre_retirement_plan_resolution=load_pending_pre_retirement_plan_resolution,
            clear_pending_pre_retirement_plan_resolution=clear_pending_pre_retirement_plan_resolution,
            load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
            coerce_float_safe=coerce_float_safe,
            compute_existing_income_offset_monthly=compute_existing_income_offset_monthly,
            build_transform_accounts_from_portfolio=build_transform_accounts_from_portfolio,
            execute_tool_call=execute_tool_call,
            sanitize_user_visible_text=sanitize_user_visible_text,
            format_tool_output_for_user_stream=format_tool_output_for_user_stream,
            store_pending_approval_request=store_pending_approval_request,
            build_approval_request_ui_action=build_approval_request_ui_action,
            store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
            store_latest_target_pension_plan=store_latest_target_pension_plan,
            clear_pending_plan_target_marker=clear_pending_plan_target_marker,
            clear_pending_approval_request=clear_pending_approval_request,
        )
        if yes_no_response is not None:
            return yes_no_response, plan_phrase_detected, None, None

        text_approval_response = maybe_handle_text_approval_flow(
            request=request,
            db=db,
            stream_request_id=stream_request_id,
            lowered_user_msg=lowered_user_msg,
            ScenarioModel=ScenarioModel,
            load_latest_pension_portfolio_snapshot_models=load_latest_pension_portfolio_snapshot_models,
            execute_tool_call=execute_tool_call,
            clear_pending_approval_request=clear_pending_approval_request,
            get_tool_display_name_hebrew=get_tool_display_name_hebrew,
            format_tool_output_for_user_stream=format_tool_output_for_user_stream,
            sanitize_user_visible_text=sanitize_user_visible_text,
            coerce_float_safe=coerce_float_safe,
            compute_existing_income_offset_monthly=compute_existing_income_offset_monthly,
            store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
            store_latest_target_pension_plan=store_latest_target_pension_plan,
        )
        if text_approval_response is not None:
            return text_approval_response, plan_phrase_detected, None, None

        def _maybe_handle_termination_alternative_choice() -> StreamingResponse | None:
            client_id_local = request.client_id
            if client_id_local is None:
                return None

            try:
                preview_payload = load_current_employer_termination_plan_preview(
                    db=db,
                    client_id=int(client_id_local),
                )
            except Exception:
                preview_payload = None

            if not isinstance(preview_payload, dict):
                return None

            preview_declined = bool(preview_payload.get("declined")) is True
            preview_approved = bool(preview_payload.get("approved")) is True
            preview_awaiting = bool(preview_payload.get("awaiting_user_confirmation")) is True
            preview_used = bool(preview_payload.get("used")) is True
            declined_at = preview_payload.get("declined_at")
            preview_id = preview_payload.get("preview_id")

            active_preview_id = None
            try:
                active_preview_id = load_current_termination_preview_id(
                    db=db,
                    client_id=int(client_id_local),
                )
            except Exception:
                active_preview_id = None

            if (not preview_declined) or preview_approved or preview_awaiting or preview_used:
                return None

            if not (
                isinstance(declined_at, str)
                and bool(declined_at.strip())
                and isinstance(preview_id, str)
                and bool(preview_id.strip())
                and isinstance(active_preview_id, str)
                and bool(active_preview_id.strip())
                and preview_id.strip() == active_preview_id.strip()
            ):
                return None

            template_base = preview_payload.get("termination_arguments_template")
            if not isinstance(template_base, dict) or not template_base:
                template_base = {
                    "confirmed": True,
                    "exempt_choice": "redeem_with_exemption",
                    "taxable_choice": "annuity",
                }
            template_base = dict(template_base)
            template_base.pop("approval_id", None)
            template_base.pop("preview_id", None)

            text = (original_user_msg or "").strip()
            lowered = text.lower()

            overrides: dict = {}

            all_to_annuity_tokens = ("הכל", "כולם", "שניהם")
            has_all_to_annuity = any(t in lowered for t in all_to_annuity_tokens) and (
                ("קצבה" in lowered) or ("רצף" in lowered) or ("annuity" in lowered)
            )
            if has_all_to_annuity:
                overrides["exempt_choice"] = "annuity"
                overrides["taxable_choice"] = "annuity"
            else:
                try:
                    overrides = extract_process_termination_choice_overrides(text)
                except Exception:
                    overrides = {}

            parsed_ok = isinstance(overrides, dict) and (
                isinstance(overrides.get("exempt_choice"), str)
                or isinstance(overrides.get("taxable_choice"), str)
            )
            logger.info(
                "termination_alternative: parsed=%s overrides=%s",
                bool(parsed_ok),
                overrides if isinstance(overrides, dict) else {},
            )

            if not parsed_ok:
                msg = (
                    "לא הבנתי בדיוק מה אתה רוצה לעשות עם הפיצויים. "
                    "כתוב בצורה מפורשת מה לעשות עם הפטור ומה לעשות עם החייב.\n\n"
                    "דוגמאות:\n"
                    "- הכל לקצבה\n"
                    "- פטור לקצבה, חייב לקצבה\n"
                    "- פטור למשיכה בפטור, חייב לקצבה"
                )
                return StreamingResponse(
                    iter([msg]),
                    media_type="text/plain; charset=utf-8",
                )

            new_template = dict(template_base)
            new_template.update({k: v for k, v in overrides.items() if k in {"exempt_choice", "taxable_choice"}})
            new_template["confirmed"] = True

            exempt_choice = str(new_template.get("exempt_choice") or "").strip()
            taxable_choice = str(new_template.get("taxable_choice") or "").strip()

            def _choice_he(choice: str, *, is_exempt: bool) -> str:
                if choice == "annuity":
                    return "המרה לרצף קצבה (annuity)"
                if choice == "redeem_with_exemption":
                    return "משיכה הונית בפטור (redeem_with_exemption)"
                if choice == "redeem_no_exemption":
                    return "משיכה הונית ללא פטור (redeem_no_exemption)"
                return choice or ("(לא נבחר)" if is_exempt else "(לא נבחר)")

            preview_text = (
                "אני עומד לבצע עכשיו עזיבת עבודה לפי הבחירה שביקשת:\n"
                f"- החלק הפטור: {_choice_he(exempt_choice, is_exempt=True)}\n"
                f"- החלק החייב: {_choice_he(taxable_choice, is_exempt=False)}\n\n"
                "לאשר את התכנית הזו?\n\nאפשרויות:\nכן\nלא"
            )

            payload_out = dict(preview_payload)
            payload_out.pop("preview_id", None)
            payload_out.pop("created_at", None)
            payload_out.pop("expires_at", None)
            payload_out["termination_arguments_template"] = new_template
            payload_out["awaiting_user_confirmation"] = True
            payload_out["approved"] = False
            payload_out["declined"] = False
            payload_out["used"] = False
            try:
                payload_out["plan"] = {
                    "exempt_choice": exempt_choice,
                    "taxable_choice": taxable_choice,
                }
            except Exception:
                pass

            try:
                store_current_employer_termination_plan_preview(
                    db=db,
                    client_id=int(client_id_local),
                    payload=payload_out,
                )
            except Exception:
                pass

            return StreamingResponse(
                iter([preview_text]),
                media_type="text/plain; charset=utf-8",
            )

        termination_alternative_response = _maybe_handle_termination_alternative_choice()
        if termination_alternative_response is not None:
            return termination_alternative_response, plan_phrase_detected, None, None

    pending_plan = load_pending_plan_target_marker_direct(
        session=db,
        client_id=client_id,
    )

    target_net = extract_target_net_ils(original_user_msg)

    pending_plan_marker_response = maybe_handle_pending_plan_target_marker_flow(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
        client_id=client_id,
        pending_plan=pending_plan,
        target_net=target_net,
        delete_marker=delete_marker,
        sanitize_user_visible_text=sanitize_user_visible_text,
        ClientModel=ClientModel,
        infer_retirement_age_for_plan_args=infer_retirement_age_for_plan_args,
        execute_tool_call=execute_tool_call,
        get_tool_display_name_hebrew=get_tool_display_name_hebrew,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
    )
    if pending_plan_marker_response is not None:
        return pending_plan_marker_response, plan_phrase_detected, None, None

    try:
        messages, computed_data = prepare_messages_with_context(request=request, db=db)
    except Exception:
        messages = list(request.messages or [])
        computed_data = None

    reports_route_response = maybe_route_to_reports_page(
        request=request,
        original_user_msg=original_user_msg,
    )
    if reports_route_response is not None:
        return reports_route_response, plan_phrase_detected, messages, computed_data

    approved_json_exec_response = maybe_handle_user_approved_json_exec(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
    )
    if approved_json_exec_response is not None:
        return approved_json_exec_response, plan_phrase_detected, messages, computed_data

    return None, plan_phrase_detected, messages, computed_data
