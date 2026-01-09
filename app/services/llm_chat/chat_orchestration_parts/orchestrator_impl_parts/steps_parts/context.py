
import json
from dataclasses import dataclass
from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatResponse
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text


from ..steps.messages_prompt import _build_messages_and_prompt
from ..steps.types import _PreparedOrchestrationInputs

def _prepare_orchestration_inputs(
    *,
    request,
    db,
    request_id: str,
    logger,
    log_llm_event_fn,
) -> _PreparedOrchestrationInputs | ChatResponse:
    import importlib

    from app.models.client import Client
    from app.models import CurrentEmployer, EmployerGrant, GrantType
    from app.services.llm_chat.chat_orchestration_parts.chat_helpers import (
        _digits_only,
        _extract_commutation_account_number,
        _fmt_money,
        _infer_target_is_net_explicit,
        _is_ignore_blocked_text,
        _is_target_plan_adjust_followup,
        _is_target_plan_adjust_request,
        _item_to_dict,
        _user_requested_target_pension_plan,
        _user_wants_full_balance,
    )
    from app.services.llm_chat.chat_orchestration_parts.tool_calling import _execute_tool_call
    from app.services.llm_chat.chat_orchestration_helpers import (
        build_approval_request_ui_action,
        build_forced_document_reply,
        build_pension_portfolio_update_after_transform,
        format_transform_result_for_user,
        build_transform_accounts_from_target_plan_payload,
        clear_pending_approval_request,
        load_latest_target_pension_plan,
        load_pending_approval_request,
        store_latest_target_pension_plan,
        store_pending_approval_request,
    )
    from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
    from app.services.llm_chat.message_utils import (
        extract_latest_approval_request,
        extract_latest_target_pension_plan_payload,
        extract_target_pension_from_message,
        extract_user_approval_for_tool_call,
        extract_user_cancel_for_tool_call,
        find_last_user_message,
        is_user_approval_intent_text,
    )
    from app.services.llm_chat.orchestration_utils import (
        build_partial_pension_transform_accounts_from_portfolio,
        build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
        build_portfolio_wide_component_transform_accounts_from_portfolio,
        build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
        build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
        build_transform_accounts_from_portfolio,
        build_targeted_component_transform_accounts_from_portfolio,
        compute_default_retirement_date_for_tool_call,
        extract_desired_monthly_income_from_text,
        extract_process_termination_choice_overrides,
        extract_process_termination_date_override,
        format_tool_output_for_user_stream,
        infer_desired_income_is_net_explicit,
        is_cashflow_missing_income_followup,
        is_data_awareness_request,
        is_document_request,
        is_list_all_financial_entities_request,
        is_max_capital_request,
        is_max_exemption_request,
        is_net_pension_request,
        is_no_termination_request,
        is_no_tools_request,
        is_pension_commutation_request,
        is_portfolio_analysis_request,
        is_portfolio_breakdown_request,
        is_process_termination_request,
        is_qa_request,
        is_retirement_cashflow_request,
        is_retirement_comparison_request,
        is_tax_documents_request,
        is_termination_change_request,
        is_transform_request,
        parse_partial_pension_conversion_request,
        parse_portfolio_wide_after_settlement_severance_conversion_request,
        parse_portfolio_wide_component_conversion_request,
        parse_portfolio_wide_education_fund_conversion_request,
        parse_portfolio_wide_prev_employers_severance_conversion_request,
        parse_targeted_component_conversion_request,
    )

    (
        effective_portfolio,
        effective_snapshot_at,
        messages,
        computed_data,
        original_user_msg,
    ) = _build_messages_and_prompt(request=request, db=db, logger=logger)

    from ..steps.prepare_inputs_parts.case_routing import _set_case_id_safe

    _set_case_id_safe(
        original_user_msg=original_user_msg,
        messages=messages,
        client_id=request.client_id,
    )

    if request.client_id is not None and (
        _is_target_plan_adjust_request(original_user_msg)
        or _is_target_plan_adjust_followup(original_user_msg, request.messages)
    ):
        payload = extract_latest_target_pension_plan_payload(request.messages)
        if payload is None:
            payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
        if not isinstance(payload, dict):
            return ChatResponse(
                reply=(
                    "כדי לתקן את תכנית יעד הקצבה אני צריך תכנית יעד אחרונה קיימת. "
                    "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של <מספר>' (ואפשר לציין ברוטו/נטו)."
                ),
                computed_data=computed_data,
            )

        plan_res = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        raw_target = plan_res.get("target_monthly_pension")
        try:
            target_val = float(raw_target or 0)
        except Exception:
            target_val = 0.0

        explicit_is_net = _infer_target_is_net_explicit(original_user_msg)
        if explicit_is_net is None:
            prev_is_net = payload.get("args", {}).get("target_is_net") if isinstance(payload.get("args"), dict) else None
            prev_mode = "נטו" if prev_is_net is True else "ברוטו"
            return ChatResponse(
                reply=(
                    "כדי לתקן את התכנית צריך להבהיר: היעד שביקשת הוא **ברוטו** או **נטו**?\n\n"
                    f"(התכנית האחרונה נבנתה במצב: {prev_mode})\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '28000 ברוטו'\n"
                    "- '28000 נטו'"
                ),
                computed_data=computed_data,
            )

        if target_val <= 0:
            return ChatResponse(
                reply=(
                    "לא הצלחתי לקרוא את יעד הקצבה מתוך התכנית האחרונה. "
                    "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של 28000' (ברוטו/נטו)."
                ),
                computed_data=computed_data,
            )

        plan_args = {
            "target_monthly_pension": float(target_val),
            "target_is_net": bool(explicit_is_net),
        }
        plan_result = _execute_tool_call(
            "BUILD_TARGET_PENSION_PLAN",
            plan_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=request_id,
        )
        try:
            store_latest_target_pension_plan(db=db, client_id=request.client_id, tool_result=plan_result)
        except Exception:
            pass
        return ChatResponse(
            reply=(
                "🔧 **פלט כלי (בניית תכנית קצבה - תיקון):**\n"
                + sanitize_user_visible_text(
                    format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                )
            ),
            computed_data=computed_data,
        )

    from ..steps.prepare_inputs_parts.portfolio_breakdown import _maybe_handle_portfolio_breakdown

    handled_breakdown = _maybe_handle_portfolio_breakdown(
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        effective_snapshot_at=effective_snapshot_at,
        computed_data=computed_data,
    )
    if handled_breakdown is not None:
        return handled_breakdown

    from ..steps.prepare_inputs_parts.data_awareness import _maybe_handle_data_awareness

    handled_data_awareness = _maybe_handle_data_awareness(
        request=request,
        db=db,
        request_id=request_id,
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        effective_snapshot_at=effective_snapshot_at,
        computed_data=computed_data,
        _execute_tool_call=_execute_tool_call,
    )
    if handled_data_awareness is not None:
        return handled_data_awareness

    from ..steps.prepare_inputs_parts.system_results_report import _maybe_handle_system_results_report

    handled_system_results_report = _maybe_handle_system_results_report(
        request=request,
        db=db,
        request_id=request_id,
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        computed_data=computed_data,
        _execute_tool_call=_execute_tool_call,
        sanitize_user_visible_text=sanitize_user_visible_text,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
    )
    if handled_system_results_report is not None:
        return handled_system_results_report

    # Deterministic handling for target pension plan requests (avoid LLM timeouts/temporary failures).
    explicit_target_plan_request = False
    wants_execute_target_plan_early = False
    try:
        lowered_tmp = (original_user_msg or "").lower()
        wants_execute_target_plan_early = (
            "בצע" in lowered_tmp
            and ("תכנית" in lowered_tmp or "תוכנית" in lowered_tmp or "מתווה" in lowered_tmp)
        )
        if ("תזרים" not in lowered_tmp) and ("cashflow" not in lowered_tmp):
            planning_keywords = (
                "יעד קצבה",
                "תכנית",
                "תוכנית",
                "מתווה",
                "בנה",
                "צור",
                "תכנן",
                "תכנון",
                "build_target_pension_plan",
            )
            if any(k in lowered_tmp for k in planning_keywords):
                extracted_target = float(extract_target_pension_from_message(original_user_msg) or 0)
                explicit_target_plan_request = extracted_target > 0
    except Exception:
        explicit_target_plan_request = False

    if (
        request.client_id is not None
        and explicit_target_plan_request
        and (not wants_execute_target_plan_early)
        and (not is_document_request(original_user_msg))
        and (not is_qa_request(original_user_msg))
        and (not is_no_tools_request(original_user_msg))
    ):

        target_val = 0.0
        try:
            target_val = float(extract_target_pension_from_message(original_user_msg) or 0)
        except Exception:
            target_val = 0.0
        if target_val <= 0:
            return ChatResponse(
                reply="כדי לבנות תכנית יעד קצבה אני צריך יעד חודשי מספרי (למשל: 28000).",
                computed_data=computed_data,
            )

        lowered = (original_user_msg or "").lower()
        explicit_is_net = None
        if any(t in lowered for t in ("ברוטו", "gross", "bruto")):
            explicit_is_net = False
        elif any(t in lowered for t in ("נטו", "ביד", "אחרי מס", "net")):
            explicit_is_net = True

        if explicit_is_net is None:
            return ChatResponse(
                reply=(
                    "כדי לבנות תכנית יעד קצבה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '28000 ברוטו'\n"
                    "- '28000 נטו'"
                ),
                computed_data=computed_data,
            )

        plan_args = {"target_monthly_pension": float(target_val), "target_is_net": bool(explicit_is_net)}
        plan_result = _execute_tool_call(
            "BUILD_TARGET_PENSION_PLAN",
            plan_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=request_id,
        )
        try:
            store_latest_target_pension_plan(db=db, client_id=request.client_id, tool_result=plan_result)
        except Exception:
            pass
        return ChatResponse(
            reply=(
                "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                + sanitize_user_visible_text(
                    format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                )
            ),
            computed_data=computed_data,
        )

    from ..steps.prepare_inputs_parts.list_all_entities import (
        _maybe_handle_list_all_financial_entities,
    )

    handled_list_all = _maybe_handle_list_all_financial_entities(
        request=request,
        db=db,
        request_id=request_id,
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        effective_snapshot_at=effective_snapshot_at,
        computed_data=computed_data,
        _execute_tool_call=_execute_tool_call,
        _fmt_money=_fmt_money,
    )
    if handled_list_all is not None:
        return handled_list_all

    is_doc_request = is_document_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = is_no_tools_request(original_user_msg)
    force_max_exemption = is_max_exemption_request(original_user_msg)
    is_net_request = is_net_pension_request(original_user_msg)
    is_cashflow_request = is_retirement_cashflow_request(original_user_msg)
    is_comparison_request = is_retirement_comparison_request(original_user_msg)
    commutation_intent = is_pension_commutation_request(original_user_msg)
    explicit_transform = (not commutation_intent) and is_transform_request(original_user_msg)
    explicit_termination = is_process_termination_request(original_user_msg)
    termination_change = is_termination_change_request(original_user_msg)
    is_portfolio_analysis = is_portfolio_analysis_request(original_user_msg)

    lowered_user_msg = (original_user_msg or "").lower()
    wants_capital_transform = (
        (
            ("להון" in lowered_user_msg)
            or ("to capital" in lowered_user_msg)
            or ("הונית" in lowered_user_msg)
            or ("הוני" in lowered_user_msg)
            or ("מקסימום הון" in lowered_user_msg)
        )
        and ("המר" in lowered_user_msg or "המרה" in lowered_user_msg or "convert" in lowered_user_msg or "משיכה" in lowered_user_msg or "משוך" in lowered_user_msg)
    )
    wants_execute_target_plan = (
        "בצע" in lowered_user_msg
        and ("תכנית" in lowered_user_msg or "תוכנית" in lowered_user_msg or "מתווה" in lowered_user_msg)
    )
    wants_fixation_execute = (
        "בצע" in lowered_user_msg
        and ("קיבוע" in lowered_user_msg)
        and ("זכויות" in lowered_user_msg)
    )

    max_capital_request = is_max_capital_request(original_user_msg)
    wants_execute_max_capital = max_capital_request and ("בצע" in lowered_user_msg)

    explicit_cashflow_request = ("תזרים" in lowered_user_msg) or ("cashflow" in lowered_user_msg)
    wants_cashflow_refresh = is_cashflow_missing_income_followup(original_user_msg)

    if commutation_intent and request.client_id is not None:
        account_number = _extract_commutation_account_number(original_user_msg)
        if not account_number:
            return ChatResponse(
                reply=(
                    "כדי לחשב היוון בצורה נכונה אני צריך לזהות *איזו קצבה* אתה רוצה להוון. "
                    "בבקשה ציין אחד מהבאים:\n"
                    "1) מספר חשבון/תיק ניכויים של הקצבה (5+ ספרות)\n"
                    "2) שם הקצבה כפי שמופיע במסך הקצבאות\n\n"
                    "בנוסף: האם הכוונה היא ל*סכום חד-פעמי* שתרצה לקבל, או ל*הפחתה חודשית מהקצבה*?"
                ),
                computed_data=computed_data,
            )

    if (
        (explicit_cashflow_request or wants_cashflow_refresh)
        and request.client_id is not None
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
        and (not commutation_intent)
    ):
        birth_date_for_default_date = None
        gender_for_default_date = None
        try:
            client_obj = db.query(Client).filter(Client.id == request.client_id).first()
            birth_date_for_default_date = getattr(client_obj, "birth_date", None) if client_obj else None
            gender_for_default_date = getattr(client_obj, "gender", None) if client_obj else None
        except Exception:
            birth_date_for_default_date = None
            gender_for_default_date = None

        default_retirement_date = compute_default_retirement_date_for_tool_call(
            birth_date=birth_date_for_default_date,
            gender=gender_for_default_date,
            user_message=original_user_msg or "",
        )
        desired_income = extract_desired_monthly_income_from_text(original_user_msg)
        desired_income_is_net = infer_desired_income_is_net_explicit(original_user_msg)
        if desired_income is not None and desired_income_is_net is None:
            return ChatResponse(
                reply=(
                    "כדי לבנות תזרים לפי יעד הכנסה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '40 אלף ברוטו'\n"
                    "- '40 אלף נטו'"
                ),
                computed_data=computed_data,
            )
        tool_args: dict[str, Any] = {"retirement_date": default_retirement_date}
        if desired_income is not None:
            tool_args["desired_monthly_income"] = float(desired_income)
        if desired_income_is_net is not None:
            tool_args["desired_income_is_net"] = bool(desired_income_is_net)

        tool_result = _execute_tool_call(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            tool_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=request_id,
        )
        try:
            parsed = json.loads(tool_result) if isinstance(tool_result, str) else {}
        except Exception:
            parsed = {}
        explanation = parsed.get("explanation") if isinstance(parsed, dict) else None
        return ChatResponse(
            reply=sanitize_user_visible_text(
                explanation.strip()
                if isinstance(explanation, str) and explanation.strip()
                else format_tool_output_for_user_stream("RUN_RETIREMENT_CASHFLOW_ANALYSIS", tool_result)
            ),
            computed_data=computed_data,
        )

    if (
        request.client_id is not None
        and max_capital_request
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
    ):
        retirement_age = None
        try:
            client = db.query(Client).filter(Client.id == request.client_id).first()
            client_age = client.get_age() if client and hasattr(client, "get_age") else None
            from app.services.retirement_age_service import (
                DEFAULT_MALE_RETIREMENT_AGE,
                get_retirement_age_simple,
            )

            legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)
            try:
                if client and getattr(client, "birth_date", None) and getattr(client, "gender", None):
                    legal_ret_age = int(get_retirement_age_simple(client.birth_date, client.gender))
            except Exception:
                legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

            retirement_age = max(int(legal_ret_age), int(client_age or legal_ret_age))
        except Exception:
            retirement_age = 67

        scenarios_raw = _execute_tool_call(
            "RUN_RETIREMENT_SCENARIOS",
            {"retirement_age": int(retirement_age)},
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=request_id,
        )
        try:
            parsed = json.loads(scenarios_raw) if scenarios_raw else {}
        except Exception:
            parsed = {}

        scenario_id = None
        for row in (parsed.get("scenarios") if isinstance(parsed, dict) else []) or []:
            if isinstance(row, dict) and row.get("scenario_key") == "scenario_2_max_capital":
                scenario_id = row.get("scenario_id")
                break

        if scenario_id is None:
            return ChatResponse(
                reply="לא הצלחתי ליצור תרחיש 'מקסימום הון' במערכת.",
                computed_data=computed_data,
            )

        if wants_execute_max_capital:
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="EXECUTE_RETIREMENT_SCENARIO",
                    tool_args={"scenario_id": int(scenario_id)},
                )
            except Exception:
                pass

            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="EXECUTE_RETIREMENT_SCENARIO",
                    tool_args={"scenario_id": int(scenario_id)},
                    reason=(
                        "בקשת 'משיכה הונית מלאה' מחייבת שמירת קצבת מינימום 5,500 ₪. "
                        "אצור ואבצע את תרחיש 'מקסימום הון' (שמשאיר קצבת מינימום) רק לאחר אישור."
                    ),
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

        return ChatResponse(
            reply=(
                "יצרתי תרחיש 'מקסימום הון' (עם שמירת קצבת מינימום 5,500 ₪). "
                "אם תרצה לבצע אותו בפועל במערכת, כתוב: 'בצע'."
            ),
            computed_data=computed_data,
        )

    # Early deterministic handling for pension commutation requests.
    # Only run this path when the user provided a specific account identifier.
    # If the request is vague (no account number), fall back to the LLM flow.
    if commutation_intent and request.client_id is not None and (not is_doc_request) and (not is_qa_mode):
        account_number = _extract_commutation_account_number(original_user_msg)
        if account_number:
            # NOTE: We deliberately do not handle vague commutation requests deterministically.
            # If no account number is provided, fall back to the LLM loop.

            fund = None
            try:
                from app.models.pension_fund import PensionFund

                fund = (
                    db.query(PensionFund)
                    .filter(PensionFund.client_id == request.client_id)
                    .filter(PensionFund.deduction_file == account_number)
                    .first()
                )
            except Exception:
                fund = None

            if fund is None:
                target_digits = _digits_only(account_number)
                matched: dict | None = None
                for acc in (effective_portfolio or []):
                    data = _item_to_dict(acc)
                    acc_num = str(
                        data.get("מספר_חשבון")
                        or data.get("account_number")
                        or ""
                    ).strip()
                    if not acc_num:
                        continue
                    if acc_num == account_number:
                        matched = data
                        break
                    if target_digits and _digits_only(acc_num) == target_digits:
                        matched = data
                        break

                if fund is None:
                    return ChatResponse(
                        reply=(
                            "כדי לבצע היוון אני צריך לזהות **קצבה קיימת במערכת** שמתאימה לחשבון שביקשת. "
                            f"לא מצאתי קצבה עם מספר חשבון/תיק ניכויים `{account_number}`.\n\n"
                            "אפשרויות:\n"
                            "1) כתוב את שם הקצבה כפי שהיא מופיעה במסך קצבאות, או את מזהה הקצבה (pension_fund_id).\n"
                            "2) אם הכוונה היא לתכנית בתיק המסלקה בלבד (לא קצבה קיימת), ציין: 'הפוך את החשבון לקצבה ואז בצע היוון'."
                        ),
                        computed_data=computed_data,
                    )

            comm_amount = None
            try:
                if _user_wants_full_balance(original_user_msg):
                    comm_amount = float(getattr(fund, "balance", 0) or 0)
            except Exception:
                comm_amount = None

            if not comm_amount or comm_amount <= 0:
                return ChatResponse(
                    reply=(
                        "מצאתי את הקצבה המתאימה, אבל חסר לי סכום היוון. "
                        "כתוב סכום (למשל 50000 ₪) או 'כל היתרה'."
                    ),
                    computed_data=computed_data,
                )

            from datetime import date

            tax_type = "exempt" if "פטור" in (original_user_msg or "") else "taxable"
            exec_args = {
                "pension_fund_id": int(getattr(fund, "id")),
                "commutation_amount": float(comm_amount),
                "commutation_date": date.today().isoformat(),
                "commutation_type": tax_type,
                "confirmed": True,
            }

            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="EXECUTE_PENSION_COMMUTATION",
                    tool_args=exec_args,
                )
            except Exception:
                pass

            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="EXECUTE_PENSION_COMMUTATION",
                    tool_args=exec_args,
                    reason="נדרש אישור לפני ביצוע היוון קצבה במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

    forced_termination_result: str | None = None

    analysis_default_retirement_age: int | None = None
    if is_portfolio_analysis and request.client_id is not None:
        try:
            client = db.query(Client).filter(Client.id == request.client_id).first()
            client_age = client.get_age() if client and hasattr(client, "get_age") else None
            from app.services.retirement_age_service import (
                DEFAULT_MALE_RETIREMENT_AGE,
                get_retirement_age_simple,
            )

            legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)
            try:
                if client and getattr(client, "birth_date", None) and getattr(client, "gender", None):
                    legal_ret_age = int(get_retirement_age_simple(client.birth_date, client.gender))
            except Exception:
                legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

            analysis_default_retirement_age = max(int(legal_ret_age), int(client_age or legal_ret_age))
        except Exception:
            analysis_default_retirement_age = None

    termination_already_executed = False
    if request.client_id is not None:
        current_employer = (
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == request.client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )
        if current_employer is not None and current_employer.end_date is not None:
            grants_count = (
                db.query(EmployerGrant)
                .filter(
                    EmployerGrant.employer_id == current_employer.id,
                    EmployerGrant.grant_type == GrantType.severance,
                )
                .count()
            )
            confirmed = False
            try:
                other_grants = current_employer.other_grants or {}
                if isinstance(other_grants, dict):
                    confirmed = bool(other_grants.get("termination_confirmed"))
            except Exception:
                confirmed = False
            termination_already_executed = confirmed or (grants_count > 0)

    if (
        explicit_termination
        and request.client_id is not None
        and (not no_tools_requested)
        and (not is_qa_mode)
    ):
        recent_user_text = "\n".join(
            [
                str(getattr(m, "content", ""))
                for m in (request.messages or [])
                if getattr(m, "role", None) == "user"
            ][-8:]
        )
        tool_args: dict[str, Any] = {
            "confirmed": True,
        }
        tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
        termination_date_override = extract_process_termination_date_override(recent_user_text)
        if termination_date_override:
            tool_args["termination_date"] = termination_date_override

        if not termination_already_executed:
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="PROCESS_TERMINATION",
                    tool_args=tool_args,
                )
            except Exception:
                pass
            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="PROCESS_TERMINATION",
                    tool_args=tool_args,
                    reason="נדרש אישור לפני ביצוע עזיבת עבודה במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

        forced_termination_result = None

    if (
        request.client_id is not None
        and (not no_tools_requested)
        and (not is_qa_mode)
        and (wants_execute_target_plan or wants_fixation_execute)
    ):
        if wants_execute_target_plan:
            payload = extract_latest_target_pension_plan_payload(request.messages)
            if payload is None:
                payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
            if not isinstance(payload, dict):
                return ChatResponse(
                    reply="לא נמצאה תכנית יעד אחרונה לביצוע. קודם צריך לבנות תכנית יעד קצבה ואז לבקש לבצע אותה בפועל.",
                    computed_data=computed_data,
                )

            accounts = build_transform_accounts_from_target_plan_payload(payload)
            if not accounts:
                return ChatResponse(
                    reply="לא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע אותה בפועל.",
                    computed_data=computed_data,
                )

            transform_args: dict[str, Any] = {
                "accounts": accounts,
                "use_provided_accounts_only": True,
                "ignore_blocked_balances": True,
                "skip_non_convertible_accounts": True,
            }
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    tool_args=transform_args,
                )
            except Exception:
                pass
            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    tool_args=transform_args,
                    reason="נדרש אישור לפני ביצוע המרות לפי תכנית היעד במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

        if wants_fixation_execute:
            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="CALCULATE_FIXATION_OF_RIGHTS",
                    tool_args={"save_result": True},
                )
            except Exception:
                pass
            return ChatResponse(
                reply=build_approval_request_ui_action(
                    tool_name="CALCULATE_FIXATION_OF_RIGHTS",
                    tool_args={"save_result": True},
                    reason="נדרש אישור לפני ביצוע קיבוע זכויות במערכת.",
                    risk_level="high",
                    rag_sources=None,
                ),
                computed_data=computed_data,
            )

    approval = extract_user_approval_for_tool_call(request.messages)
    cancelled = extract_user_cancel_for_tool_call(request.messages)

    if approval is None and request.client_id is not None and (not no_tools_requested):
        last_user_text = find_last_user_message(request.messages)
        if is_user_approval_intent_text(last_user_text):
            pending = extract_latest_approval_request(request.messages)
            if pending is not None:
                approval = pending
            else:
                try:
                    pending_db = load_pending_approval_request(
                        db=db,
                        client_id=request.client_id,
                    )
                except Exception:
                    pending_db = None
                if pending_db is not None:
                    approval = pending_db

            if approval is None:
                raw = (last_user_text or "").strip().lower()
                if raw in {
                    "אשר",
                    "מאשר",
                    "אני מאשר",
                    "מאשרת",
                    "אני מאשרת",
                    "approve",
                    "approved",
                    "ok",
                    "כן",
                }:
                    return ChatResponse(
                        reply=(
                            "לא נמצאה בקשת אישור פעילה לביצוע. "
                            "כדי לבצע פעולה במערכת צריך קודם לקבל בקשת אישור (כפתור אשר), "
                            "או לבקש שוב במפורש לבצע את הפעולה."
                        ),
                        computed_data=computed_data,
                    )
    if (
        approval
        and request.client_id is not None
        and (not no_tools_requested)
        and (not explicit_transform)
    ):
        approved_tool_name, approved_tool_args = approval

        if (
            approved_tool_name == "PROCESS_TERMINATION"
            and termination_already_executed
            and (not termination_change)
            and wants_execute_target_plan
        ):
            payload = extract_latest_target_pension_plan_payload(request.messages)
            if payload is None:
                payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
            if not isinstance(payload, dict):
                return ChatResponse(
                    reply=(
                        "עזיבת עבודה כבר בוצעה. "
                        "לא נמצאה תכנית יעד אחרונה לביצוע. קודם צריכה להיבנות תכנית יעד קצבה ואז לבקש לבצע אותה."
                    ),
                    computed_data=computed_data,
                )

            accounts = build_transform_accounts_from_target_plan_payload(payload)
            if not accounts:
                return ChatResponse(
                    reply=(
                        "עזיבת עבודה כבר בוצעה. "
                        "לא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע."
                    ),
                    computed_data=computed_data,
                )

            transform_args = {
                "accounts": accounts,
                "use_provided_accounts_only": True,
                "ignore_blocked_balances": True,
                "skip_non_convertible_accounts": True,
            }
            transform_result = _execute_tool_call(
                "TRANSFORM_FUNDS_TO_ASSETS",
                transform_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=True,
                request_id=request_id,
            )

            try:
                clear_pending_approval_request(db=db, client_id=request.client_id)
            except Exception:
                pass

            portfolio_update_marker = build_pension_portfolio_update_after_transform(
                tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                tool_result=transform_result,
                tool_args=transform_args,
                current_pension_portfolio=effective_portfolio,
            )

            reply_text = format_transform_result_for_user(tool_result=transform_result)
            if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
                reply_text = f"{portfolio_update_marker}{reply_text}"
            return ChatResponse(
                reply=sanitize_user_visible_text(reply_text),
                computed_data=computed_data,
            )

        if approved_tool_name == "PROCESS_TERMINATION":
            overrides = extract_process_termination_choice_overrides(original_user_msg)
            if overrides and isinstance(approved_tool_args, dict):
                approved_tool_args = dict(approved_tool_args)
                approved_tool_args.update(overrides)
        tool_result = _execute_tool_call(
            approved_tool_name,
            approved_tool_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=request_id,
        )

        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

        portfolio_update_marker = build_pension_portfolio_update_after_transform(
            tool_name=approved_tool_name,
            tool_result=tool_result,
            tool_args=approved_tool_args,
            current_pension_portfolio=effective_portfolio,
        )
        forced_document_reply = build_forced_document_reply(
            tool_name=approved_tool_name,
            tool_result=tool_result,
        )

        reply_text = forced_document_reply or tool_result
        if approved_tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            reply_text = format_transform_result_for_user(tool_result=tool_result)
        else:
            reply_text = format_tool_output_for_user_stream(approved_tool_name, reply_text)

        if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
            reply_text = f"{portfolio_update_marker}{reply_text}"

        sanitized = sanitize_user_visible_text(reply_text)
        if is_portfolio_analysis and isinstance(sanitized, str) and sanitized.strip():
            if "הערכה" not in sanitized and "הערכה גסה" not in sanitized and "ראשונית" not in sanitized:
                sanitized = (
                    "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                    + sanitized
                )

        return ChatResponse(reply=sanitized, computed_data=computed_data)

    if cancelled and request.client_id is not None and (not no_tools_requested):
        cancelled_tool_name, _cancelled_tool_args = cancelled
        return ChatResponse(
            reply=f"בוצעה ביטול להפעלת הכלי: {cancelled_tool_name}. לא בוצע שינוי במערכת.",
            computed_data=computed_data,
        )

    wants_ignore_blocked = any(
        _is_ignore_blocked_text(getattr(m, "content", ""))
        for m in (request.messages or [])
        if getattr(m, "role", None) == "user"
    )

    wants_ignore_blocked = wants_ignore_blocked or any(
        is_no_termination_request(getattr(m, "content", ""))
        for m in (request.messages or [])
        if getattr(m, "role", None) == "user"
    )

    if wants_ignore_blocked:
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    "המשתמש אישר להתעלם מיתרות חסומות/יתרות לטיפול במסך עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                    "אל תשאל שוב לאישור על זה. אל תבצע עזיבת עבודה בשיחה זו, והמשך עם שאר הכלים הרלוונטיים בלבד."
                ),
            )
        )

    if is_portfolio_analysis:
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    "הנחיה: המשתמש ביקש ניתוח תיק. חובה להחזיר ניתוח מיד (Advisory Mode). "
                    "אסור לבצע אימות/בדיקת חוקיות של סכום הפיצויים מול נוסחה או מול 'חובת מעסיק'. "
                    "ברירת מחדל: אסור לפרט מדרגות מס. חריג: אם המשתמש ביקש פרמטרים/מדרגות/תקרות והרצת GET_TAX_PARAMS — מותר לצטט מספרים רק מתוך תוצאת הכלי. "
                    "כאשר אתה מדבר עם המשתמש על הפעולה, השתמש במונח 'עזיבת עבודה' בלבד. "
                    "אם מציגים תרחישים אוטומטיים: הם הערכה גסה/ראשונית בלבד, והצג אותם כ'תרחיש 1/2/3'."
                ),
            )
        )

    current_pension_portfolio = effective_portfolio

    if explicit_transform and (not no_tools_requested) and (not is_doc_request) and (not is_qa_mode):
        derived_accounts = build_transform_accounts_from_portfolio(current_pension_portfolio)
        try:
            logger.info(
                "🔁 Deterministic transform requested (client_id=%s, portfolio_accounts=%s, derived_accounts=%s)",
                request.client_id,
                len(current_pension_portfolio) if isinstance(current_pension_portfolio, list) else 0,
                len(derived_accounts),
            )
        except Exception:
            pass
        if not derived_accounts:
            try:
                logger.info(
                    "⚠️ Deterministic transform blocked: no derived accounts (client_id=%s)",
                    request.client_id,
                )
            except Exception:
                pass
            return ChatResponse(
                reply=(
                    "לא ניתן לבצע המרה כי אין תיק מסלקה/סנאפשוט זמין במערכת (pension_portfolio_snapshot ריק). "
                    "כדי לבצע המרה מלאה צריך קודם לטעון תיק מסלקה כך שיופיע פירוט חשבונות."
                ),
                computed_data=computed_data,
            )

        tool_args: dict[str, Any] = {}
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
                return ChatResponse(
                    reply=(
                        f"לא הצלחתי למצוא חשבון מספר {acc_num} בתיק כדי לבצע המרה חלקית. "
                        "אנא ודא שמספר החשבון נכון ושיש סנאפשוט תיק מעודכן."
                    ),
                    computed_data=computed_data,
                )
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
                    return ChatResponse(
                        reply=(
                            f"לא הצלחתי למצוא רכיבים מתאימים בחשבון מספר {acc_num} כדי לבצע המרה ממוקדת. "
                            "אנא ודא שמספר החשבון נכון ושיש רכיב רלוונטי בתיק."
                        ),
                        computed_data=computed_data,
                    )
                tool_args["accounts"] = targeted_accounts
                tool_args["use_provided_accounts_only"] = True
            else:
                prev_sev_req = parse_portfolio_wide_prev_employers_severance_conversion_request(original_user_msg)
                if prev_sev_req is not None:
                    _fields, conv_type = prev_sev_req
                    if conv_type == "blocked":
                        return ChatResponse(
                            reply=(
                                "מצאתי בקשה ל'פיצויים מעסיקים קודמים (רצף זכויות)', אך רכיב זה חסום להמרה במערכת "
                                "ודורש טיפול חיצוני/התחשבנות. אם תרצה, אוכל להציג באילו חשבונות הוא מופיע."
                            ),
                            computed_data=computed_data,
                        )
                    portfolio_accounts = build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio(
                        pension_portfolio=current_pension_portfolio,
                        conversion_type=conv_type,
                    )
                    if not portfolio_accounts:
                        return ChatResponse(
                            reply="לא מצאתי בתיק רכיב 'פיצויים מעסיקים קודמים (רצף קצבה)' להמרה.",
                            computed_data=computed_data,
                        )
                    tool_args["accounts"] = portfolio_accounts
                    tool_args["use_provided_accounts_only"] = True
                else:
                    after_settle_req = parse_portfolio_wide_after_settlement_severance_conversion_request(
                        original_user_msg
                    )
                    if after_settle_req is not None:
                        _fields, conv_type = after_settle_req
                        portfolio_accounts = build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio(
                            pension_portfolio=current_pension_portfolio,
                            conversion_type=conv_type,
                        )
                        if not portfolio_accounts:
                            return ChatResponse(
                                reply="לא מצאתי בתיק רכיב 'פיצויים לאחר התחשבנות' להמרה.",
                                computed_data=computed_data,
                            )
                        tool_args = {
                            "accounts": portfolio_accounts,
                            "use_provided_accounts_only": True,
                        }
                    else:
                        portfolio_wide_req = parse_portfolio_wide_component_conversion_request(original_user_msg)
                        if portfolio_wide_req is not None:
                            _fields, conv_type = portfolio_wide_req
                            portfolio_accounts = build_portfolio_wide_component_transform_accounts_from_portfolio(
                                pension_portfolio=current_pension_portfolio,
                                fields=_fields,
                                conversion_type=conv_type,
                            )
                            if not portfolio_accounts:
                                return ChatResponse(
                                    reply=(
                                        "לא מצאתי בתיק רכיבי 'תגמולים אחרי 2000' להמרה. "
                                        "אם אתה מתכוון לרכיבים אחרים, ציין במפורש אילו רכיבים להמיר."
                                    ),
                                    computed_data=computed_data,
                                )
                            tool_args = {
                                "accounts": portfolio_accounts,
                                "use_provided_accounts_only": True,
                            }
                        else:
                            edu_req = parse_portfolio_wide_education_fund_conversion_request(original_user_msg)
                            if edu_req is not None:
                                _fields, conv_type = edu_req
                                edu_accounts = build_portfolio_wide_education_fund_transform_accounts_from_portfolio(
                                    pension_portfolio=current_pension_portfolio,
                                    conversion_type=conv_type,
                                )
                                if not edu_accounts:
                                    return ChatResponse(
                                        reply="לא מצאתי בתיק קרנות השתלמות להמרה.",
                                        computed_data=computed_data,
                                    )
                                tool_args = {
                                    "accounts": edu_accounts,
                                    "use_provided_accounts_only": True,
                                }
                            else:
                                tool_args["accounts"] = derived_accounts

        if wants_ignore_blocked:
            tool_args["ignore_blocked_balances"] = True
            tool_args["skip_non_convertible_accounts"] = True

        if wants_capital_transform:
            return ChatResponse(
                reply=(
                    "המרה להון של רכיבים קצבתיים (למשל 'תגמולים אחרי 2000') לא מבוצעת דרך TRANSFORM_FUNDS_TO_ASSETS, "
                    "כדי למנוע הפרת קצבת מינימום.\n\n"
                    "אם הכוונה ל*משיכה הונית מלאה* — בקש: 'משיכה הונית מלאה' ואז אשר את תרחיש 'מקסימום הון' "
                    "(ששומר קצבת מינימום 5,500).\n"
                    "אם הכוונה ל*היוון קצבה ספציפית* — בקש: 'הוון קצבה' וציין מספר חשבון/שם קצבה."
                ),
                computed_data=computed_data,
            )

        tool_result = _execute_tool_call(
            "TRANSFORM_FUNDS_TO_ASSETS",
            tool_args,
            request.client_id,
            db,
            pension_portfolio=current_pension_portfolio,
            force_max_exemption=False,
            request_id=request_id,
        )

        log_llm_event_fn(
            request_id=request_id,
            event_type="tool_call",
            payload={"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": tool_args},
            client_id=request.client_id,
        )
        log_llm_event_fn(
            request_id=request_id,
            event_type="tool_result",
            payload={"tool_name": "TRANSFORM_FUNDS_TO_ASSETS", "result": tool_result},
            client_id=request.client_id,
        )

        portfolio_update_marker = build_pension_portfolio_update_after_transform(
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_result=tool_result,
            tool_args=tool_args,
            current_pension_portfolio=current_pension_portfolio,
        )

        reply_text = format_transform_result_for_user(tool_result=tool_result)
        if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
            reply_text = f"{portfolio_update_marker}{reply_text}"

        return ChatResponse(reply=reply_text, computed_data=computed_data)

    log_llm_event_fn(
        request_id=request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
    )

    return _PreparedOrchestrationInputs(
        messages=messages,
        original_user_msg=original_user_msg,
        current_pension_portfolio=current_pension_portfolio,
        computed_data=computed_data,
        is_qa_mode=is_qa_mode,
        no_tools_requested=no_tools_requested,
        is_doc_request=is_doc_request,
        is_cashflow_request=is_cashflow_request,
        is_comparison_request=is_comparison_request,
        is_net_request=is_net_request,
        is_portfolio_analysis=is_portfolio_analysis,
        analysis_default_retirement_age=analysis_default_retirement_age,
        force_max_exemption=force_max_exemption,
        wants_ignore_blocked=wants_ignore_blocked,
        explicit_termination=explicit_termination,
        termination_change=termination_change,
        termination_already_executed=termination_already_executed,
        wants_execute_target_plan=wants_execute_target_plan,
        wants_fixation_execute=wants_fixation_execute,
    )


