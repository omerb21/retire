import json
import logging
import inspect
import re
import uuid
import time
import threading
import queue
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    build_forced_document_reply,
    build_pension_portfolio_update_after_commutation,
    build_pension_portfolio_update_after_transform,
    build_transform_accounts_from_target_plan_payload,
    format_transform_result_for_user,
    get_gross_for_tax_chaining,
    build_approval_request_ui_action,
    store_pending_approval_request,
    load_pending_approval_request,
    clear_pending_approval_request,
    load_latest_target_pension_plan,
    run_tax_projection_autochain,
    store_latest_target_pension_plan,
)

from datetime import date
from app.services.llm_chat.message_preparation import prepare_messages_with_context
from app.services.llm_chat.message_utils import (
    extract_user_approval_for_tool_call,
    extract_user_cancel_for_tool_call,
    extract_latest_approval_request,
    get_tool_call_approval_signature,
    extract_latest_target_pension_plan_payload,
    extract_target_pension_from_message,
    find_last_user_message,
    is_user_approval_intent_text,
)
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_partial_pension_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_stream,
    build_tool_call_message_content,
    build_tool_result_system_message_for_stream,
    compute_default_retirement_date_for_tool_call,
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    format_tool_output_for_user_stream,
    get_tool_display_name_hebrew,
    is_document_request,
    is_portfolio_breakdown_request,
    is_tax_documents_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_no_termination_request,
    is_no_tools_request,
    is_portfolio_analysis_request,
    is_process_termination_request,
    is_pension_commutation_request,
    is_qa_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_termination_change_request,
    is_transform_request,
    is_max_capital_request,
    extract_desired_monthly_income_from_text,
    is_data_awareness_request,
    is_list_all_financial_entities_request,
    parse_partial_pension_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_targeted_component_conversion_request,
    normalize_retirement_date_if_jan1_placeholder,
    parse_tool_call_from_reply,
    sanitize_user_visible_text,
    validate_tool_call_protocol_for_execution,
)
from app.services.llm_chat.chat_orchestration_helpers import maybe_clear_pension_portfolio_after_transform
from app.services.llm_chat.tool_execution import execute_tool_call
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)
from app.models.client import Client
from app.models import CurrentEmployer, EmployerGrant, GrantType
from app.utils.llm_chat_log import generate_request_id, log_llm_event, set_current_request_id
from app.services.llm_agent_tools_service import AgentToolsService

logger = logging.getLogger("app.llm_chat")

PC_LLM_MAX_RETRIES = 3
PC_LLM_TIMEOUT_SECONDS = 45.0
PC_LLM_BACKOFF_SECONDS = (0.75, 1.5, 3.0)


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
        extra={"endpoint": "stream"},
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


def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    stream_request_id = generate_request_id()
    set_current_request_id(stream_request_id)

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    if request.client_id is not None:
        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded
            try:
                logger.info(
                    "📦 Using DB pension_portfolio_snapshot (client_id=%s, accounts=%s, snapshot_at=%s)",
                    request.client_id,
                    len(effective_portfolio),
                    effective_snapshot_at,
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
        # Fallback: last 5+ digit token (avoid 2000/2008)
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

    def _is_system_results_request(text: str | None) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        if any(k in lowered for k in ("בנה", "תכנית", "תוכנית", "יעד", "תכנן", "מתווה")) and "קצבה" in lowered:
            return False
        if any(k in lowered for k in ("המר", "המרה", "בצע", "ביצוע", "עזיבת עבודה", "קיבוע")):
            return False
        if "קצבה" not in lowered:
            return False
        if any(k in lowered for k in ("כעת", "עכשיו", "במערכת", "מסך", "תוצאות", "בפועל", "סה\"כ", "סה")):
            return True
        if lowered.startswith("מה") and ("גובה" in lowered or "כמה" in lowered):
            return True
        return False

    def _format_system_results_from_cashflow(tool_result: str) -> str:
        try:
            parsed = json.loads(tool_result)
        except Exception:
            return tool_result

        if not isinstance(parsed, dict):
            return tool_result

        def _num(v: Any) -> float | None:
            try:
                if v is None:
                    return None
                return float(v)
            except Exception:
                return None

        gross = _num(parsed.get("projected_pension"))
        net = _num(parsed.get("projected_pension_net"))
        tax = _num(parsed.get("monthly_tax_deduction"))
        liquid = _num(parsed.get("total_liquid_capital"))
        retire_date = str(parsed.get("retirement_date") or "").strip()
        retire_age = parsed.get("retirement_age")
        exempt_monthly = _num(parsed.get("exempt_pension_monthly"))
        exemption_pct = _num(parsed.get("exemption_percentage"))

        lines: list[str] = []
        lines.append("תוצאות בפועל במערכת – סיכום קצבה")
        if retire_date:
            lines.append(f"תאריך פרישה שנבדק: {retire_date}")
        if retire_age is not None:
            try:
                lines.append(f"גיל בפרישה: {int(retire_age)}")
            except Exception:
                pass
        if gross is not None:
            lines.append(f"קצבה ברוטו: {gross:,.2f} ₪/חודש")
        if tax is not None:
            lines.append(f"ניכוי מס חודשי משוער: {tax:,.2f} ₪")
        if net is not None:
            lines.append(f"קצבה נטו משוערת (אחרי מס הכנסה בלבד): {net:,.2f} ₪/חודש")
        if (exemption_pct is not None) or (exempt_monthly is not None):
            pct_str = f"{exemption_pct:.1f}%" if exemption_pct is not None else "לא ידוע"
            exempt_str = f"{exempt_monthly:,.2f} ₪" if exempt_monthly is not None else "לא ידוע"
            lines.append(f"פטור מקיבוע זכויות שהוחל: {pct_str} | קצבה פטורה חודשית: {exempt_str}")
        if liquid is not None:
            lines.append(f"הון נזיל זמין במערכת: {liquid:,.2f} ₪")

        lines.append("")
        lines.append("הערה: התשובה נבנתה ישירות מתוצאות החישוב של המערכת (ללא חישוב פנימי של הסוכן).")
        return "\n".join(lines).strip()

    def _format_list_all_entities(tool_result: str) -> str:
        try:
            parsed = json.loads(tool_result)
        except Exception:
            parsed = None

        entities = parsed.get("entities") if isinstance(parsed, dict) else {}
        pension_funds = entities.get("pension_funds") if isinstance(entities, dict) else None
        capital_assets = entities.get("capital_assets") if isinstance(entities, dict) else None
        additional_incomes = entities.get("additional_incomes") if isinstance(entities, dict) else None

        lines: list[str] = []
        lines.append("הנתונים שנמצאים כרגע במערכת (DB) + תיק מסלקה שניטען:")

        # Portfolio snapshot (Maslaka) summary
        if isinstance(effective_portfolio, list):
            lines.append("")
            lines.append("תיק פנסיוני (מסלקה / טבלת מוצרים):")
            lines.append(f"- מספר חשבונות: {len(effective_portfolio)}")
            if effective_snapshot_at:
                lines.append(f"- תאריך snapshot: {effective_snapshot_at}")

        def _fmt_money(v: object) -> str:
            try:
                if v is None:
                    return "0"
                return f"{float(v):,.0f}"
            except Exception:
                return "0"

        # Additional incomes
        lines.append("")
        lines.append("הכנסות נוספות (AdditionalIncome):")
        if isinstance(additional_incomes, list) and additional_incomes:
            for ai in additional_incomes:
                if not isinstance(ai, dict):
                    continue
                desc = (ai.get("description") or ai.get("source_type") or "הכנסה").strip() if isinstance(ai.get("description") or ai.get("source_type") or "", str) else "הכנסה"
                amount = _fmt_money(ai.get("amount"))
                freq = ai.get("frequency") or ""
                start = ai.get("start_date") or ""
                end = ai.get("end_date") or ""
                suffix = f" | תוקף: {start}–{end}" if start or end else ""
                lines.append(f"- {desc}: {amount} ₪ ({freq}){suffix}")
        else:
            lines.append("- לא נמצאו הכנסות נוספות ב-DB")

        # Pension funds
        lines.append("")
        lines.append("קצבאות / קופות (PensionFund):")
        if isinstance(pension_funds, list) and pension_funds:
            for pf in pension_funds:
                if not isinstance(pf, dict):
                    continue
                name = (pf.get("fund_name") or "קופה").strip() if isinstance(pf.get("fund_name") or "", str) else "קופה"
                p_amount = _fmt_money(pf.get("pension_amount"))
                bal = _fmt_money(pf.get("balance"))
                lines.append(f"- {name}: קצבה={p_amount} ₪/חודש | יתרה={bal} ₪")
        else:
            lines.append("- לא נמצאו קצבאות/קופות ב-DB (ייתכן שעדיין לא בוצעה המרה מהמסלקה לנכסים)")

        # Capital assets
        lines.append("")
        lines.append("נכסי הון (CapitalAsset):")
        if isinstance(capital_assets, list) and capital_assets:
            for ca in capital_assets:
                if not isinstance(ca, dict):
                    continue
                name = (ca.get("asset_name") or "נכס").strip() if isinstance(ca.get("asset_name") or "", str) else "נכס"
                cur = _fmt_money(ca.get("current_value"))
                mi = _fmt_money(ca.get("monthly_income"))
                lines.append(f"- {name}: שווי={cur} ₪ | הכנסה חודשית={mi} ₪")
        else:
            lines.append("- לא נמצאו נכסי הון ב-DB")

        lines.append("")
        lines.append(
            "אם תרצה שאציג גם את פירוט חשבונות המסלקה (9 חשבונות) לפי שם תכנית/מספר חשבון/יתרה — תגיד: 'תציג פירוט תיק מסלקה'."
        )
        return "\n".join(lines).strip()

    def _format_data_awareness_snapshot(tool_result: str) -> str:
        try:
            parsed = json.loads(tool_result)
        except Exception:
            parsed = None

        counts = parsed.get("counts") if isinstance(parsed, dict) else {}

        def _count(name: str) -> int:
            try:
                return int(counts.get(name) or 0) if isinstance(counts, dict) else 0
            except Exception:
                return 0

        lines: list[str] = []
        lines.append("כן — אני עובד על בסיס הנתונים שנמצאים כרגע במערכת עבור הלקוח הזה.")

        if isinstance(effective_portfolio, list):
            lines.append("")
            lines.append("תיק פנסיוני (מסלקה / טבלת מוצרים):")
            lines.append(f"- מספר חשבונות שנטענו: {len(effective_portfolio)}")
            if effective_snapshot_at:
                lines.append(f"- תאריך snapshot אחרון: {effective_snapshot_at}")

        lines.append("")
        lines.append("מקורות/ישויות שנמצאו ב-DB:")
        lines.append(f"- קצבאות (PensionFund): {_count('pension_funds')}")
        lines.append(f"- נכסי הון (CapitalAsset): {_count('capital_assets')}")
        lines.append(f"- הכנסות נוספות (AdditionalIncome): {_count('additional_incomes')}")
        lines.append(f"- מעסיק נוכחי (CurrentEmployer): {_count('current_employers')}")

        lines.append("")
        lines.append(
            "אם תרצה לוודא *בדיוק* אילו מקורות נכללים בתזרים (למשל העסק/נכסי הון), תגיד: 'תציג לי את כל ההכנסות הנוספות' או 'תציג לי את כל נכסי ההון'."
        )
        return "\n".join(lines).strip()

    def _is_system_inventory_request(text: str | None) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        if any(k in lowered for k in ("מה יש", "תציג", "הצג", "פירוט", "פרט", "רשימה", "inventory", "snapshot")) and any(
            k in lowered for k in ("במערכת", "בפועל", "מסך", "נתונים")
        ):
            return True
        if "כל האלמנטים" in lowered or "כל הנתונים" in lowered:
            return True
        return False

    def _format_system_inventory_snapshot(tool_result: str) -> str:
        try:
            parsed = json.loads(tool_result)
        except Exception:
            return tool_result

        if not isinstance(parsed, dict):
            return tool_result

        counts = parsed.get("counts") if isinstance(parsed.get("counts"), dict) else {}
        entities = parsed.get("entities") if isinstance(parsed.get("entities"), dict) else {}

        def _count(name: str) -> int:
            try:
                return int(counts.get(name) or 0)
            except Exception:
                return 0

        def _first_name(items: Any, *fields: str) -> str | None:
            if not isinstance(items, list) or not items:
                return None
            first = items[0]
            if not isinstance(first, dict):
                return None
            for f in fields:
                val = first.get(f)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            return None

        lines: list[str] = []
        lines.append("מצב בפועל במערכת – Snapshot (DB)")
        generated_at = str(parsed.get("generated_at") or "").strip()
        if generated_at:
            lines.append(f"נוצר בתאריך: {generated_at}")
        lines.append("")
        lines.append("סיכום ישויות:")
        lines.append(f"- קצבאות (PensionFund): {_count('pension_funds')}")
        lines.append(f"- נכסי הון (CapitalAsset): {_count('capital_assets')}")
        lines.append(f"- הכנסות נוספות (AdditionalIncome): {_count('additional_incomes')}")
        lines.append(f"- מעסיק נוכחי (CurrentEmployer): {_count('current_employers')}")
        lines.append(f"- מענקי מעסיק נוכחי (EmployerGrant): {_count('employer_grants')}")
        lines.append(f"- מענקים ממעסיקים קודמים (Grant legacy): {_count('legacy_grants')}")
        lines.append(f"- אירועי עזיבת עבודה (TerminationEvent): {_count('termination_events')}")
        lines.append(f"- קיבוע זכויות (FixationResult): {_count('fixation_results')}")
        lines.append(f"- קצבאות מערכת קיבוע ישנה (Pension): {_count('pensions')}")
        lines.append(f"- היוונים מערכת קיבוע ישנה (Commutation): {_count('commutations')}")
        lines.append(f"- תרחישים/תוצאות (Scenario): {_count('scenarios')}")

        # Provide a tiny sample of what's inside, without dumping JSON.
        sample_pf = _first_name(entities.get("pension_funds"), "fund_name")
        sample_ca = _first_name(entities.get("capital_assets"), "asset_name")
        sample_ce = _first_name(entities.get("current_employers"), "employer_name")
        if any([sample_pf, sample_ca, sample_ce]):
            lines.append("")
            lines.append("דוגמאות (פריט ראשון מכל קטגוריה, אם קיים):")
            if sample_pf:
                lines.append(f"- קצבה: {sample_pf}")
            if sample_ca:
                lines.append(f"- נכס הון: {sample_ca}")
            if sample_ce:
                lines.append(f"- מעסיק נוכחי: {sample_ce}")

        lines.append("")
        lines.append(
            "הערה: התשובה נבנתה ישירות מ-DB (Snapshot) ללא השלמות/חישובים פנימיים של הסוכן. "
            "אם תרצה פירוט של קטגוריה ספציפית (למשל 'תציג את כל נכסי ההון'), תגיד איזו קטגוריה."
        )
        return "\n".join(lines).strip()

    if request.client_id is not None and (
        _is_target_plan_adjust_request(original_user_msg)
        or _is_target_plan_adjust_followup(original_user_msg, request.messages)
    ):
        payload = extract_latest_target_pension_plan_payload(request.messages)
        if payload is None:
            payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)

        def generate_adjust_reply():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            if not isinstance(payload, dict):
                yield (
                    "כדי לתקן את תכנית יעד הקצבה אני צריך תכנית יעד אחרונה קיימת. "
                    "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של <מספר>' (ואפשר לציין ברוטו/נטו)."
                )
                return

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
                yield (
                    "כדי לתקן את התכנית צריך להבהיר: היעד שביקשת הוא **ברוטו** או **נטו**?\n\n"
                    f"(התכנית האחרונה נבנתה במצב: {prev_mode})\n\n"
                    "כתוב אחת מהאפשרויות:\n"
                    "- '28000 ברוטו'\n"
                    "- '28000 נטו'"
                )
                return

            if target_val <= 0:
                yield (
                    "לא הצלחתי לקרוא את יעד הקצבה מתוך התכנית האחרונה. "
                    "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של 28000' (ברוטו/נטו)."
                )
                return

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
                request_id=stream_request_id,
            )
            try:
                store_latest_target_pension_plan(db=db, client_id=request.client_id, tool_result=plan_result)
            except Exception:
                pass
            yield (
                "🔧 **פלט כלי (בניית תכנית קצבה - תיקון):**\n"
                + sanitize_user_visible_text(
                    format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                )
            )

        return StreamingResponse(generate_adjust_reply(), media_type="text/plain; charset=utf-8")

    if request.client_id is not None and _is_system_results_request(original_user_msg):
        def generate_system_results():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

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

            tool_result = _execute_tool_call(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                {"retirement_date": default_retirement_date},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=stream_request_id,
            )

            if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
                yield sanitize_user_visible_text(tool_result)
                return

            yield sanitize_user_visible_text(_format_system_results_from_cashflow(tool_result))

        return StreamingResponse(generate_system_results(), media_type="text/plain; charset=utf-8")

    if request.client_id is not None and _is_system_inventory_request(original_user_msg):
        def generate_system_inventory():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = _execute_tool_call(
                "GET_SYSTEM_STATE_SNAPSHOT",
                {},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=stream_request_id,
            )

            if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
                yield sanitize_user_visible_text(tool_result)
                return

            yield sanitize_user_visible_text(_format_system_inventory_snapshot(tool_result))

        return StreamingResponse(generate_system_inventory(), media_type="text/plain; charset=utf-8")

    if request.client_id is not None and is_data_awareness_request(original_user_msg):
        def generate_data_awareness():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = _execute_tool_call(
                "GET_SYSTEM_STATE_SNAPSHOT",
                {},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=stream_request_id,
            )

            if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
                yield sanitize_user_visible_text(tool_result)
                return

            yield sanitize_user_visible_text(_format_data_awareness_snapshot(tool_result))

        return StreamingResponse(generate_data_awareness(), media_type="text/plain; charset=utf-8")

    if request.client_id is not None and is_list_all_financial_entities_request(original_user_msg):
        def generate_list_all_entities():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = _execute_tool_call(
                "GET_SYSTEM_STATE_SNAPSHOT",
                {},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=stream_request_id,
            )

            if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
                yield sanitize_user_visible_text(tool_result)
                return

            yield sanitize_user_visible_text(_format_list_all_entities(tool_result))

        return StreamingResponse(generate_list_all_entities(), media_type="text/plain; charset=utf-8")
    if is_portfolio_breakdown_request(original_user_msg):
        portfolio = effective_portfolio or []
        if portfolio:

            def generate_breakdown():
                if computed_data is not None:
                    computed_json = json.dumps(
                        {"type": "computed_data", "data": computed_data.model_dump()},
                        ensure_ascii=False,
                    )
                    yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

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
                yield breakdown or "אין תיק פנסיוני לניתוח."

            return StreamingResponse(generate_breakdown(), media_type="text/plain; charset=utf-8")

    if is_portfolio_analysis_request(original_user_msg):
        portfolio = effective_portfolio or []
        if portfolio:

            def generate_portfolio_analysis():
                if computed_data is not None:
                    computed_json = json.dumps(
                        {"type": "computed_data", "data": computed_data.model_dump()},
                        ensure_ascii=False,
                    )
                    yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

                full_name = None
                if request.client_id is not None:
                    try:
                        client = db.query(Client).filter(Client.id == request.client_id).first()
                        full_name = getattr(client, "full_name", None) if client else None
                    except Exception:
                        full_name = None

                title_name = (
                    str(full_name).strip()
                    if isinstance(full_name, str) and full_name.strip()
                    else ""
                )
                title = "כותרת: ניתוח תיק פנסיוני מלא"
                if title_name:
                    title = f"{title} — {title_name}"

                scenarios_text = ""
                if request.client_id is not None:
                    try:
                        client_obj = db.query(Client).filter(Client.id == request.client_id).first()
                        client_age = None
                        try:
                            client_age = (
                                client_obj.get_age()
                                if client_obj and hasattr(client_obj, "get_age")
                                else None
                            )
                        except Exception:
                            client_age = None

                        from app.services.retirement_age_service import (
                            DEFAULT_MALE_RETIREMENT_AGE,
                            get_retirement_age_simple,
                        )

                        legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)
                        try:
                            if (
                                client_obj
                                and getattr(client_obj, "birth_date", None)
                                and getattr(client_obj, "gender", None)
                            ):
                                legal_ret_age = int(
                                    get_retirement_age_simple(
                                        client_obj.birth_date,
                                        client_obj.gender,
                                    )
                                )
                        except Exception:
                            legal_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

                        retirement_age = legal_ret_age
                        if client_age is not None:
                            retirement_age = max(int(legal_ret_age), int(client_age))

                        agent_tools = AgentToolsService(
                            db=db,
                            client_id=request.client_id,
                            client_object=client_obj,
                            pension_portfolio_data=portfolio,
                        )
                        scenario_result = agent_tools.run_retirement_scenarios(
                            retirement_age=int(retirement_age),
                            pension_portfolio=portfolio,
                            include_current_employer_termination=False,
                        )
                        if scenario_result.get("success"):
                            scenarios_text = str(
                                scenario_result.get("explanation") or ""
                            ).strip()
                        else:
                            scenarios_text = ""
                    except Exception:
                        scenarios_text = ""

                analysis = (
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

                note = "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק."
                if analysis:
                    extra = ""
                    if isinstance(scenarios_text, str) and scenarios_text.strip():
                        extra = f"\n\n{scenarios_text}"
                    yield f"{note}\n\n{title}\n\n{analysis}{extra}"
                    return

                yield f"{title}\n\nאין תיק פנסיוני לניתוח."

            return StreamingResponse(generate_portfolio_analysis(), media_type="text/plain; charset=utf-8")

    def _stream_execute_tool_no_approval(tool_name: str, tool_args: dict[str, Any]) -> StreamingResponse:
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
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=True,
                request_id=stream_request_id,
            )

            try:
                clear_pending_approval_request(db=db, client_id=request.client_id)
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
    ) -> StreamingResponse:
        def generate_approval():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            try:
                store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
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
    is_net_request = is_net_pension_request(original_user_msg)
    is_doc_request = is_document_request(original_user_msg)
    is_tax_doc_request = is_tax_documents_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = is_no_tools_request(original_user_msg)
    force_max_exemption = is_max_exemption_request(original_user_msg)
    commutation_intent = is_pension_commutation_request(original_user_msg)
    explicit_transform = (not commutation_intent) and is_transform_request(original_user_msg)
    explicit_termination = is_process_termination_request(original_user_msg)
    termination_change = is_termination_change_request(original_user_msg)
    is_cashflow_request = is_retirement_cashflow_request(original_user_msg)
    is_comparison_request = is_retirement_comparison_request(original_user_msg)
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

    wants_fixation_documents = bool(
        is_tax_doc_request
        and any(token in lowered_user_msg for token in ("קיבוע", "זכויות", "161ד", "161d"))
    )

    explicit_cashflow_request = ("תזרים" in lowered_user_msg) or ("cashflow" in lowered_user_msg)

    if commutation_intent and request.client_id is not None:
        account_number = _extract_commutation_account_number(original_user_msg)
        if not account_number:
            def generate_commutation_need_account():
                if computed_data is not None:
                    computed_json = json.dumps(
                        {"type": "computed_data", "data": computed_data.model_dump()},
                        ensure_ascii=False,
                    )
                    yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
                yield (
                    "כדי לחשב היוון בצורה נכונה אני צריך לזהות *איזו קצבה* אתה רוצה להוון. "
                    "בבקשה ציין אחד מהבאים:\n"
                    "1) מספר חשבון/תיק ניכויים של הקצבה (5+ ספרות)\n"
                    "2) שם הקצבה כפי שמופיע במסך הקצבאות\n\n"
                    "בנוסף: האם הכוונה היא ל*סכום חד-פעמי* שתרצה לקבל, או ל*הפחתה חודשית מהקצבה*?"
                )

            return StreamingResponse(
                generate_commutation_need_account(),
                media_type="text/plain; charset=utf-8",
            )

    if (
        explicit_cashflow_request
        and request.client_id is not None
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
        and (not commutation_intent)
    ):
        def generate_cashflow():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

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
            tool_args: dict[str, Any] = {"retirement_date": default_retirement_date}
            if desired_income is not None:
                tool_args["desired_monthly_income"] = float(desired_income)

            tool_result = _execute_tool_call(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                tool_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=True,
                request_id=stream_request_id,
            )

            if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
                yield sanitize_user_visible_text(tool_result)
                return
            yield sanitize_user_visible_text(
                format_tool_output_for_user_stream("RUN_RETIREMENT_CASHFLOW_ANALYSIS", tool_result)
            )

        return StreamingResponse(generate_cashflow(), media_type="text/plain; charset=utf-8")

    max_capital_request = is_max_capital_request(original_user_msg)
    wants_execute_max_capital = max_capital_request and ("בצע" in lowered_user_msg)

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
            request_id=stream_request_id,
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
            return StreamingResponse(
                iter(["לא הצלחתי ליצור תרחיש 'מקסימום הון' במערכת."]),
                media_type="text/plain; charset=utf-8",
            )

        if wants_execute_max_capital:
            return _stream_request_approval(
                "EXECUTE_RETIREMENT_SCENARIO",
                {"scenario_id": int(scenario_id)},
                reason=(
                    "בקשת 'משיכה הונית מלאה' מחייבת שמירת קצבת מינימום 5,500 ₪. "
                    "אצור ואבצע את תרחיש 'מקסימום הון' (שמשאיר קצבת מינימום) רק לאחר אישור."
                ),
            )

        return StreamingResponse(
            iter([
                "יצרתי תרחיש 'מקסימום הון' (עם שמירת קצבת מינימום 5,500 ₪). "
                "אם תרצה לבצע אותו בפועל במערכת, כתוב: 'בצע'."
            ]),
            media_type="text/plain; charset=utf-8",
        )

    # Deterministic handling for fixation-rights document requests.
    # This avoids relying on the LLM to choose the correct GENERATE_* tool.
    if (
        request.client_id is not None
        and wants_fixation_documents
        and (not is_qa_mode)
        and (not no_tools_requested)
    ):
        return _stream_execute_tool_no_approval(
            "GENERATE_TAX_DEDUCTION_DOCUMENTS",
            {"document_type": "fixation_package"},
        )

    # Early deterministic handling for pension commutation requests.
    # Only run this path when the user provided a specific account identifier.
    # If the request is vague (no account number), fall back to the LLM flow.
    if commutation_intent and request.client_id is not None and (not is_doc_request) and (not is_qa_mode):
        account_number = _extract_commutation_account_number(original_user_msg)
        if account_number:
            def _item_to_dict(item: Any) -> dict:
                if isinstance(item, dict):
                    return item
                model_dump = getattr(item, "model_dump", None)
                if callable(model_dump):
                    dumped = model_dump()
                    return dumped if isinstance(dumped, dict) else {}
                raw = getattr(item, "__dict__", {})
                return raw if isinstance(raw, dict) else {}

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

            if fund is not None:
                # Deterministic execution requires an explicit amount (or 'כל היתרה').
                comm_amount = None
                try:
                    if _user_wants_full_balance(original_user_msg):
                        comm_amount = float(getattr(fund, "balance", 0) or 0)
                except Exception:
                    comm_amount = None

                if not comm_amount or comm_amount <= 0:
                    def generate_commutation_need_amount_existing():
                        if computed_data is not None:
                            computed_json = json.dumps(
                                {"type": "computed_data", "data": computed_data.model_dump()},
                                ensure_ascii=False,
                            )
                            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
                        yield (
                            "מצאתי את הקצבה המתאימה, אבל חסר לי סכום היוון. "
                            "כתוב סכום (למשל 50000 ₪) או 'כל היתרה'."
                        )

                    return StreamingResponse(
                        generate_commutation_need_amount_existing(),
                        media_type="text/plain; charset=utf-8",
                    )

                tax_type = "exempt" if "פטור" in (original_user_msg or "") else "taxable"
                exec_args = {
                    "pension_fund_id": int(getattr(fund, "id")),
                    "commutation_amount": float(comm_amount),
                    "commutation_date": date.today().isoformat(),
                    "commutation_type": tax_type,
                    "confirmed": True,
                }
                return _stream_request_approval(
                    "EXECUTE_PENSION_COMMUTATION",
                    exec_args,
                    reason="נדרש אישור לפני ביצוע היוון קצבה במערכת.",
                )

            def _digits_only(value: str | None) -> str:
                return "".join(ch for ch in (value or "") if ch.isdigit())

            target_digits = _digits_only(account_number)
            matched: dict | None = None
            for acc in (effective_portfolio or []):
                data = _item_to_dict(acc)
                acc_num = str(data.get("מספר_חשבון") or data.get("account_number") or "").strip()
                if not acc_num:
                    continue
                if acc_num == account_number:
                    matched = data
                    break
                if target_digits and _digits_only(acc_num) == target_digits:
                    matched = data
                    break

            if matched is not None:
                fund = None

            if fund is None:
                def generate_commutation_missing():
                    if computed_data is not None:
                        computed_json = json.dumps(
                            {"type": "computed_data", "data": computed_data.model_dump()},
                            ensure_ascii=False,
                        )
                        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

                    yield (
                        "כדי לבצע היוון אני צריך לזהות **קצבה קיימת במערכת** שמתאימה לחשבון שביקשת. "
                        f"לא מצאתי קצבה עם מספר חשבון/תיק ניכויים `{account_number}`.\n\n"
                        "אפשרויות:\n"
                        "1) כתוב את שם הקצבה כפי שהיא מופיעה במסך קצבאות, או את מזהה הקצבה (pension_fund_id).\n"
                        "2) אם הכוונה היא לתכנית בתיק המסלקה בלבד (לא קצבה קיימת), ציין: 'הפוך את החשבון לקצבה ואז בצע היוון'."
                    )

                return StreamingResponse(
                    generate_commutation_missing(),
                    media_type="text/plain; charset=utf-8",
                )

            comm_amount = None
            try:
                if _user_wants_full_balance(original_user_msg):
                    comm_amount = float(getattr(fund, "balance", 0) or 0)
            except Exception:
                comm_amount = None
            if not comm_amount or comm_amount <= 0:
                def generate_commutation_need_amount():
                    if computed_data is not None:
                        computed_json = json.dumps(
                            {"type": "computed_data", "data": computed_data.model_dump()},
                            ensure_ascii=False,
                        )
                        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
                    yield (
                        "מצאתי את הקצבה המתאימה, אבל חסר לי סכום היוון. "
                        "כתוב סכום (למשל 50000 ₪) או 'כל היתרה'."
                    )

                return StreamingResponse(
                    generate_commutation_need_amount(),
                    media_type="text/plain; charset=utf-8",
                )

            tax_type = "exempt" if "פטור" in (original_user_msg or "") else "taxable"
            exec_args = {
                "pension_fund_id": int(getattr(fund, "id")),
                "commutation_amount": float(comm_amount),
                "commutation_date": date.today().isoformat(),
                "commutation_type": tax_type,
                "confirmed": True,
            }
            return _stream_request_approval(
                "EXECUTE_PENSION_COMMUTATION",
                exec_args,
                reason="נדרש אישור לפני ביצוע היוון קצבה במערכת.",
            )

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
        and (not (wants_execute_target_plan or wants_fixation_execute))
    ):

        recent_user_text = "\n".join(
            [
                str(getattr(m, "content", ""))
                for m in (request.messages or [])
                if getattr(m, "role", None) == "user"
            ][-8:]
        )
        tool_args: dict[str, Any] = {"confirmed": True}
        tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
        termination_date_override = extract_process_termination_date_override(recent_user_text)
        if termination_date_override:
            tool_args["termination_date"] = termination_date_override
        tool_args.update(extract_process_termination_choice_overrides(original_user_msg))

        return _stream_execute_tool_no_approval("PROCESS_TERMINATION", tool_args)

    if (
        request.client_id is not None
        and (not no_tools_requested)
        and (not is_qa_mode)
        and (wants_execute_target_plan or wants_fixation_execute)
    ):

        def generate_forced_approval():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            # If the user explicitly asked to execute termination and it wasn't done yet,
            # we must request approval BEFORE running.
            if explicit_termination and (not termination_already_executed):
                recent_user_text = "\n".join(
                    [
                        str(getattr(m, "content", ""))
                        for m in (request.messages or [])
                        if getattr(m, "role", None) == "user"
                    ][-8:]
                )
                tool_args: dict[str, Any] = {"confirmed": True}
                tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
                termination_date_override = extract_process_termination_date_override(recent_user_text)
                if termination_date_override:
                    tool_args["termination_date"] = termination_date_override

                tool_result = _execute_tool_call(
                    "PROCESS_TERMINATION",
                    tool_args,
                    request.client_id,
                    db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=force_max_exemption,
                    user_approved=True,
                    request_id=stream_request_id,
                )

                try:
                    clear_pending_approval_request(db=db, client_id=request.client_id)
                except Exception:
                    pass

                out = sanitize_user_visible_text(
                    format_tool_output_for_user_stream("PROCESS_TERMINATION", tool_result)
                )
                yield out
                return

            if wants_execute_target_plan:
                payload = extract_latest_target_pension_plan_payload(request.messages)
                if payload is None:
                    payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
                if not isinstance(payload, dict):
                    yield "\n\nלא נמצאה תכנית יעד אחרונה לביצוע. קודם צריך לבנות תכנית יעד קצבה ואז לבקש לבצע אותה בפועל."
                    return

                accounts = build_transform_accounts_from_target_plan_payload(payload)
                if not accounts:
                    yield "\n\nלא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע אותה בפועל."
                    return

                transform_args: dict[str, Any] = {
                    "accounts": accounts,
                    "use_provided_accounts_only": True,
                    "ignore_blocked_balances": True,
                    "skip_non_convertible_accounts": True,
                }

                if wants_capital_transform:
                    transform_args.setdefault("default_conversion_type", "capital_asset")
                    transform_args["commute_pension_components"] = True

                tool_result = _execute_tool_call(
                    "TRANSFORM_FUNDS_TO_ASSETS",
                    transform_args,
                    request.client_id,
                    db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=force_max_exemption,
                    user_approved=True,
                    request_id=stream_request_id,
                )

                try:
                    clear_pending_approval_request(db=db, client_id=request.client_id)
                except Exception:
                    pass

                portfolio_update_marker = build_pension_portfolio_update_after_transform(
                    tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    tool_result=tool_result,
                    tool_args=transform_args,
                    current_pension_portfolio=effective_portfolio,
                )
                if portfolio_update_marker:
                    yield portfolio_update_marker

                yield format_transform_result_for_user(tool_result=tool_result)
                return

            if wants_fixation_execute:
                tool_args = {"save_result": True}

                tool_result = _execute_tool_call(
                    "CALCULATE_FIXATION_OF_RIGHTS",
                    tool_args,
                    request.client_id,
                    db,
                    pension_portfolio=effective_portfolio,
                    force_max_exemption=force_max_exemption,
                    user_approved=True,
                    request_id=stream_request_id,
                )

                try:
                    clear_pending_approval_request(db=db, client_id=request.client_id)
                except Exception:
                    pass

                out = sanitize_user_visible_text(
                    format_tool_output_for_user_stream("CALCULATE_FIXATION_OF_RIGHTS", tool_result)
                )
                yield out

        return StreamingResponse(generate_forced_approval(), media_type="text/plain; charset=utf-8")

    approval = extract_user_approval_for_tool_call(request.messages)
    cancelled = extract_user_cancel_for_tool_call(request.messages)
    if request.client_id is not None and (not no_tools_requested):
        try:
            pending_db = load_pending_approval_request(
                db=db,
                client_id=request.client_id,
            )
        except Exception:
            pending_db = None

        last_user_text = find_last_user_message(request.messages)
        if pending_db is not None and isinstance(last_user_text, str) and last_user_text:
            try:
                if "###USER_APPROVED###" in last_user_text:
                    after = last_user_text.split("###USER_APPROVED###", 1)[1].strip()
                    raw_json = after.strip("`").strip()
                    raw_json = raw_json.splitlines()[0] if raw_json else ""
                    parsed = json.loads(raw_json) if raw_json else None
                    if isinstance(parsed, dict):
                        raw_tool = parsed.get("tool_name")
                        raw_args = parsed.get("arguments")
                        pending_tool_name, pending_tool_args = pending_db
                        if (
                            isinstance(raw_tool, str)
                            and isinstance(raw_args, dict)
                            and isinstance(pending_tool_name, str)
                            and isinstance(pending_tool_args, dict)
                            and raw_tool == pending_tool_name
                        ):
                            merged_args = dict(pending_tool_args)
                            merged_args.update(raw_args)
                            approval = (pending_tool_name, merged_args)
                if "###USER_CANCELLED###" in last_user_text:
                    after = last_user_text.split("###USER_CANCELLED###", 1)[1].strip()
                    raw_json = after.strip("`").strip()
                    raw_json = raw_json.splitlines()[0] if raw_json else ""
                    parsed = json.loads(raw_json) if raw_json else None
                    if isinstance(parsed, dict):
                        raw_tool = parsed.get("tool_name")
                        raw_args = parsed.get("arguments")
                        pending_tool_name, pending_tool_args = pending_db
                        if (
                            isinstance(raw_tool, str)
                            and isinstance(raw_args, dict)
                            and isinstance(pending_tool_name, str)
                            and isinstance(pending_tool_args, dict)
                            and raw_tool == pending_tool_name
                        ):
                            merged_args = dict(pending_tool_args)
                            merged_args.update(raw_args)
                            cancelled = (pending_tool_name, merged_args)
            except Exception:
                pass

        if approval is not None and pending_db is not None:
            approved_tool_name, approved_tool_args = approval
            pending_tool_name, pending_tool_args = pending_db
            if (
                isinstance(approved_tool_name, str)
                and isinstance(pending_tool_name, str)
                and approved_tool_name == pending_tool_name
                and isinstance(approved_tool_args, dict)
                and isinstance(pending_tool_args, dict)
            ):
                if len(approved_tool_args.keys()) < len(pending_tool_args.keys()):
                    merged_args = dict(pending_tool_args)
                    merged_args.update(approved_tool_args)
                    approval = (approved_tool_name, merged_args)

        if cancelled is not None and pending_db is not None:
            cancelled_tool_name, cancelled_tool_args = cancelled
            pending_tool_name, pending_tool_args = pending_db
            if (
                isinstance(cancelled_tool_name, str)
                and isinstance(pending_tool_name, str)
                and cancelled_tool_name == pending_tool_name
                and isinstance(cancelled_tool_args, dict)
                and isinstance(pending_tool_args, dict)
            ):
                if len(cancelled_tool_args.keys()) < len(pending_tool_args.keys()):
                    merged_args = dict(pending_tool_args)
                    merged_args.update(cancelled_tool_args)
                    cancelled = (cancelled_tool_name, merged_args)

    if approval is None and request.client_id is not None and (not no_tools_requested):
        last_user_text = find_last_user_message(request.messages)
        if is_user_approval_intent_text(last_user_text):
            pending = extract_latest_approval_request(request.messages)
            if pending is not None:
                approval = pending
            else:
                pending_db = pending_db
                if pending_db is not None:
                    approval = pending_db
    if approval and request.client_id is not None and (not no_tools_requested):
        approved_tool_name, approved_tool_args = approval

        if (
            approved_tool_name == "PROCESS_TERMINATION"
            and termination_already_executed
            and (not termination_change)
            and wants_execute_target_plan
        ):
            def generate_execute_target_after_termination():
                if computed_data is not None:
                    computed_json = json.dumps(
                        {"type": "computed_data", "data": computed_data.model_dump()},
                        ensure_ascii=False,
                    )
                    yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

                payload = extract_latest_target_pension_plan_payload(request.messages)
                if payload is None:
                    payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
                if not isinstance(payload, dict):
                    yield "עזיבת עבודה כבר בוצעה. לא נמצאה תכנית יעד אחרונה לביצוע. קודם צריך לבנות תכנית יעד קצבה ואז לבקש לבצע אותה."
                    return

                accounts = build_transform_accounts_from_target_plan_payload(payload)
                if not accounts:
                    yield "עזיבת עבודה כבר בוצעה. לא הצלחתי לגזור רשימת רכיבים לביצוע מתוך תכנית היעד האחרונה. אנא בנה שוב תכנית יעד ואז בקש לבצע."
                    return

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
                    request_id=stream_request_id,
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
                if portfolio_update_marker:
                    yield portfolio_update_marker
                yield sanitize_user_visible_text(
                    format_tool_output_for_user_stream(
                        "TRANSFORM_FUNDS_TO_ASSETS",
                        transform_result,
                    )
                )

            return StreamingResponse(
                generate_execute_target_after_termination(),
                media_type="text/plain; charset=utf-8",
            )

        if approved_tool_name == "PROCESS_TERMINATION":
            overrides = extract_process_termination_choice_overrides(original_user_msg)
            if overrides and isinstance(approved_tool_args, dict):
                approved_tool_args = dict(approved_tool_args)
                approved_tool_args.update(overrides)

        if is_doc_request and not is_qa_mode:
            allowed_doc_tools = {"GENERATE_FULL_REPORT", "GENERATE_TAX_DEDUCTION_DOCUMENTS", "TRANSFORM_FUNDS_TO_ASSETS"}
            if approved_tool_name not in allowed_doc_tools:
                return StreamingResponse(
                    iter(
                        [
                            "אזהרה: המשתמש ביקש דוח/מסמך (ללא QA). הכלי המאושר אינו מותר במצב זה."
                        ]
                    ),
                    media_type="text/plain; charset=utf-8",
                )

        if is_qa_mode and approved_tool_name not in {
            "GET_PENSION_PRODUCTS",
            "TRANSFORM_FUNDS_TO_ASSETS",
            "GENERATE_FULL_REPORT",
        }:
            return StreamingResponse(
                iter(["אזהרה: במצב QA הכלי המאושר אינו מותר."]),
                media_type="text/plain; charset=utf-8",
            )

        def generate_approval_exec():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = _execute_tool_call(
                approved_tool_name,
                approved_tool_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=True,
                request_id=stream_request_id,
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
            if portfolio_update_marker:
                yield portfolio_update_marker

            forced_document_reply = build_forced_document_reply(
                tool_name=approved_tool_name,
                tool_result=tool_result,
            )
            if forced_document_reply:
                yield "\n\n" + sanitize_user_visible_text(forced_document_reply)
                return

            if approved_tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
                yield format_transform_result_for_user(tool_result=tool_result)
                return

            out = sanitize_user_visible_text(
                format_tool_output_for_user_stream(approved_tool_name, tool_result)
            )
            if is_portfolio_analysis and isinstance(out, str) and out.strip():
                if "הערכה" not in out and "הערכה גסה" not in out and "ראשונית" not in out:
                    out = (
                        "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                        + out
                    )
            yield out

        return StreamingResponse(generate_approval_exec(), media_type="text/plain; charset=utf-8")

    if cancelled and request.client_id is not None and (not no_tools_requested):
        cancelled_tool_name, _cancelled_tool_args = cancelled
        return StreamingResponse(
            iter([f"בוצעה ביטול להפעלת הכלי: {cancelled_tool_name}. לא בוצע שינוי במערכת."]),
            media_type="text/plain; charset=utf-8",
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

    log_llm_event(
        request_id=stream_request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    def generate(force_max_exemption_val: bool, req_id: str):
        if computed_data is not None:
            computed_json = json.dumps(
                {"type": "computed_data", "data": computed_data.model_dump()},
                ensure_ascii=False,
            )
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        current_pension_portfolio = effective_portfolio

        if explicit_transform and (not no_tools_requested) and (not is_doc_request) and (not is_qa_mode):
            partial_req = parse_partial_pension_conversion_request(original_user_msg)
            if partial_req is not None:
                acc_num, amount = partial_req
                partial_accounts = build_partial_pension_transform_accounts_from_portfolio(
                    pension_portfolio=current_pension_portfolio,
                    account_number=acc_num,
                    amount=amount,
                )
                if not partial_accounts:
                    yield (
                        f"לא הצלחתי למצוא חשבון מספר {acc_num} בתיק כדי לבצע המרה חלקית. "
                        "אנא ודא שמספר החשבון נכון ושיש סנאפשוט תיק מעודכן."
                    )
                    return
                tool_args: dict[str, Any] = {
                    "accounts": partial_accounts,
                    "use_provided_accounts_only": True,
                }
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
                        yield (
                            f"לא הצלחתי למצוא רכיבים מתאימים בחשבון מספר {acc_num} כדי לבצע המרה ממוקדת. "
                            "אנא ודא שמספר החשבון נכון ושיש רכיב רלוונטי בתיק."
                        )
                        return
                    tool_args = {
                        "accounts": targeted_accounts,
                        "use_provided_accounts_only": True,
                    }
                else:
                    prev_sev_req = parse_portfolio_wide_prev_employers_severance_conversion_request(original_user_msg)
                    if prev_sev_req is not None:
                        fields, conv_type = prev_sev_req
                        if conv_type == "blocked":
                            yield (
                                "מצאתי בקשה ל'פיצויים מעסיקים קודמים (רצף זכויות)', אך רכיב זה חסום להמרה במערכת "
                                "ודורש טיפול חיצוני/התחשבנות. אם תרצה, אוכל להציג באילו חשבונות הוא מופיע."
                            )
                            return
                        portfolio_accounts = build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio(
                            pension_portfolio=current_pension_portfolio,
                            conversion_type=conv_type,
                        )
                        if not portfolio_accounts:
                            yield "לא מצאתי בתיק רכיב 'פיצויים מעסיקים קודמים (רצף קצבה)' להמרה."
                            return
                        tool_args = {"accounts": portfolio_accounts, "use_provided_accounts_only": True}
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
                                yield "לא מצאתי בתיק רכיב 'פיצויים לאחר התחשבנות' להמרה."
                                return
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
                                    yield (
                                        "לא מצאתי בתיק רכיבי 'תגמולים אחרי 2000' להמרה. "
                                        "אם אתה מתכוון לרכיבים אחרים, ציין במפורש אילו רכיבים להמיר."
                                    )
                                    return
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
                                        yield "לא מצאתי בתיק קרנות השתלמות להמרה."
                                        return
                                    tool_args = {
                                        "accounts": edu_accounts,
                                        "use_provided_accounts_only": True,
                                    }
                                else:
                                    derived_accounts = build_transform_accounts_from_portfolio(current_pension_portfolio)
                                    if not derived_accounts:
                                        yield (
                                            "לא ניתן לבצע המרה כי אין תיק מסלקה/סנאפשוט זמין במערכת (pension_portfolio_snapshot ריק). "
                                            "כדי לבצע המרה מלאה צריך קודם לטעון תיק מסלקה כך שיופיע פירוט חשבונות."
                                        )
                                        return
                                    tool_args = {
                                        "accounts": derived_accounts,
                                    }

            if wants_capital_transform:
                tool_args.setdefault("default_conversion_type", "capital_asset")
                tool_args["commute_pension_components"] = True

            log_llm_event(
                request_id=req_id,
                event_type="tool_call",
                payload={"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": tool_args},
                client_id=request.client_id,
                extra={"endpoint": "stream"},
            )

            tool_result = _execute_tool_call(
                "TRANSFORM_FUNDS_TO_ASSETS",
                tool_args,
                request.client_id,
                db,
                pension_portfolio=current_pension_portfolio,
                force_max_exemption=False,
                request_id=req_id,
            )

            log_llm_event(
                request_id=req_id,
                event_type="tool_result",
                payload={"tool_name": "TRANSFORM_FUNDS_TO_ASSETS", "result": tool_result},
                client_id=request.client_id,
                extra={"endpoint": "stream"},
            )

            portfolio_update_marker = build_pension_portfolio_update_after_transform(
                tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                tool_result=tool_result,
                tool_args=tool_args,
                current_pension_portfolio=current_pension_portfolio,
            )

            if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
                yield portfolio_update_marker

            yield format_transform_result_for_user(tool_result=tool_result)
            return

        report_open_path: str | None = None
        qa_summary_required = False
        qa_summary_satisfied = False
        executed_tools: set[str] = set()
        forced_fixation_chain_done = False

        required_tools: set[str] = set()
        if not no_tools_requested:
            if is_doc_request:
                if is_tax_doc_request:
                    required_tools.add("GENERATE_TAX_DEDUCTION_DOCUMENTS")
                else:
                    required_tools.add("GENERATE_FULL_REPORT")

        tool_call_marker = "###TOOL_CALL###"
        max_steps = 5
        current_step = 0

        history_messages: list[ChatMessage] = list(messages)

        if wants_ignore_blocked:
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "המשתמש אישר להתעלם מיתרות חסומות/יתרות לטיפול במסך עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                        "אל תשאל שוב לאישור על זה. אל תבצע עזיבת עבודה בשיחה זו, והמשך עם שאר הכלים הרלוונטיים בלבד."
                    ),
                )
            )

        while current_step < max_steps:
            current_step += 1

            def _collect_llm_response_once(timeout_seconds: float) -> tuple[Optional[str], Optional[str]]:
                out_q: "queue.Queue[tuple[str, Any]]" = queue.Queue(maxsize=1)

                def _runner() -> None:
                    try:
                        buf: list[str] = []
                        for chunk in pension_llm_service.chat_stream(history_messages, request.client_id):
                            if chunk:
                                buf.append(str(chunk))
                        out_q.put(("ok", "".join(buf)))
                    except Exception as e:
                        out_q.put(("err", e))

                t = threading.Thread(target=_runner, daemon=True)
                t.start()
                t.join(timeout_seconds)
                if t.is_alive():
                    return None, f"timeout_after_{timeout_seconds}s"
                try:
                    status, payload = out_q.get_nowait()
                except Exception:
                    return None, "no_result"
                if status == "err":
                    try:
                        return None, str(payload) or "llm_error"
                    except Exception:
                        return None, "llm_error"
                try:
                    return str(payload), None
                except Exception:
                    return None, "invalid_response"

            def _collect_llm_response_with_retry() -> tuple[Optional[str], Optional[str]]:
                last_err: Optional[str] = None
                retries = int(PC_LLM_MAX_RETRIES or 1)
                timeout = float(PC_LLM_TIMEOUT_SECONDS or 0)
                backoffs = PC_LLM_BACKOFF_SECONDS
                for attempt in range(max(1, retries)):
                    resp, err = _collect_llm_response_once(timeout_seconds=timeout)
                    if isinstance(resp, str) and resp.strip():
                        return resp, None
                    last_err = err or "empty_reply"
                    if err and ("timeout_after_" in err or err in {"no_result", "llm_error"}):
                        try:
                            pension_llm_service.set_provider("ollama", None)
                        except Exception:
                            pass
                    if attempt < (retries - 1):
                        try:
                            delay = float(backoffs[attempt]) if attempt < len(backoffs) else float(backoffs[-1])
                        except Exception:
                            delay = 1.0
                        time.sleep(max(0.0, delay))
                return None, last_err

            full_response, llm_err = _collect_llm_response_with_retry()
            if not isinstance(full_response, str) or not full_response.strip():
                logger.error(
                    "Public chat LLM call failed (request_id=%s, client_id=%s, step=%s, error=%s)",
                    stream_request_id,
                    request.client_id,
                    current_step,
                    llm_err,
                )
                yield (
                    "שגיאה: לא הצלחתי לקבל תשובה מהמערכת כרגע (כשל זמני). "
                    "נסה שוב בעוד רגע. "
                    f"(request_id: {stream_request_id})"
                )
                break

            if tool_call_marker not in full_response:
                lowered = (full_response or "").lower()
                has_pass_fail = ("pass" in lowered) or ("fail" in lowered)

                user_msg_for_default_date = find_last_user_message(request.messages) or ""
                birth_date_for_default_date = None
                client = None
                if request.client_id is not None:
                    client = (
                        db.query(Client)
                        .filter(Client.id == request.client_id)
                        .first()
                    )
                    birth_date_for_default_date = (
                        getattr(client, "birth_date", None) if client else None
                    )

                gender_for_default_date = None
                try:
                    gender_for_default_date = getattr(client, "gender", None) if client else None
                except Exception:
                    gender_for_default_date = None

                default_retirement_date = compute_default_retirement_date_for_tool_call(
                    birth_date=birth_date_for_default_date,
                    gender=gender_for_default_date,
                    user_message=user_msg_for_default_date,
                )

                if is_qa_mode and no_tools_requested and not has_pass_fail:
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                                "אסור להחזיר TOOL_CALL. כעת החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר."
                            ),
                        )
                    )
                    continue

                missing_tools = required_tools.difference(executed_tools)

                if missing_tools and not no_tools_requested:
                    preferred_order = ["TRANSFORM_FUNDS_TO_ASSETS"]
                    if is_tax_doc_request:
                        preferred_order.append("GENERATE_TAX_DEDUCTION_DOCUMENTS")
                    else:
                        preferred_order.append("GENERATE_FULL_REPORT")
                    suggested_tool = next(
                        (name for name in preferred_order if name in missing_tools),
                        next(iter(missing_tools)),
                    )
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: טרם הושלמו שלבי החובה לבקשה. "
                                f"כעת עליך להפעיל את הכלי: {suggested_tool}. "
                                "החזר רק בלוקים בפורמט: "
                                '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                            ),
                        )
                    )
                    continue

                if qa_summary_required and not has_pass_fail:
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: במצב QA חובה לסיים בתשובת PASS/FAIL וסיכום קצר. "
                                "החזר כעת תשובת PASS או FAIL בלבד + 3-6 שורות סיכום + open_path של הדוח."
                            ),
                        )
                    )
                    continue

                has_tool_results = any(
                    (m.role == "system")
                    and (
                        ("Tool Result (" in (m.content or ""))
                        or ("פלט כלי (" in (m.content or ""))
                    )
                    for m in history_messages
                )

                if is_cashflow_request and (not no_tools_requested) and (not has_tool_results):
                    if _user_requested_target_pension_plan(user_msg_for_default_date):
                        warning_msg = (
                            "אזהרה: המשתמש ביקש מתווה/תכנית ליעד קצבה עם מספר. אסור לענות ללא הרצת הכלי הייעודי. "
                            "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                            '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "BUILD_TARGET_PENSION_PLAN", "arguments": {"target_monthly_pension": 28000}} ללא טקסט נוסף.'
                        )
                        history_messages.append(ChatMessage(role="system", content=warning_msg))
                        continue

                    warning_msg = (
                        "אזהרה: אסור לך לענות על בקשות חישוב/השוואת קצבה ללא הרצת כלים. "
                        "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                        f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
                    )
                    history_messages.append(ChatMessage(role="system", content=warning_msg))
                    continue

                if is_comparison_request and (not no_tools_requested):
                    cashflow_results = sum(
                        1
                        for m in history_messages
                        if (m.role == "system")
                        and ("Tool Result (RUN_RETIREMENT_CASHFLOW_ANALYSIS" in m.content)
                    )
                    if cashflow_results < 2:
                        warning_msg = (
                            "אזהרה: המשתמש ביקש השוואה בין שני תרחישי פרישה (למשל גיל 68 מול 69). "
                            "אסור לספק תשובה מספרית לפני שתי הרצות של RUN_RETIREMENT_CASHFLOW_ANALYSIS (אחת לכל תרחיש). "
                            "כעת עליך להחזיר רק בלוק יחיד בפורמט "
                            f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
                        )
                        history_messages.append(ChatMessage(role="system", content=warning_msg))
                        continue

                if is_net_request and (not no_tools_requested) and not has_tool_results:
                    warning_msg = (
                        "אזהרה: אסור לך לענות על שאלות נטו או אחרי מס ללא הרצת כלים. "
                        "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                        f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {{"retirement_date": "{default_retirement_date}"}}}} ללא טקסט נוסף.'
                    )
                    history_messages.append(ChatMessage(role="system", content=warning_msg))
                    continue

                if is_doc_request and not has_tool_results:
                    doc_tool = "GENERATE_TAX_DEDUCTION_DOCUMENTS" if is_tax_doc_request else "GENERATE_FULL_REPORT"
                    warning_msg = (
                        "אזהרה: המשתמש ביקש דוח/מסמך להורדה. אסור לך להשיב טקסט חופשי או לטעון שהופק מסמך ללא הפעלת כלי GENERATE_* "
                        "והחזרת download_url או open_path. התשובה האחרונה שלך בוטלה. "
                        "כעת עליך להחזיר רק בלוק יחיד בפורמט "
                        f'###TRANSPARENCY_LOG### {{...}} ואז ###RISK_REVIEW### {{...}} ואז ###TOOL_CALL### {{"name": "{doc_tool}", "arguments": {{}}}} ללא טקסט נוסף.'
                    )
                    history_messages.append(ChatMessage(role="system", content=warning_msg))
                    continue

                log_llm_event(
                    request_id=req_id,
                    event_type="final_answer",
                    payload=full_response,
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )
                if qa_summary_required and has_pass_fail:
                    qa_summary_satisfied = True
                final_out = sanitize_user_visible_text(full_response)
                if is_portfolio_analysis and isinstance(final_out, str) and final_out.strip():
                    final_out = "\n".join(
                        ln for ln in final_out.splitlines() if "מדרגות מס" not in ln
                    ).strip()
                if is_portfolio_analysis and isinstance(final_out, str) and final_out.strip():
                    if "הערכה" not in final_out and "הערכה גסה" not in final_out and "ראשונית" not in final_out:
                        final_out = (
                            "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                            + final_out
                        )
                yield final_out
                break

            try:
                parsed = parse_tool_call_from_reply(full_response)
                if parsed is None:
                    break

                text_part, tool_data = parsed
                tool_name = tool_data.get("name")
                tool_args = tool_data.get("arguments", {})

                if tool_name == "RUN_RETIREMENT_SCENARIOS" and is_portfolio_analysis:
                    if not isinstance(tool_args, dict):
                        tool_args = {}
                    if analysis_default_retirement_age is not None:
                        tool_args["retirement_age"] = analysis_default_retirement_age

                if _user_requested_target_pension_plan(original_user_msg) and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
                    history_messages.append(
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
                        history_messages.append(
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
                        continue

                if tool_name == "PROCESS_TERMINATION" and wants_ignore_blocked:
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש במפורש להתעלם מיתרות חסומות/עזיבת עבודה ולהמשיך ללא טיפול בעזיבת עבודה. "
                                "אסור לבצע עזיבת עבודה. כעת המשך ללא TOOL_CALL ובחר כלי אחר שמתאים לבקשה."
                            ),
                        )
                    )
                    continue

                if tool_name == "PROCESS_TERMINATION" and (not explicit_termination):
                    allow_change_after_execution = bool(
                        termination_already_executed and termination_change
                    )
                    if not allow_change_after_execution:
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: אסור לבצע עזיבת עבודה ללא בקשה מפורשת לביצוע עזיבת עבודה/פיצויים. "
                                    "כעת המשך ללא TOOL_CALL."
                                ),
                            )
                        )
                        continue

                if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
                    # Guardrail: if the user is asking about current-employer severance / work termination,
                    # do not transform the whole portfolio. The correct action is PROCESS_TERMINATION.
                    # This prevents accidental portfolio conversion when the user asked to withdraw an exempt grant
                    # during work termination.
                    if (
                        (not wants_ignore_blocked)
                        and (not is_doc_request)
                        and (not is_qa_mode)
                        and is_process_termination_request(original_user_msg)
                    ):
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: המשתמש ביקש עזיבת עבודה/פיצויים/מענק. "
                                    "אסור לבצע המרת תיק לנכסים. "
                                    "כעת אל תחזיר TOOL_CALL ל-TRANSFORM_FUNDS_TO_ASSETS. "
                                    "במקום זאת החזר TOOL_CALL ל-PROCESS_TERMINATION בלבד (עם confirmed=true)."
                                ),
                            )
                        )
                        continue

                    # Guardrail: pension commutation (היוון קצבה) must not be routed to TRANSFORM_FUNDS_TO_ASSETS.
                    if (
                        (not is_doc_request)
                        and (not is_qa_mode)
                        and is_pension_commutation_request(original_user_msg)
                    ):
                        history_messages.append(
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

                    if (not is_doc_request) and (not is_qa_mode) and (not explicit_transform):
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: אסור לבצע TRANSFORM_FUNDS_TO_ASSETS ללא בקשה מפורשת להמרה, "
                                    "או במסגרת בקשת דוח/QA. כעת המשך ללא TOOL_CALL."
                                ),
                            )
                        )
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
                            history_messages.append(
                                ChatMessage(
                                    role="system",
                                    content=(
                                        f"אזהרה: המשתמש ביקש המרה חלקית לחשבון {acc_num} אך החשבון לא נמצא בתיק. "
                                        "אסור לבצע המרת תיק מלאה. כעת אל תחזיר TOOL_CALL."
                                    ),
                                )
                            )
                            continue
                        if not isinstance(tool_args, dict):
                            tool_args = {}
                        tool_args["accounts"] = partial_accounts
                        tool_args["use_provided_accounts_only"] = True
                    else:
                        derived_accounts = build_transform_accounts_from_portfolio(
                            current_pension_portfolio
                        )
                        if derived_accounts:
                            tool_args_accounts = tool_args.get("accounts") if isinstance(tool_args, dict) else None
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
                                    enriched: list[dict] = []
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
                                    if enriched:
                                        tool_args["accounts"] = enriched
                                    else:
                                        tool_args["accounts"] = derived_accounts
                        else:
                            history_messages.append(
                                ChatMessage(
                                    role="system",
                                    content=(
                                        "אזהרה: TRANSFORM_FUNDS_TO_ASSETS דורש רשימת accounts תקינה. "
                                        "אין accounts ואין pension_portfolio שממנו ניתן לגזור accounts. "
                                        "כעת אל תחזיר TOOL_CALL."
                                    ),
                                )
                            )
                            continue

                    if wants_ignore_blocked:
                        tool_args["ignore_blocked_balances"] = True
                        tool_args["skip_non_convertible_accounts"] = True

                    if wants_capital_transform:
                        tool_args.setdefault("default_conversion_type", "capital_asset")
                        tool_args["commute_pension_components"] = True

                if no_tools_requested:
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                                "אסור לבצע TOOL_CALL. החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר, ללא כלים."
                            ),
                        )
                    )
                    continue

                if is_doc_request and not is_qa_mode:
                    allowed_doc_tools = {"GENERATE_FULL_REPORT"}
                    if (
                        isinstance(current_pension_portfolio, list)
                        and current_pension_portfolio
                    ):
                        allowed_doc_tools.add("TRANSFORM_FUNDS_TO_ASSETS")

                    if is_tax_doc_request:
                        allowed_doc_tools = {"GENERATE_TAX_DEDUCTION_DOCUMENTS"}
                        if (
                            isinstance(current_pension_portfolio, list)
                            and current_pension_portfolio
                        ):
                            allowed_doc_tools.add("TRANSFORM_FUNDS_TO_ASSETS")

                    if tool_name not in allowed_doc_tools:
                        history_messages.append(
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
                        continue

                if is_qa_mode and tool_name not in {
                    "GET_PENSION_PRODUCTS",
                    "TRANSFORM_FUNDS_TO_ASSETS",
                    "GENERATE_FULL_REPORT",
                }:
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: המשתמש ביקש בדיקת מערכת (QA). "
                                "במצב QA אסור להפעיל כלים שמשנים נתונים או עוסקים בתהליכים אחרים. "
                                "כעת עליך לבחור רק אחד מהכלים: GET_PENSION_PRODUCTS, TRANSFORM_FUNDS_TO_ASSETS, GENERATE_FULL_REPORT."
                            ),
                        )
                    )
                    continue

                ok, error_msg = validate_tool_call_protocol_for_execution(full_response)
                if not ok:
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                "אזהרה: אסור לבצע TOOL_CALL כי חסרים שלבי החובה/הפרוטוקול לא תקין. "
                                "כעת החזר רק בלוקים בפורמט: "
                                '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                            ),
                        )
                    )
                    continue

                log_llm_event(
                    request_id=req_id,
                    event_type="tool_call",
                    payload={"name": tool_name, "arguments": tool_args},
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )

                apply_max_exemption_if_requested(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    force_max_exemption=force_max_exemption_val,
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
                    history_messages.append(ChatMessage(role="assistant", content=text_part))

                tool_msg_content = build_tool_call_message_content(
                    tool_data, ensure_ascii=False
                )
                history_messages.append(ChatMessage(role="assistant", content=tool_msg_content))

                if tool_name in {"EXECUTE_PENSION_COMMUTATION", "SUBMIT_TAX_COMMUTATION"}:
                    reason = "נדרש אישור לפני ביצוע פעולה במערכת."
                    if tool_name == "EXECUTE_PENSION_COMMUTATION":
                        reason = "נדרש אישור לפני ביצוע היוון קצבה במערכת."
                    if tool_name == "SUBMIT_TAX_COMMUTATION":
                        reason = "נדרש אישור לפני הגשת/ביצוע קיבוע/פריסה במערכת."

                    try:
                        store_pending_approval_request(
                            db=db,
                            client_id=request.client_id,
                            tool_name=tool_name,
                            tool_args=tool_args if isinstance(tool_args, dict) else {},
                        )
                    except Exception:
                        pass

                    yield build_approval_request_ui_action(
                        tool_name=tool_name,
                        tool_args=tool_args if isinstance(tool_args, dict) else {},
                        reason=reason,
                        risk_level="high",
                        rag_sources=None,
                    )
                    return

                tool_db = SessionLocal()
                try:
                    tool_result = _execute_tool_call(
                        tool_name,
                        tool_args,
                        request.client_id,
                        tool_db,
                        pension_portfolio=current_pension_portfolio,
                        force_max_exemption=force_max_exemption_val,
                        agent_reply=full_response,
                        request_id=req_id,
                    )

                    if tool_name == "BUILD_TARGET_PENSION_PLAN" and request.client_id is not None:
                        try:
                            store_latest_target_pension_plan(
                                db=tool_db,
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
                        pending = extract_latest_approval_request(request.messages)
                        if pending is not None:
                            pending_tool, pending_args = pending
                            pending_sig = get_tool_call_approval_signature(
                                pending_tool, pending_args
                            )
                            current_sig = get_tool_call_approval_signature(
                                tool_name, tool_args if isinstance(tool_args, dict) else {}
                            )
                            if pending_sig and current_sig and pending_sig == current_sig:
                                log_llm_event(
                                    request_id=req_id,
                                    event_type="final_answer",
                                    payload=(
                                        "נדרש אישור לפני הפעלת כלי (כבר נשלחה בקשת אישור). ממתין לאישור בחלונית."
                                    ),
                                    client_id=request.client_id,
                                    extra={"endpoint": "stream"},
                                )
                                yield "נדרש אישור לפני הפעלת כלי. ממתין לאישור בחלונית."
                                break

                        log_llm_event(
                            request_id=req_id,
                            event_type="final_answer",
                            payload=tool_result,
                            client_id=request.client_id,
                            extra={"endpoint": "stream"},
                        )
                        yield tool_result
                        break

                    if tool_name:
                        executed_tools.add(tool_name)

                    portfolio_update_marker = build_pension_portfolio_update_after_transform(
                        tool_name=tool_name,
                        tool_result=tool_result,
                        tool_args=tool_args,
                        current_pension_portfolio=current_pension_portfolio,
                    )
                    if portfolio_update_marker:
                        yield "\n\n" + portfolio_update_marker

                    missing_tools_after = required_tools.difference(executed_tools)
                    if missing_tools_after:
                        preferred_order = ["TRANSFORM_FUNDS_TO_ASSETS"]
                        if is_tax_doc_request:
                            preferred_order.append("GENERATE_TAX_DEDUCTION_DOCUMENTS")
                        else:
                            preferred_order.append("GENERATE_FULL_REPORT")
                        suggested_tool = next(
                            (
                                name
                                for name in preferred_order
                                if name in missing_tools_after
                            ),
                        )
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "אזהרה: נותרו שלבי חובה לבקשה. "
                                    f"כעת עליך להפעיל את הכלי: {suggested_tool}. "
                                    "החזר רק בלוקים בפורמט: "
                                    '###TRANSPARENCY_LOG### {...} ואז ###RISK_REVIEW### {...} ואז ###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}} ללא טקסט נוסף.'
                                ),
                            )
                        )

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

                    forced_document_reply = build_forced_document_reply(
                        tool_name=tool_name,
                        tool_result=tool_result,
                    )

                    if forced_document_reply:
                        yield "\n\n" + sanitize_user_visible_text(forced_document_reply)
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    "המסמך הופק בהצלחה (UI_ACTION כבר נשלח למשתמש). "
                                    "כעת עליך להמשיך ולספק תשובת סיכום טקסטואלית מלאה בהתאם לבקשה (למשל QA / PASS/FAIL), "
                                    "ולהזכיר בבירור את open_path או קישור הדוח."
                                ),
                            )
                        )

                    user_tool_output = format_tool_output_for_user_stream(
                        tool_name, tool_result
                    )

                    tool_display = get_tool_display_name_hebrew(tool_name)
                    yield f"\n\n🔧 **פלט כלי ({tool_display}):**\n{sanitize_user_visible_text(user_tool_output)}"

                    log_llm_event(
                        request_id=req_id,
                        event_type="tool_result",
                        payload={"tool_name": tool_name, "result": tool_result},
                        client_id=request.client_id,
                        extra={"endpoint": "stream"},
                    )

                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=build_tool_result_system_message_for_stream(
                                tool_name, tool_result
                            ),
                        )
                    )

                    current_user_msg = find_last_user_message(request.messages)
                    is_net = is_net_pension_request(current_user_msg)
                    is_doc = is_document_request(current_user_msg)

                    logger.info(
                        "🔗 Checking Force Chaining (Stream): Tool=%s, IsNet=%s, Msg='%s'",
                        tool_name,
                        is_net,
                        current_user_msg[:50],
                    )

                    gross_for_tax = get_gross_for_tax_chaining(
                        is_net=is_net,
                        tool_name=tool_name,
                        tool_result=tool_result,
                    )

                    logger.info(
                        "🔗 Force Chaining (Stream): Tool=%s, IsNet=%s, GrossForTax=%s",
                        tool_name,
                        is_net,
                        gross_for_tax,
                    )

                    tax_result = run_tax_projection_autochain(
                        gross_for_tax=gross_for_tax,
                        execute_tool_call_fn=lambda name, args: _execute_tool_call(
                            name,
                            args,
                            request.client_id,
                            tool_db,
                            pension_portfolio=current_pension_portfolio,
                            force_max_exemption=force_max_exemption_val,
                            request_id=req_id,
                        ),
                    )
                    if tax_result is not None:
                        logger.info(
                            "🔗 Force Chaining (Stream): Running GET_TAX_PROJECTION with gross=%s",
                            gross_for_tax,
                        )
                        yield (
                            "\n\n🔧 **פלט כלי (הערכת מס - שרשור אוטומטי):**\n"
                            f"{tax_result}"
                        )
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=build_tax_result_system_message_for_stream(
                                    tax_result
                                ),
                            )
                        )

                    # Mandatory chaining for NET target pension plans (stream):
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
                                    tool_db,
                                    pension_portfolio=current_pension_portfolio,
                                    force_max_exemption=False,
                                    agent_reply=None,
                                    user_approved=True,
                                    request_id=req_id,
                                )
                                yield (
                                    "\n\n🔧 **פלט כלי (קיבוע זכויות - שרשור חובה):**\n"
                                    + sanitize_user_visible_text(
                                        format_tool_output_for_user_stream(
                                            "CALCULATE_FIXATION_OF_RIGHTS",
                                            fixation_result,
                                        )
                                    )
                                )
                                history_messages.append(
                                    ChatMessage(
                                        role="system",
                                        content=build_tool_result_system_message_for_stream(
                                            "CALCULATE_FIXATION_OF_RIGHTS",
                                            fixation_result,
                                        ),
                                    )
                                )

                                plan_result = _execute_tool_call(
                                    "BUILD_TARGET_PENSION_PLAN",
                                    {"target_monthly_pension": float(target_val), "target_is_net": True},
                                    request.client_id,
                                    tool_db,
                                    pension_portfolio=current_pension_portfolio,
                                    force_max_exemption=False,
                                    agent_reply=None,
                                    user_approved=True,
                                    request_id=req_id,
                                )
                                yield (
                                    "\n\n🔧 **פלט כלי (בניית תכנית קצבה - אחרי קיבוע זכויות):**\n"
                                    + sanitize_user_visible_text(
                                        format_tool_output_for_user_stream(
                                            "BUILD_TARGET_PENSION_PLAN",
                                            plan_result,
                                        )
                                    )
                                )
                                history_messages.append(
                                    ChatMessage(
                                        role="system",
                                        content=build_tool_result_system_message_for_stream(
                                            "BUILD_TARGET_PENSION_PLAN",
                                            plan_result,
                                        ),
                                    )
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
                                        tool_db,
                                        pension_portfolio=current_pension_portfolio,
                                        force_max_exemption=False,
                                        agent_reply=None,
                                        user_approved=True,
                                        request_id=req_id,
                                    ),
                                )
                                if tax_after is not None:
                                    yield (
                                        "\n\n🔧 **פלט כלי (הערכת מס - אחרי קיבוע זכויות):**\n" + tax_after
                                    )
                                    history_messages.append(
                                        ChatMessage(
                                            role="system",
                                            content=build_tax_result_system_message_for_stream(
                                                tax_after
                                            ),
                                        )
                                    )

                                forced_fixation_chain_done = True

                finally:
                    tool_db.close()

            except Exception as e:
                logger.error("Stream Tool Execution Failed: %s", e, exc_info=True)
                yield f"\n\n(Error executing tool: {sanitize_user_visible_text(str(e))})"
                break

        if qa_summary_required and not qa_summary_satisfied:
            if report_open_path:
                yield (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח. "
                    f"open_path: {report_open_path}"
                )
            else:
                yield "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח."

        if not no_tools_requested:
            missing_tools_final = required_tools.difference(executed_tools)
            if missing_tools_final:
                yield (
                    "\n\nFAIL - לא הושלמו שלבי החובה לבקשה. חסרים הכלים: "
                    + ", ".join(sorted(missing_tools_final))
                )

    return StreamingResponse(
        generate(force_max_exemption, stream_request_id),
        media_type="text/plain; charset=utf-8",
    )
