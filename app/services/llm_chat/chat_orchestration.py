import json
import logging
import inspect
import re
import uuid
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatMessage, ChatRequest, ChatResponse
from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    build_forced_document_reply,
    build_pension_portfolio_update_after_transform,
    build_transform_accounts_from_target_plan_payload,
    format_transform_result_for_user,
    get_gross_for_tax_chaining,
    store_pending_approval_request,
    load_pending_approval_request,
    clear_pending_approval_request,
    load_latest_target_pension_plan,
    maybe_clear_pension_portfolio_after_transform,
    run_tax_projection_autochain,
    store_latest_target_pension_plan,
)

from datetime import date
import re
from app.services.llm_chat.chat_stream_orchestration import (
    run_pension_chat_stream as run_pension_chat_stream_impl,
)
from app.services.llm_chat.message_preparation import prepare_messages_with_context
from app.services.llm_chat.message_utils import (
    extract_latest_approval_request,
    extract_user_approval_for_tool_call,
    extract_user_cancel_for_tool_call,
    extract_latest_target_pension_plan_payload,
    extract_target_pension_from_message,
    was_tool_call_previously_approved,
    find_last_user_message,
    is_user_approval_intent_text,
)
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_partial_pension_transform_accounts_from_portfolio,
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_chat,
    build_tool_call_message_content,
    build_tool_result_system_message_for_chat,
    compute_default_retirement_date_for_tool_call,
    normalize_retirement_date_if_jan1_placeholder,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    is_no_termination_request,
    is_tax_documents_request,
    is_document_request,
    is_no_tools_request,
    is_qa_request,
    is_transform_request,
    parse_partial_pension_conversion_request,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_targeted_component_conversion_request,
    is_process_termination_request,
    is_pension_commutation_request,
    is_termination_change_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_portfolio_breakdown_request,
    is_portfolio_analysis_request,
    parse_tool_call_from_reply,
    validate_tool_call_protocol_for_execution,
)
from app.services.llm_chat.tool_execution import execute_tool_call
from app.services.llm_pension_agent_service import pension_llm_service
from app.models.client import Client
from app.models import CurrentEmployer, EmployerGrant, GrantType
from app.utils.llm_chat_log import generate_request_id, log_llm_event, set_current_request_id

logger = logging.getLogger("app.llm_chat")


def _execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
    force_max_exemption: bool = False,
    agent_reply: str | None = None,
    user_approved: bool = False,
    request_id: str | None = None,
) -> str:
    logger.info("⚡ Executing Tool: %s with args: %s", tool_name, args)

    req_id = request_id or "unknown"
    log_llm_event(
        request_id=req_id,
        event_type="tool_execution",
        payload={
            "execution_id": str(uuid.uuid4()),
            "tool_name": tool_name,
            "args": args if isinstance(args, dict) else {},
        },
        client_id=client_id,
    )
    try:
        sig = inspect.signature(execute_tool_call)
        if "agent_reply" in sig.parameters or "user_approved" in sig.parameters:
            return execute_tool_call(
                tool_name=tool_name,
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
                force_max_exemption=force_max_exemption,
                agent_reply=agent_reply,
                user_approved=user_approved,
            )
    except Exception:
        pass

    return execute_tool_call(
        tool_name=tool_name,
        args=args,
        client_id=client_id,
        db=db,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
    )


def run_pension_chat(request: ChatRequest, db: Session) -> ChatResponse:
    request_id = generate_request_id()
    set_current_request_id(request_id)

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    try:
        request_portfolio_count = (
            len(request.pension_portfolio)
            if isinstance(request.pension_portfolio, list)
            else 0
        )
    except Exception:
        request_portfolio_count = 0
    if request.client_id is not None:
        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded
            try:
                logger.info(
                    "📦 Using DB pension_portfolio_snapshot (client_id=%s, accounts=%s, snapshot_at=%s)",
                    request.client_id,
                    len(effective_portfolio) if isinstance(effective_portfolio, list) else 0,
                    effective_snapshot_at,
                )
            except Exception:
                pass
        else:
            try:
                logger.info(
                    "📦 No DB pension_portfolio_snapshot found; using request payload (client_id=%s, accounts=%s)",
                    request.client_id,
                    request_portfolio_count,
                )
            except Exception:
                pass
    else:
        try:
            logger.info(
                "📦 No client_id provided; using request payload (accounts=%s)",
                request_portfolio_count,
            )
        except Exception:
            pass

    messages, computed_data = prepare_messages_with_context(request, db)
    original_user_msg = find_last_user_message(request.messages)

    def _extract_commutation_account_number(text: str | None) -> str | None:
        raw = str(text or "").strip()
        if not raw:
            return None
        m = re.search(r"\((\d{5,})\)", raw)
        if m:
            return str(m.group(1) or "").strip()
        candidates = re.findall(r"\b(\d{5,})\b", raw)
        return str(candidates[-1]).strip() if candidates else None

    def _user_wants_full_balance(text: str | None) -> bool:
        lowered = (text or "").lower()
        return ("כל" in lowered) and ("יתרה" in lowered)

    def _is_target_plan_adjust_request(text: str | None) -> bool:
        lowered = (text or "").lower()
        if not lowered.strip():
            return False
        if "קצבה" not in lowered:
            return False
        if not any(token in lowered for token in ("גבוה", "גבוהה", "יותר", "מדי", "תקן", "לתקן")):
            return False
        return True

    def _infer_target_is_net_explicit(text: str | None) -> bool | None:
        lowered = (text or "").lower()
        if any(t in lowered for t in ("ברוטו", "gross", "bruto")):
            return False
        if any(t in lowered for t in ("נטו", "ביד", "אחרי מס", "net")):
            return True
        return None

    def _is_target_plan_adjust_followup(user_text: str | None, history: list[ChatMessage]) -> bool:
        lowered = (user_text or "").lower()
        if not lowered.strip():
            return False
        if ("נטו" not in lowered) and ("ברוטו" not in lowered) and ("net" not in lowered) and ("gross" not in lowered):
            return False
        if not any(ch.isdigit() for ch in lowered):
            return False
        last_assistant = None
        for msg in reversed(history or []):
            if getattr(msg, "role", None) == "assistant":
                last_assistant = getattr(msg, "content", "") or ""
                break
        if not last_assistant:
            return False
        probe = last_assistant
        return ("ברוטו" in probe and "נטו" in probe and "כדי לתקן" in probe)

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
    if is_portfolio_breakdown_request(original_user_msg):
        portfolio = effective_portfolio or []
        breakdown = (
            "\n".join(
                build_pension_portfolio_context(
                    portfolio,
                    user_message=original_user_msg,
                    snapshot_at=effective_snapshot_at,
                )
            ).strip()
            if portfolio
            else ""
        )
        if breakdown:
            return ChatResponse(reply=breakdown, computed_data=computed_data)
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
        ("להון" in lowered_user_msg or "to capital" in lowered_user_msg)
        and ("המר" in lowered_user_msg or "המרה" in lowered_user_msg or "convert" in lowered_user_msg)
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
                def _item_to_dict(item: Any) -> dict:
                    if isinstance(item, dict):
                        return item
                    model_dump = getattr(item, "model_dump", None)
                    if callable(model_dump):
                        dumped = model_dump()
                        return dumped if isinstance(dumped, dict) else {}
                    raw = getattr(item, "__dict__", {})
                    return raw if isinstance(raw, dict) else {}

                def _digits_only(value: str | None) -> str:
                    return "".join(ch for ch in (value or "") if ch.isdigit())

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

                if matched is not None:
                    try:
                        from app.models.pension_fund import PensionFund

                        raw_balance = matched.get("יתרה")
                        if raw_balance is None:
                            raw_balance = matched.get("balance")
                        try:
                            balance = float(raw_balance or 0)
                        except Exception:
                            balance = 0.0

                        fund = PensionFund(
                            client_id=int(request.client_id),
                            fund_name=str(
                                matched.get("שם_תכנית")
                                or matched.get("account_name")
                                or "קצבה"
                            ),
                            fund_type=str(
                                matched.get("סוג_מוצר")
                                or matched.get("product_type")
                                or "unknown"
                            ),
                            input_mode="manual",
                            balance=float(balance),
                            annuity_factor=200.0,
                            pension_amount=round(float(balance) / 200.0)
                            if float(balance) > 0
                            else 0.0,
                            pension_start_date=None,
                            indexation_method="none",
                            tax_treatment="taxable",
                            deduction_file=str(
                                matched.get("מספר_חשבון")
                                or matched.get("account_number")
                                or account_number
                            ),
                            conversion_source=json.dumps(
                                {
                                    "type": "pension_portfolio",
                                    "source": "pension_portfolio",
                                    "account_number": str(
                                        matched.get("מספר_חשבון")
                                        or matched.get("account_number")
                                        or account_number
                                    ),
                                    "account_name": str(
                                        matched.get("שם_תכנית")
                                        or matched.get("account_name")
                                        or ""
                                    ),
                                    "company": str(
                                        matched.get("חברה_מנהלת")
                                        or matched.get("company")
                                        or ""
                                    ),
                                    "product_type": str(
                                        matched.get("סוג_מוצר")
                                        or matched.get("product_type")
                                        or ""
                                    ),
                                    "amount": float(balance),
                                    "conversion_date": date.today().isoformat(),
                                },
                                ensure_ascii=False,
                            ),
                        )
                        db.add(fund)
                        db.commit()
                        db.refresh(fund)
                    except Exception:
                        fund = None

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

            tax_type = "exempt" if "פטור" in (original_user_msg or "") else "taxable"
            exec_args = {
                "pension_fund_id": int(getattr(fund, "id")),
                "commutation_amount": float(comm_amount),
                "commutation_date": date.today().isoformat(),
                "commutation_type": tax_type,
                "confirmed": True,
            }

            tool_result = _execute_tool_call(
                "EXECUTE_PENSION_COMMUTATION",
                exec_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=request_id,
            )

            return ChatResponse(
                reply=sanitize_user_visible_text(
                    format_tool_output_for_user_stream(
                        "EXECUTE_PENSION_COMMUTATION",
                        tool_result,
                    )
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

    def _is_ignore_blocked_text(text: str) -> bool:
        lowered = (text or "").lower()
        return any(
            token in lowered
            for token in (
                "התעלם",
                "להתעלם",
                "דלג",
                "לדלג",
                "המשך",
                "להמשיך",
                "בלי",
            )
        ) and any(
            token in lowered
            for token in (
                "חסומ",
                "פיצויים מעסיק נוכחי",
                "מעסיק נוכחי",
                "רצף זכויות",
                "שלא עברו התחשבנות",
                "התחשבנות",
            )
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

    def _user_requested_target_pension_plan(text: str) -> bool:
        lowered = (text or "").lower().replace(",", "")
        if not lowered.strip():
            return False
        planning_keywords = [
            "יעד קצבה",
            "תכנית",
            "תוכנית",
            "מתווה",
            "בנה",
            "צור",
            "תכנן",
            "תכנון",
            "build_target_pension_plan",
        ]
        if not any(k in lowered for k in planning_keywords):
            return False
        has_numeric = bool(re.search(r"\b\d{2,3}\s*[kK]\b", lowered)) or bool(
            re.search(r"\b\d{4,6}\b", lowered)
        ) or ("אלף" in lowered)
        return has_numeric

    def _extract_target_monthly_pension(text: str) -> float | None:
        if not isinstance(text, str) or not text.strip():
            return None
        cleaned = text.replace(",", "")

        m_k = re.search(r"\b(\d{2,3})\s*[kK]\b", cleaned)
        if m_k:
            try:
                return float(int(m_k.group(1)) * 1000)
            except Exception:
                return None

        m_num = re.search(r"\b(\d{4,6})\b", cleaned)
        if m_num:
            try:
                return float(int(m_num.group(1)))
            except Exception:
                return None

        m_he = re.search(r"\b(\d{1,3})\s*אלף\b", cleaned)
        if m_he:
            try:
                return float(int(m_he.group(1)) * 1000)
            except Exception:
                return None

        return None

    def _infer_target_is_net(text: str) -> bool:
        lowered = (text or "").lower()
        if any(t in lowered for t in ("ברוטו", "gross", "bruto")):
            return False
        if any(t in lowered for t in ("נטו", "ביד", "אחרי מס", "net")):
            return True
        return False

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
                    "אסור לפרט מדרגות מס. "
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
                    fields, conv_type = prev_sev_req
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
                        fields, conv_type = after_settle_req
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
                            fields, conv_type = portfolio_wide_req
                            portfolio_accounts = build_portfolio_wide_component_transform_accounts_from_portfolio(
                                pension_portfolio=current_pension_portfolio,
                                fields=fields,
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
            tool_args.setdefault("default_conversion_type", "capital_asset")
            tool_args["commute_pension_components"] = True

        tool_result = _execute_tool_call(
            "TRANSFORM_FUNDS_TO_ASSETS",
            tool_args,
            request.client_id,
            db,
            pension_portfolio=current_pension_portfolio,
            force_max_exemption=False,
            request_id=request_id,
        )

        log_llm_event(
            request_id=request_id,
            event_type="tool_call",
            payload={"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": tool_args},
            client_id=request.client_id,
        )
        log_llm_event(
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

    log_llm_event(
        request_id=request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
    )

    max_steps = 5
    current_step = 0
    final_reply = ""
    forced_user_prefix: str = ""
    qa_summary_required = False
    report_open_path: str | None = None
    forced_fixation_chain_done = False

    while current_step < max_steps:
        logger.info(
            "🔄 Agent Loop Step %d/%d for client %s",
            current_step + 1,
            max_steps,
            request.client_id,
        )

        raw_reply = pension_llm_service.chat(messages, request.client_id)

        lowered = (raw_reply or "").lower()
        has_pass_fail = ("pass" in lowered) or ("fail" in lowered)

        if is_qa_mode and no_tools_requested and not has_pass_fail and "###TOOL_CALL###" not in raw_reply:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                        "אסור להחזיר TOOL_CALL. כעת החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר."
                    ),
                )
            )
            current_step += 1
            continue

        if qa_summary_required and not has_pass_fail and "###TOOL_CALL###" not in raw_reply:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: במצב QA חובה לסיים בתשובת PASS/FAIL וסיכום קצר. "
                        "החזר כעת תשובת PASS או FAIL בלבד + 3-6 שורות סיכום + open_path של הדוח."
                    ),
                )
            )
            current_step += 1
            continue

        if "###TOOL_CALL###" in raw_reply:
            tool_part_for_log = raw_reply.split("###TOOL_CALL###", 1)[1].strip()

            try:
                parsed = parse_tool_call_from_reply(raw_reply)
                if parsed is None:
                    break

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
                    continue

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
                        continue

                if tool_name == "PROCESS_TERMINATION" and wants_ignore_blocked:
                    messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש במפורש להתעלם מיתרות חסומות/עזיבת עבודה ולהמשיך ללא טיפול בעזיבת עבודה. "
                                "אסור לבצע עזיבת עבודה. כעת המשך ללא TOOL_CALL ובחר כלי אחר שמתאים לבקשה."
                            ),
                        )
                    )
                    current_step += 1
                    continue

                if tool_name == "PROCESS_TERMINATION" and (not explicit_termination):
                    allow_change_after_execution = bool(
                        termination_already_executed and termination_change
                    )
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
                        continue

                if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
                    # Guardrail: when the user intent is current-employer severance / work termination,
                    # do not transform the whole portfolio. Route to PROCESS_TERMINATION instead.
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
                                    "במקום זאת החזר TOOL_CALL ל-PROCESS_TERMINATION בלבד (עם confirmed=true)."
                                ),
                            )
                        )
                        current_step += 1
                        continue

                    # Guardrail: pension commutation (היוון קצבה) must not be routed to TRANSFORM_FUNDS_TO_ASSETS.
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
                                    "במקום זאת החזר TOOL_CALL ל-EXECUTE_PENSION_COMMUTATION בלבד (עם confirmed=true) "
                                    "ועם pension_fund_id, commutation_amount, commutation_date, commutation_type."
                                ),
                            )
                        )
                        current_step += 1
                        continue

                    # Deterministic override: if the user asked to convert a specific component bucket
                    # (e.g., "תגמולים לפני 2000"), do NOT allow a full-portfolio tool call.
                    if (not current_pension_portfolio) and request.client_id is not None:
                        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
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
                            prev_sev_req = parse_portfolio_wide_prev_employers_severance_conversion_request(
                                original_user_msg
                            )
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
                                after_settle_req = parse_portfolio_wide_after_settlement_severance_conversion_request(
                                    original_user_msg
                                )
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
                                    portfolio_wide_req = parse_portfolio_wide_component_conversion_request(
                                        original_user_msg
                                    )
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
                                        edu_req = parse_portfolio_wide_education_fund_conversion_request(
                                            original_user_msg
                                        )
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
                        continue

                    if (not current_pension_portfolio) and request.client_id is not None:
                        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
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
                            continue
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
                                continue
                            if not isinstance(tool_args, dict):
                                tool_args = {}
                            tool_args["accounts"] = targeted_accounts
                            tool_args["use_provided_accounts_only"] = True
                        else:
                            derived_accounts = build_transform_accounts_from_portfolio(
                                current_pension_portfolio
                            )
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
                                continue

                            tool_args_accounts = (
                                tool_args.get("accounts") if isinstance(tool_args, dict) else None
                            )
                            if not isinstance(tool_args, dict):
                                tool_args = {}
                            if not (isinstance(tool_args_accounts, list) and tool_args_accounts):
                                tool_args["accounts"] = derived_accounts
                            else:
                                def _is_aggregate_account(acc: dict) -> bool:
                                    name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
                                    number = str(acc.get("account_number") or acc.get("מספר_חשבון") or "")
                                    product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
                                    return (
                                        name.startswith("Aggregate_")
                                        or number.startswith("AGG-")
                                        or product_type.startswith("aggregate_")
                                    )

                                if any(
                                    _is_aggregate_account(acc)
                                    for acc in tool_args_accounts
                                    if isinstance(acc, dict)
                                ):
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
                    continue

                if is_doc_request and not is_qa_mode:
                    allowed_doc_tools = {"GENERATE_FULL_REPORT", "GENERATE_TAX_DEDUCTION_DOCUMENTS", "TRANSFORM_FUNDS_TO_ASSETS"}

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
                        continue

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
                    continue

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
                    continue

                log_llm_event(
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
                        client = (
                            db.query(Client)
                            .filter(Client.id == request.client_id)
                            .first()
                        )
                        birth_date = getattr(client, "birth_date", None) if client else None
                        if birth_date is not None:
                            tool_args["retirement_date"] = normalize_retirement_date_if_jan1_placeholder(
                                retirement_date=date_str.strip(),
                                birth_date=birth_date,
                                user_message=original_user_msg,
                            )

                if text_part:
                    messages.append(ChatMessage(role="assistant", content=text_part))

                tool_msg_content = build_tool_call_message_content(
                    tool_call_data, ensure_ascii=True
                )
                messages.append(ChatMessage(role="assistant", content=tool_msg_content))

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
                    break

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

                log_llm_event(
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
                        break

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
                    forced_user_prefix += (
                        "🔧 **פלט כלי (הערכת מס - שרשור אוטומטי):**\n" + tax_result + "\n\n"
                    )

                # Mandatory chaining for NET target pension plans:
                # After a conversion or work termination, we MUST refresh fixation and rebuild the plan
                # so tax exemption is applied deterministically.
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
                                    "🔧 **פלט כלי (הערכת מס - אחרי קיבוע זכויות):**\n"
                                    + tax_after
                                    + "\n\n"
                                )

                            forced_fixation_chain_done = True

                current_step += 1
                continue

            except json.JSONDecodeError:
                logger.error("Failed to parse TOOL_CALL JSON: %s", tool_part_for_log)
                messages.append(
                    ChatMessage(
                        role="system",
                        content="Error: Invalid JSON in TOOL_CALL. Please try again.",
                    )
                )

                current_step += 1
                continue

        else:
            has_tool_results = any(
                (m.role == "system")
                and (
                    ("Tool Result (" in (m.content or ""))
                    or ("פלט כלי (" in (m.content or ""))
                )
                for m in messages
            )

            user_msg_for_default_date = find_last_user_message(request.messages) or ""
            birth_date_for_default_date = None
            gender_for_default_date = None
            if request.client_id is not None:
                client = (
                    db.query(Client)
                    .filter(Client.id == request.client_id)
                    .first()
                )
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
                    continue
                warning_msg = (
                    "אזהרה: אסור לך לענות על בקשות חישוב/השוואת קצבה ללא הרצת כלים. "
                    "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוקים בפורמט "
                    f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
                )
                messages.append(ChatMessage(role="system", content=warning_msg))
                current_step += 1
                continue

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
                    continue

            if is_net_request and (not no_tools_requested) and (not has_tool_results):
                warning_msg = (
                    "אזהרה: אסור לך לענות על שאלות נטו/אחרי מס ללא הרצת כלים. "
                    "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                    f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
                )
                messages.append(ChatMessage(role="system", content=warning_msg))
                current_step += 1
                continue

            if is_doc_request and not has_tool_results:
                is_tax_doc_request = is_tax_documents_request(original_user_msg)
                doc_tool = (
                    "GENERATE_TAX_DEDUCTION_DOCUMENTS"
                    if is_tax_doc_request
                    else "GENERATE_FULL_REPORT"
                )
                warning_msg = (
                    "אזהרה: המשתמש ביקש דוח/מסמך להורדה. אסור לך להשיב טקסט חופשי או לטעון שהופק דוח ללא הפעלת כלי GENERATE_* "
                    "והחזרת download_url. התשובה האחרונה שלך בוטלה. "
                    "כעת עליך להחזיר רק בלוק יחיד בפורמט "
                    f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "{doc_tool}", "arguments": {{}}}} ללא טקסט נוסף.'
                )
                messages.append(ChatMessage(role="system", content=warning_msg))
                current_step += 1
                continue

            final_reply = raw_reply
            break

    log_llm_event(
        request_id=request_id,
        event_type="final_answer",
        payload=final_reply,
        client_id=request.client_id,
    )

    if current_step >= max_steps:
        final_reply += "\n\n(הערה: עצרתי את רצף הפעולות האוטומטי כדי למנוע לולאה אינסופית)"

    if qa_summary_required:
        lowered_final = (final_reply or "").lower()
        if ("pass" not in lowered_final) and ("fail" not in lowered_final):
            if report_open_path:
                final_reply += (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח. "
                    f"open_path: {report_open_path}"
                )
            else:
                final_reply += "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח."

    return ChatResponse(
        reply=(
            (lambda txt: (
                ("הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n" + txt)
                if is_portfolio_analysis
                and isinstance(txt, str)
                and txt.strip()
                and ("הערכה" not in txt and "הערכה גסה" not in txt and "ראשונית" not in txt)
                else txt
            ))(sanitize_user_visible_text(forced_user_prefix + final_reply))
        ),
        computed_data=computed_data,
    )


def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    return run_pension_chat_stream_impl(request, db)
