import json
from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatResponse


def _handle_tool_call_step(
    *,
    request,
    db,
    request_id: str,
    logger,
    log_llm_event_fn,
    raw_reply: str,
    original_user_msg: str | None,
    messages: list[ChatMessage],
    current_pension_portfolio,
    is_qa_mode: bool,
    no_tools_requested: bool,
    is_doc_request: bool,
    is_cashflow_request: bool,
    is_comparison_request: bool,
    is_net_request: bool,
    is_portfolio_analysis: bool,
    analysis_default_retirement_age,
    force_max_exemption: bool,
    wants_ignore_blocked: bool,
    explicit_termination: bool,
    termination_change: bool,
    termination_already_executed: bool,
    wants_execute_target_plan: bool,
    wants_fixation_execute: bool,
    final_reply: str,
    forced_user_prefix: str,
    qa_summary_required: bool,
    report_open_path: str | None,
    forced_fixation_chain_done: bool,
    current_step: int,
    computed_data,
 ):
    from app.services.llm_chat.numeric_provenance import extract_numeric_matches
    from app.utils.trace_context import get_current_trace_id
    if "###TOOL_CALL###" not in raw_reply:
        return (
            False,
            False,
            None,
            original_user_msg,
            current_pension_portfolio,
            final_reply,
            forced_user_prefix,
            qa_summary_required,
            report_open_path,
            forced_fixation_chain_done,
            current_step,
        )

    from app.models.client import Client
    from app.services.llm_chat.chat_orchestration_helpers import (
        build_approval_request_ui_action,
        build_forced_document_reply,
        build_pension_portfolio_update_after_transform,
        get_gross_for_tax_chaining,
        run_tax_projection_autochain,
        store_latest_target_pension_plan,
        store_pending_approval_request,
        maybe_clear_pension_portfolio_after_transform,
    )
    from app.services.llm_chat.message_utils import (
        extract_target_pension_from_message,
        find_last_user_message,
        was_tool_call_previously_approved,
    )
    from app.services.llm_chat.orchestration_utils import (
        apply_max_exemption_if_requested,
        build_tax_result_system_message_for_chat,
        build_tool_call_message_content,
        build_tool_result_system_message_for_chat,
        format_tool_output_for_user_stream,
        is_tax_documents_request,
        normalize_retirement_date_if_jan1_placeholder,
        parse_tool_call_from_reply,
        sanitize_user_visible_text,
        validate_tool_call_protocol_for_execution,
    )
    from app.services.llm_chat.chat_orchestration_parts.chat_helpers import (
        _extract_target_monthly_pension,
        _infer_target_is_net,
        _is_aggregate_account,
        _user_requested_target_pension_plan,
    )
    from app.services.llm_chat.chat_orchestration_parts.chat_top_level_helpers import (
        _load_latest_pension_portfolio_snapshot_models,
    )
    from app.services.llm_chat.chat_orchestration_parts.tool_calling import _execute_tool_call
    from app.services.llm_chat.orchestration_utils import (
        build_partial_pension_transform_accounts_from_portfolio,
        build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
        build_portfolio_wide_component_transform_accounts_from_portfolio,
        build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
        build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
        build_targeted_component_transform_accounts_from_portfolio,
        build_transform_accounts_from_portfolio,
        parse_partial_pension_conversion_request,
        parse_portfolio_wide_after_settlement_severance_conversion_request,
        parse_portfolio_wide_component_conversion_request,
        parse_portfolio_wide_education_fund_conversion_request,
        parse_portfolio_wide_prev_employers_severance_conversion_request,
        parse_targeted_component_conversion_request,
    )
    from app.services.llm_chat.orchestration_utils import (
        is_cashflow_missing_income_followup,
        is_net_pension_request,
        is_pension_commutation_request,
        is_process_termination_request,
        is_transform_request,
    )

    tool_part_for_log = raw_reply.split("###TOOL_CALL###", 1)[1].strip()

    try:
        parsed = parse_tool_call_from_reply(raw_reply)
        if parsed is None:
            return (
                True,
                True,
                None,
                original_user_msg,
                current_pension_portfolio,
                final_reply,
                forced_user_prefix,
                qa_summary_required,
                report_open_path,
                forced_fixation_chain_done,
                current_step,
            )

        text_part, tool_call_data = parsed
        tool_name = tool_call_data.get("name")
        tool_args = tool_call_data.get("arguments", {})

        if tool_name == "RUN_RETIREMENT_SCENARIOS" and is_portfolio_analysis:
            if not isinstance(tool_args, dict):
                tool_args = {}
            if analysis_default_retirement_age is not None:
                tool_args["retirement_age"] = analysis_default_retirement_age

        if _user_requested_target_pension_plan(original_user_msg) and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש לבנות תכנית יעד קצבה (מתווה להשגת יעד חודשי). "
                        "אסור להפעיל RUN_RETIREMENT_CASHFLOW_ANALYSIS בהקשר זה. "
                        "כעת אל תחזיר TOOL_CALL. במקום זאת החזר TOOL_CALL ל-BUILD_TARGET_PENSION_PLAN בלבד "
                        "עם target_monthly_pension כפי שמופיע בבקשת המשתמש."
                    ),
                )
            )
            current_step += 1
            return (
                True,
                False,
                None,
                original_user_msg,
                current_pension_portfolio,
                final_reply,
                forced_user_prefix,
                qa_summary_required,
                report_open_path,
                forced_fixation_chain_done,
                current_step,
            )

        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            if not isinstance(tool_args, dict):
                tool_args = {}
            user_wants_plan = _user_requested_target_pension_plan(original_user_msg)
            raw_target = tool_args.get("target_monthly_pension")
            target_ok = False
            try:
                target_ok = float(raw_target or 0) > 0
            except Exception:
                target_ok = False

            if user_wants_plan:
                extracted_target = _extract_target_monthly_pension(original_user_msg)
                if extracted_target and extracted_target > 0:
                    tool_args["target_monthly_pension"] = extracted_target
                    try:
                        target_ok = float(extracted_target) > 0
                    except Exception:
                        target_ok = False

                tool_args["target_is_net"] = _infer_target_is_net(original_user_msg)

            if (not user_wants_plan) or (not target_ok):
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "אזהרה: אסור לבצע BUILD_TARGET_PENSION_PLAN כאשר המשתמש ביקש ניתוח/אפשרויות משיכה בלבד, "
                            "או כאשר לא סופק יעד קצבה חודשי מספרי מפורש. "
                            "כעת אל תחזיר TOOL_CALL. במקום זאת: "
                            "(1) אם המשתמש ביקש ניתוח/אפשרויות משיכה – השב טקסטואלית על סמך טבלת המוצרים והחוקים; "
                            "(2) אם המשתמש מבקש תכנית יעד קצבה – שאל שאלה אחת: מה יעד הקצבה החודשי במספר (למשל 20000)."
                        ),
                    )
                )
                current_step += 1
                return (
                    True,
                    False,
                    None,
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

        if tool_name == "PROCESS_TERMINATION" and wants_ignore_blocked:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש במפורש להתעלם מיתרות חסומות/עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                        "אסור לבצע עזיבת עבודה. כעת המשך ללא TOOL_CALL ובחר כלי אחר שמתאים לבקשה."
                    ),
                )
            )
            current_step += 1
            return (
                True,
                False,
                None,
                original_user_msg,
                current_pension_portfolio,
                final_reply,
                forced_user_prefix,
                qa_summary_required,
                report_open_path,
                forced_fixation_chain_done,
                current_step,
            )

        if tool_name == "PROCESS_TERMINATION" and (not explicit_termination):
            allow_change_after_execution = bool(termination_already_executed and termination_change)
            if not allow_change_after_execution:
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "אזהרה: אסור לבצע עזיבת עבודה ללא בקשה מפורשת לביצוע עזיבת עבודה/פיצויים. "
                            "כעת המשך ללא TOOL_CALL ותן תשובה טקסטואלית בלבד או שאל שאלת הבהרה."
                        ),
                    )
                )
                current_step += 1
                return (
                    True,
                    False,
                    None,
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            if (
                (not wants_ignore_blocked)
                and (not is_doc_request)
                and (not is_qa_mode)
                and is_process_termination_request(original_user_msg)
            ):
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "אזהרה: המשתמש ביקש עזיבת עבודה/פיצויים/מענק. "
                            "אסור לבצע TRANSFORM_FUNDS_TO_ASSETS. "
                            "כעת אל תחזיר TOOL_CALL להמרת תיק. "
                            "במקום זאת החזיר TOOL_CALL ל-PROCESS_TERMINATION בלבד (עם confirmed=true)."
                        ),
                    )
                )
                current_step += 1
                return (
                    True,
                    False,
                    None,
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

            if (
                (not is_doc_request)
                and (not is_qa_mode)
                and is_pension_commutation_request(original_user_msg)
            ):
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "אזהרה: המשתמש ביקש היוון קצבה. "
                            "אסור לבצע TRANSFORM_FUNDS_TO_ASSETS. "
                            "כעת אל תחזיר TOOL_CALL להמרת תיק. "
                            "במקום זאת החזיר TOOL_CALL ל-EXECUTE_PENSION_COMMUTATION בלבד (עם confirmed=true) "
                            "ועם pension_fund_id, commutation_amount, commutation_date, commutation_type."
                        ),
                    )
                )
                current_step += 1
                return (
                    True,
                    False,
                    None,
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

            if (not current_pension_portfolio) and request.client_id is not None:
                loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    current_pension_portfolio, _effective_snapshot_at = loaded

            if isinstance(current_pension_portfolio, list) and current_pension_portfolio:
                targeted_req = parse_targeted_component_conversion_request(original_user_msg)
                if targeted_req is not None:
                    acc_num, fields, conv_type = targeted_req
                    targeted_accounts = build_targeted_component_transform_accounts_from_portfolio(
                        pension_portfolio=current_pension_portfolio,
                        account_number=acc_num,
                        fields=fields,
                        conversion_type=conv_type,
                    )
                    if targeted_accounts:
                        tool_args["accounts"] = targeted_accounts
                        tool_args["use_provided_accounts_only"] = True
                else:
                    prev_sev_req = parse_portfolio_wide_prev_employers_severance_conversion_request(original_user_msg)
                    if prev_sev_req is not None:
                        _fields, conv_type = prev_sev_req
                        if conv_type != "blocked":
                            portfolio_accounts = build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio(
                                pension_portfolio=current_pension_portfolio,
                                conversion_type=conv_type,
                            )
                            if portfolio_accounts:
                                tool_args["accounts"] = portfolio_accounts
                                tool_args["use_provided_accounts_only"] = True
                    else:
                        after_settle_req = parse_portfolio_wide_after_settlement_severance_conversion_request(original_user_msg)
                        if after_settle_req is not None:
                            _fields, conv_type = after_settle_req
                            portfolio_accounts = build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio(
                                pension_portfolio=current_pension_portfolio,
                                conversion_type=conv_type,
                            )
                            if portfolio_accounts:
                                tool_args["accounts"] = portfolio_accounts
                                tool_args["use_provided_accounts_only"] = True
                        else:
                            portfolio_wide_req = parse_portfolio_wide_component_conversion_request(original_user_msg)
                            if portfolio_wide_req is not None:
                                fields, conv_type = portfolio_wide_req
                                portfolio_accounts = build_portfolio_wide_component_transform_accounts_from_portfolio(
                                    pension_portfolio=current_pension_portfolio,
                                    fields=fields,
                                    conversion_type=conv_type,
                                )
                                if portfolio_accounts:
                                    tool_args["accounts"] = portfolio_accounts
                                    tool_args["use_provided_accounts_only"] = True
                            else:
                                edu_req = parse_portfolio_wide_education_fund_conversion_request(original_user_msg)
                                if edu_req is not None:
                                    _fields, conv_type = edu_req
                                    edu_accounts = build_portfolio_wide_education_fund_transform_accounts_from_portfolio(
                                        pension_portfolio=current_pension_portfolio,
                                        conversion_type=conv_type,
                                    )
                                    if edu_accounts:
                                        tool_args["accounts"] = edu_accounts
                                        tool_args["use_provided_accounts_only"] = True

            explicit_transform = is_transform_request(original_user_msg)
            if (not is_doc_request) and (not is_qa_mode) and (not explicit_transform):
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "אזהרה: אסור לבצע TRANSFORM_FUNDS_TO_ASSETS ללא בקשה מפורשת להמרה, "
                            "או במסגרת בקשת דוח/QA. כעת המשך ללא TOOL_CALL ותן תשובה טקסטואלית בלבד "
                            "או בחר כלי אחר שמתאים לבקשה."
                        ),
                    )
                )
                current_step += 1
                return (
                    True,
                    False,
                    None,
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

            if (not current_pension_portfolio) and request.client_id is not None:
                loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
                if loaded is not None:
                    current_pension_portfolio, _effective_snapshot_at = loaded

            partial_req = parse_partial_pension_conversion_request(original_user_msg)
            if partial_req is not None:
                acc_num, amount = partial_req
                partial_accounts = build_partial_pension_transform_accounts_from_portfolio(
                    pension_portfolio=current_pension_portfolio,
                    account_number=acc_num,
                    amount=amount,
                )
                if not partial_accounts:
                    messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                f"אזהרה: המשתמש ביקש המרה חלקית לחשבון {acc_num} אך החשבון לא נמצא בתיק. "
                                "אסור לבצע המרת תיק מלאה. כעת אל תחזיר TOOL_CALL ותן תשובה טקסטואלית בלבד."
                            ),
                        )
                    )
                    current_step += 1
                    return (
                        True,
                        False,
                        None,
                        original_user_msg,
                        current_pension_portfolio,
                        final_reply,
                        forced_user_prefix,
                        qa_summary_required,
                        report_open_path,
                        forced_fixation_chain_done,
                        current_step,
                    )
                if not isinstance(tool_args, dict):
                    tool_args = {}
                tool_args["accounts"] = partial_accounts
                tool_args["use_provided_accounts_only"] = True
            else:
                targeted_req = parse_targeted_component_conversion_request(original_user_msg)
                if targeted_req is not None:
                    acc_num, fields, conv_type = targeted_req
                    targeted_accounts = build_targeted_component_transform_accounts_from_portfolio(
                        pension_portfolio=current_pension_portfolio,
                        account_number=acc_num,
                        fields=fields,
                        conversion_type=conv_type,
                    )
                    if not targeted_accounts:
                        messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    f"אזהרה: המשתמש ביקש המרה ממוקדת לחשבון {acc_num} אך לא נמצאו רכיבים מתאימים בתיק. "
                                    "אסור לבצע המרת תיק מלאה. כעת אל תחזיר TOOL_CALL ותן תשובה טקסטואלית בלבד."
                                ),
                            )
                        )
                        current_step += 1
                        return (
                            True,
                            False,
                            None,
                            original_user_msg,
                            current_pension_portfolio,
                            final_reply,
                            forced_user_prefix,
                            qa_summary_required,
                            report_open_path,
                            forced_fixation_chain_done,
                            current_step,
                        )
                    if not isinstance(tool_args, dict):
                        tool_args = {}
                    tool_args["accounts"] = targeted_accounts
                    tool_args["use_provided_accounts_only"] = True
                else:
                    derived_accounts = build_transform_accounts_from_portfolio(current_pension_portfolio)
                    if not derived_accounts:
                        messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: TRANSFORM_FUNDS_TO_ASSETS דורש רשימת accounts תקינה. "
                                    "אין accounts ואין pension_portfolio שממנו ניתן לגזור accounts. "
                                    "כעת אל תחזיר TOOL_CALL."
                                ),
                            )
                        )
                        current_step += 1
                        return (
                            True,
                            False,
                            None,
                            original_user_msg,
                            current_pension_portfolio,
                            final_reply,
                            forced_user_prefix,
                            qa_summary_required,
                            report_open_path,
                            forced_fixation_chain_done,
                            current_step,
                        )

                    tool_args_accounts = tool_args.get("accounts") if isinstance(tool_args, dict) else None
                    if not isinstance(tool_args, dict):
                        tool_args = {}
                    if not (isinstance(tool_args_accounts, list) and tool_args_accounts):
                        tool_args["accounts"] = derived_accounts
                    else:
                        if any(_is_aggregate_account(acc) for acc in tool_args_accounts if isinstance(acc, dict)):
                            tool_args["accounts"] = derived_accounts
                        else:
                            by_number = {
                                (acc.get("account_number") or acc.get("מספר_חשבון") or "").strip(): acc
                                for acc in derived_accounts
                                if isinstance(acc, dict)
                            }
                            enriched: list[dict[str, Any]] = []
                            for acc in tool_args_accounts:
                                if not isinstance(acc, dict):
                                    continue
                                num = (acc.get("account_number") or acc.get("מספר_חשבון") or "").strip()
                                base = by_number.get(num) if num else None
                                if base is None:
                                    continue
                                merged = dict(base or {})
                                merged.update(acc)
                                enriched.append(merged)
                            tool_args["accounts"] = enriched or derived_accounts

            if wants_ignore_blocked:
                tool_args["ignore_blocked_balances"] = True
                tool_args["skip_non_convertible_accounts"] = True

        if no_tools_requested:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                        "אסור לבצע TOOL_CALL. החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר, ללא כלים."
                    ),
                )
            )
            current_step += 1
            return (
                True,
                False,
                None,
                original_user_msg,
                current_pension_portfolio,
                final_reply,
                forced_user_prefix,
                qa_summary_required,
                report_open_path,
                forced_fixation_chain_done,
                current_step,
            )

        if is_doc_request and not is_qa_mode:
            allowed_doc_tools = {
                "GENERATE_FULL_REPORT",
                "GENERATE_TAX_DEDUCTION_DOCUMENTS",
                "TRANSFORM_FUNDS_TO_ASSETS",
            }

            if tool_name not in allowed_doc_tools:
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "אזהרה: המשתמש ביקש דוח/מסמך להורדה (ללא QA). "
                            "אסור לבצע פעולות שמשנות נתונים או תהליכים אחרים. "
                            "כעת עליך לבחור רק אחד מהכלים המותרים: "
                            + ", ".join(sorted(allowed_doc_tools))
                            + "."
                        ),
                    )
                )
                current_step += 1
                return (
                    True,
                    False,
                    None,
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

        if is_qa_mode and tool_name not in {
            "GET_PENSION_PRODUCTS",
            "TRANSFORM_FUNDS_TO_ASSETS",
            "GENERATE_FULL_REPORT",
        }:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש בדיקת מערכת (QA). "
                        "במצב QA אסור להפעיל כלים שמשנים נתונים או עוסקים בתהליכים אחרים. "
                        "כעת עליך לבחור רק אחד מהכלים: GET_PENSION_PRODUCTS, TRANSFORM_FUNDS_TO_ASSETS, GENERATE_FULL_REPORT."
                    ),
                )
            )
            current_step += 1
            return (
                True,
                False,
                None,
                original_user_msg,
                current_pension_portfolio,
                final_reply,
                forced_user_prefix,
                qa_summary_required,
                report_open_path,
                forced_fixation_chain_done,
                current_step,
            )

        ok, error_msg = validate_tool_call_protocol_for_execution(raw_reply)
        if not ok:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: אסור לבצע TOOL_CALL כי חסרים שלבי החובה/הפרוטוקול לא תקין. "
                        "כעת החזר רק בלוקים בפורמט: "
                        '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                    ),
                )
            )
            current_step += 1
            return (
                True,
                False,
                None,
                original_user_msg,
                current_pension_portfolio,
                final_reply,
                forced_user_prefix,
                qa_summary_required,
                report_open_path,
                forced_fixation_chain_done,
                current_step,
            )

        log_llm_event_fn(
            request_id=request_id,
            event_type="tool_call",
            payload={"name": tool_name, "arguments": tool_args},
            client_id=request.client_id,
        )

        apply_max_exemption_if_requested(
            tool_name=tool_name,
            tool_args=tool_args,
            force_max_exemption=force_max_exemption,
        )

        if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
            date_str = tool_args.get("retirement_date")
            if isinstance(date_str, str) and date_str.strip() and request.client_id is not None:
                client = db.query(Client).filter(Client.id == request.client_id).first()
                birth_date = getattr(client, "birth_date", None) if client else None
                if birth_date is not None:
                    tool_args["retirement_date"] = normalize_retirement_date_if_jan1_placeholder(
                        retirement_date=date_str.strip(),
                        birth_date=birth_date,
                        user_message=original_user_msg,
                    )

        if text_part:
            messages.append(ChatMessage(role="assistant", content=text_part))

        tool_msg_content = build_tool_call_message_content(tool_call_data, ensure_ascii=True)
        messages.append(ChatMessage(role="assistant", content=tool_msg_content))

        if tool_name in {"EXECUTE_PENSION_COMMUTATION", "SUBMIT_TAX_COMMUTATION"}:
            already_approved = was_tool_call_previously_approved(
                request.messages,
                tool_name=tool_name,
                tool_args=tool_args if isinstance(tool_args, dict) else {},
            )
            if not already_approved:
                try:
                    store_pending_approval_request(
                        db=db,
                        client_id=request.client_id,
                        tool_name=tool_name,
                        tool_args=tool_args if isinstance(tool_args, dict) else {},
                    )
                except Exception:
                    pass

                reason = "נדרש אישור לפני ביצוע פעולה במערכת."
                if tool_name == "EXECUTE_PENSION_COMMUTATION":
                    reason = "נדרש אישור לפני ביצוע היוון קצבה במערכת."
                if tool_name == "SUBMIT_TAX_COMMUTATION":
                    reason = "נדרש אישור לפני הגשת/ביצוע קיבוע/פריסה במערכת."

                return (
                    True,
                    True,
                    ChatResponse(
                        reply=build_approval_request_ui_action(
                            tool_name=tool_name,
                            tool_args=tool_args if isinstance(tool_args, dict) else {},
                            reason=reason,
                            risk_level="high",
                            rag_sources=None,
                        ),
                        computed_data=computed_data,
                    ),
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

        tool_result = _execute_tool_call(
            tool_name,
            tool_args,
            request.client_id,
            db,
            pension_portfolio=current_pension_portfolio,
            force_max_exemption=force_max_exemption,
            agent_reply=raw_reply,
            user_approved=was_tool_call_previously_approved(
                request.messages,
                tool_name=tool_name,
                tool_args=tool_args if isinstance(tool_args, dict) else {},
            ),
            request_id=request_id,
        )

        if tool_name == "BUILD_TARGET_PENSION_PLAN" and request.client_id is not None:
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=tool_result,
                )
            except Exception:
                pass

        if (
            isinstance(tool_result, str)
            and "###UI_ACTION###" in tool_result
            and "approval_request" in tool_result
        ):
            final_reply = tool_result
            return (
                True,
                True,
                None,
                original_user_msg,
                current_pension_portfolio,
                final_reply,
                forced_user_prefix,
                qa_summary_required,
                report_open_path,
                forced_fixation_chain_done,
                current_step,
            )

        portfolio_update_marker = build_pension_portfolio_update_after_transform(
            tool_name=tool_name,
            tool_result=tool_result,
            tool_args=tool_args,
            current_pension_portfolio=current_pension_portfolio,
        )
        if portfolio_update_marker:
            forced_user_prefix += portfolio_update_marker

        if is_qa_mode and tool_name == "GENERATE_FULL_REPORT":
            qa_summary_required = True
            try:
                parsed_tool = json.loads(tool_result)
                report_open_path = parsed_tool.get("open_path")
            except Exception:
                report_open_path = report_open_path

        current_pension_portfolio = maybe_clear_pension_portfolio_after_transform(
            tool_name=tool_name,
            tool_result=tool_result,
            current_pension_portfolio=current_pension_portfolio,
        )

        log_llm_event_fn(
            request_id=request_id,
            event_type="tool_result",
            payload={"tool_name": tool_name, "result": tool_result},
            client_id=request.client_id,
        )

        forced_document_reply = build_forced_document_reply(
            tool_name=tool_name,
            tool_result=tool_result,
        )

        if forced_document_reply:
            if is_doc_request and not is_qa_mode:
                final_reply = forced_document_reply
                return (
                    True,
                    True,
                    None,
                    original_user_msg,
                    current_pension_portfolio,
                    final_reply,
                    forced_user_prefix,
                    qa_summary_required,
                    report_open_path,
                    forced_fixation_chain_done,
                    current_step,
                )

            forced_user_prefix += forced_document_reply.strip() + "\n\n"
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "המסמך הופק בהצלחה (UI_ACTION כבר נשלח למשתמש). "
                        "כעת עליך להמשיך ולספק תשובת סיכום טקסטואלית מלאה בהתאם לבקשה (למשל QA / PASS/FAIL), "
                        "ולהזכיר בבירור את open_path או קישור הדוח."
                    ),
                )
            )

        result_msg = build_tool_result_system_message_for_chat(tool_name, tool_result)
        messages.append(ChatMessage(role="system", content=result_msg))

        original_user_msg = find_last_user_message(request.messages)
        is_net = is_net_pension_request(original_user_msg)

        gross_for_tax = get_gross_for_tax_chaining(
            is_net=is_net,
            tool_name=tool_name,
            tool_result=tool_result,
        )

        logger.info(
            "🔗 Checking Force Chaining: Tool=%s, IsNet=%s, GrossForTax=%s, Msg='%s'",
            tool_name,
            is_net,
            gross_for_tax,
            original_user_msg[:50],
        )

        tax_result = run_tax_projection_autochain(
            gross_for_tax=gross_for_tax,
            execute_tool_call_fn=lambda name, args: _execute_tool_call(
                name,
                args,
                request.client_id,
                db,
                pension_portfolio=current_pension_portfolio,
                force_max_exemption=force_max_exemption,
                request_id=request_id,
            ),
        )
        if tax_result is not None:
            logger.info(
                "🔗 Force Chaining: Running GET_TAX_PROJECTION with gross=%s",
                gross_for_tax,
            )
            tax_msg = build_tax_result_system_message_for_chat(tax_result)
            messages.append(ChatMessage(role="system", content=tax_msg))
            forced_user_prefix += "🔧 **פלט כלי (הערכת מס - שרשור אוטומטי):**\n" + tax_result + "\n\n"

        if False and (
            (not forced_fixation_chain_done)
            and tool_name in {"TRANSFORM_FUNDS_TO_ASSETS", "PROCESS_TERMINATION"}
        ):
            user_msg_for_chain = find_last_user_message(request.messages) or ""
            user_wants_target_plan = _user_requested_target_pension_plan(user_msg_for_chain)
            if user_wants_target_plan and _infer_target_is_net(user_msg_for_chain):
                target_val = None
                try:
                    target_val = float(extract_target_pension_from_message(user_msg_for_chain) or 0)
                except Exception:
                    target_val = None
                if target_val and target_val > 0:
                    fixation_result = _execute_tool_call(
                        "CALCULATE_FIXATION_OF_RIGHTS",
                        {"save_result": True},
                        request.client_id,
                        db,
                        pension_portfolio=current_pension_portfolio,
                        force_max_exemption=False,
                        agent_reply=None,
                        user_approved=True,
                        request_id=request_id,
                    )
                    messages.append(
                        ChatMessage(
                            role="system",
                            content=build_tool_result_system_message_for_chat(
                                "CALCULATE_FIXATION_OF_RIGHTS",
                                fixation_result,
                            ),
                        )
                    )
                    forced_user_prefix += (
                        "🔧 **פלט כלי (קיבוע זכויות - שרשור חובה):**\n"
                        + sanitize_user_visible_text(
                            format_tool_output_for_user_stream(
                                "CALCULATE_FIXATION_OF_RIGHTS",
                                fixation_result,
                            )
                        )
                        + "\n\n"
                    )

                    plan_args = {
                        "target_monthly_pension": float(target_val),
                        "target_is_net": True,
                    }
                    plan_result = _execute_tool_call(
                        "BUILD_TARGET_PENSION_PLAN",
                        plan_args,
                        request.client_id,
                        db,
                        pension_portfolio=current_pension_portfolio,
                        force_max_exemption=False,
                        agent_reply=None,
                        user_approved=True,
                        request_id=request_id,
                    )
                    messages.append(
                        ChatMessage(
                            role="system",
                            content=build_tool_result_system_message_for_chat(
                                "BUILD_TARGET_PENSION_PLAN",
                                plan_result,
                            ),
                        )
                    )
                    forced_user_prefix += (
                        "🔧 **פלט כלי (בניית תכנית קצבה - אחרי קיבוע זכויות):**\n"
                        + sanitize_user_visible_text(
                            format_tool_output_for_user_stream(
                                "BUILD_TARGET_PENSION_PLAN",
                                plan_result,
                            )
                        )
                        + "\n\n"
                    )

                    gross_for_tax_after = get_gross_for_tax_chaining(
                        is_net=True,
                        tool_name="BUILD_TARGET_PENSION_PLAN",
                        tool_result=plan_result,
                    )
                    tax_after = run_tax_projection_autochain(
                        gross_for_tax=gross_for_tax_after,
                        execute_tool_call_fn=lambda name, args: _execute_tool_call(
                            name,
                            args,
                            request.client_id,
                            db,
                            pension_portfolio=current_pension_portfolio,
                            force_max_exemption=False,
                            agent_reply=None,
                            user_approved=True,
                            request_id=request_id,
                        ),
                    )
                    if tax_after is not None:
                        messages.append(
                            ChatMessage(
                                role="system",
                                content=build_tax_result_system_message_for_chat(tax_after),
                            )
                        )
                        forced_user_prefix += (
                            "🔧 **פלט כלי (הערכת מס - אחרי קיבוע זכויות):**\n" + tax_after + "\n\n"
                        )

                    forced_fixation_chain_done = True

        current_step += 1
        return (
            True,
            False,
            None,
            original_user_msg,
            current_pension_portfolio,
            final_reply,
            forced_user_prefix,
            qa_summary_required,
            report_open_path,
            forced_fixation_chain_done,
            current_step,
        )

    except json.JSONDecodeError:
        logger.error("Failed to parse TOOL_CALL JSON: %s", tool_part_for_log)
        messages.append(
            ChatMessage(
                role="system",
                content="Error: Invalid JSON in TOOL_CALL. Please try again.",
            )
        )

        current_step += 1
        return (
            True,
            False,
            None,
            original_user_msg,
            current_pension_portfolio,
            final_reply,
            forced_user_prefix,
            qa_summary_required,
            report_open_path,
            forced_fixation_chain_done,
            current_step,
        )


def _handle_no_tool_call_step(
    *,
    request,
    db,
    request_id: str,
    logger,
    log_llm_event_fn,
    raw_reply: str,
    original_user_msg: str | None,
    messages: list[ChatMessage],
    is_qa_mode: bool,
    no_tools_requested: bool,
    is_doc_request: bool,
    is_cashflow_request: bool,
    is_comparison_request: bool,
    is_net_request: bool,
    forced_user_prefix: str,
    final_reply: str,
    current_step: int,
 ):
    from app.models.client import Client
    from app.services.llm_chat.numeric_provenance import extract_numeric_matches
    from app.services.llm_chat.numeric_provenance import validate_reply_numeric_provenance
    from app.services.llm_chat.orchestration_utils import (
        compute_default_retirement_date_for_tool_call,
        is_tax_documents_request,
    )
    from app.utils.trace_context import get_current_trace_id
    from app.services.llm_chat.chat_orchestration_parts.chat_helpers import _user_requested_target_pension_plan
    from app.services.llm_chat.message_utils import find_last_user_message
    from app.services.llm_chat.orchestration_utils import is_net_pension_request

    has_tool_results = any(
        (m.role == "system")
        and (
            ("Tool Result (" in (m.content or ""))
            or ("פלט כלי (" in (m.content or ""))
            or ("🔧 **פלט כלי" in (m.content or ""))
        )
        for m in messages
    )

    user_msg_for_default_date = find_last_user_message(request.messages) or ""
    birth_date_for_default_date = None
    gender_for_default_date = None
    if request.client_id is not None:
        client = db.query(Client).filter(Client.id == request.client_id).first()
        birth_date_for_default_date = getattr(client, "birth_date", None) if client else None
        gender_for_default_date = getattr(client, "gender", None) if client else None
    default_retirement_date = compute_default_retirement_date_for_tool_call(
        birth_date=birth_date_for_default_date,
        gender=gender_for_default_date,
        user_message=user_msg_for_default_date,
    )

    if is_cashflow_request and (not no_tools_requested) and (not has_tool_results):
        if _user_requested_target_pension_plan(user_msg_for_default_date):
            warning_msg = (
                "אזהרה: המשתמש ביקש מתווה/תכנית ליעד קצבה עם מספר. אסור לענות ללא הרצת הכלי הייעודי. "
                "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוקים בפורמט "
                '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "BUILD_TARGET_PENSION_PLAN", "arguments": {"target_monthly_pension": 28000}} ללא טקסט נוסף.'
            )
            messages.append(ChatMessage(role="system", content=warning_msg))
            current_step += 1
            return True, False, final_reply, current_step
        warning_msg = (
            "אזהרה: אסור לך לענות על בקשות חישוב/השוואת קצבה ללא הרצת כלים. "
            "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוקים בפורמט "
            f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
        )
        messages.append(ChatMessage(role="system", content=warning_msg))
        current_step += 1
        return True, False, final_reply, current_step

    if is_comparison_request and (not no_tools_requested):
        cashflow_results = sum(
            1
            for m in messages
            if (m.role == "system")
            and (
                ("Tool Result (RUN_RETIREMENT_CASHFLOW_ANALYSIS" in (m.content or ""))
                or ("פלט כלי (ניתוח פרישה" in (m.content or ""))
            )
        )
        if cashflow_results < 2:
            warning_msg = (
                "אזהרה: המשתמש ביקש השוואה בין שני תרחישי פרישה (למשל גיל 68 מול 69). "
                "אסור לספק תשובה מספרית לפני שתי הרצות של RUN_RETIREMENT_CASHFLOW_ANALYSIS (אחת לכל תרחיש). "
                "כעת עליך להחזיר רק בלוקים בפורמט "
                f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
            )
            messages.append(ChatMessage(role="system", content=warning_msg))
            current_step += 1
            return True, False, final_reply, current_step

    if is_net_request and (not no_tools_requested) and (not has_tool_results):
        warning_msg = (
            "אזהרה: אסור לך לענות על שאלות נטו/אחרי מס ללא הרצת כלים. "
            "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
            f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
        )
        messages.append(ChatMessage(role="system", content=warning_msg))
        current_step += 1
        return True, False, final_reply, current_step

    if is_doc_request and not has_tool_results:
        is_tax_doc_request = is_tax_documents_request(original_user_msg)
        doc_tool = "GENERATE_TAX_DEDUCTION_DOCUMENTS" if is_tax_doc_request else "GENERATE_FULL_REPORT"
        warning_msg = (
            "אזהרה: המשתמש ביקש דוח/מסמך להורדה. אסור לך להשיב טקסט חופשי או לטעון שהופק דוח ללא הפעלת כלי GENERATE_* "
            "והחזרת download_url. התשובה האחרונה שלך בוטלה. "
            "כעת עליך להחזיר רק בלוק יחיד בפורמט "
            f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "{doc_tool}", "arguments": {{}}}} ללא טקסט נוסף.'
        )
        messages.append(ChatMessage(role="system", content=warning_msg))
        current_step += 1
        return True, False, final_reply, current_step

    allowed_sources: list[str] = []
    try:
        for msg in (request.messages or []):
            if getattr(msg, "role", None) == "user":
                allowed_sources.append(getattr(msg, "content", "") or "")
    except Exception:
        pass

    try:
        for msg in (messages or []):
            if getattr(msg, "role", None) != "system":
                continue
            content = getattr(msg, "content", "") or ""
            if ("Tool Result (" in content) or ("פלט כלי (" in content) or ("🔧 **פלט כלי" in content):
                allowed_sources.append(content)
    except Exception:
        pass

    if isinstance(forced_user_prefix, str) and forced_user_prefix:
        allowed_sources.append(forced_user_prefix)

    violation = validate_reply_numeric_provenance(
        reply_text=raw_reply,
        allowed_source_texts=allowed_sources,
    )
    if violation is not None:
        trace_id = get_current_trace_id()
        matches = extract_numeric_matches(raw_reply)
        head_preview = raw_reply[:300] if isinstance(raw_reply, str) else ""
        tail_preview = raw_reply[-300:] if isinstance(raw_reply, str) else ""
        try:
            log_llm_event_fn(
                request_id=request_id,
                event_type="numeric_provenance_violation",
                payload={
                    "tokens": list(violation.tokens),
                    "matches": matches,
                    "blocked_preview_head": head_preview,
                    "blocked_preview_tail": tail_preview,
                },
                client_id=request.client_id,
                extra={"endpoint": "non_stream", "trace_id": trace_id},
            )
        except Exception:
            pass
        final_reply = (
            "שגיאה: המערכת חסמה תשובה שכללה מספרים שלא הגיעו מחישוב מערכת. "
            "כדי לקבל מספרים, בקש לבצע חישוב/דוח דרך הכלים של המערכת."
        )
    else:
        final_reply = raw_reply

    return False, True, final_reply, current_step
