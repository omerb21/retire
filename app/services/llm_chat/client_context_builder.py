import json
import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    AdditionalIncome,
    CapitalAsset,
    Commutation,
    CurrentEmployer,
    FixationResult,
    PensionFund,
    Scenario,
)
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.documents.data_fetchers.client_data import fetch_client_data
from app.services.llm_chat.message_utils import extract_executed_tools_from_history
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.state_tools import get_agent_state_json
from app.services.llm_chat.orchestration_utils import is_portfolio_analysis_request
from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot_models
from app.services.retirement_age_service import calculate_retirement_age
from app.services.tax_data import TaxBracketsService

logger = logging.getLogger("app.llm_chat")


def _find_last_user_text(messages: list[ChatMessage]) -> str:
    for m in reversed(messages or []):
        if getattr(m, "role", None) == "user" and isinstance(getattr(m, "content", None), str):
            return m.content
    return ""


def _is_portfolio_summary_only_request(user_text: str) -> bool:
    lowered = (user_text or "").lower()
    if not lowered.strip():
        return False

    planning_intent_keywords = [
        "קצבה",
        "פנסיה",
        "יעד קצבה",
        "יעד",
        "תכנית משיכה",
        "תוכנית משיכה",
        "מתווה משיכה",
        "משיכה",
        "build_target_pension_plan",
        "25k",
        "k",
    ]
    if any(k in lowered for k in planning_intent_keywords) and any(
        k in lowered for k in ["צור", "בנה", "תכנן", "תכנון", "תכנית", "תוכנית", "מתווה", "אני צריך", "אני זקוק"]
    ):
        return False

    has_summary_intent = any(
        k in lowered
        for k in [
            "סכם",
            "סיכום",
            "תסכם",
            "תסכום",
            "סכמ",
            "summary",
        ]
    )
    refers_to_portfolio = any(
        k in lowered
        for k in [
            "תיק פנסיוני",
            "פורטפוליו",
            "טבלת המוצרים",
            "מסלקה",
            "מוצרים מובילים",
        ]
    )
    if has_summary_intent and refers_to_portfolio:
        return True
    if "תיק פנסיוני" in lowered and any(k in lowered for k in ["נתונים", "הצג", "תציג", "תפרט"]):
        return True
    return False


def build_llm_context_parts(
    *,
    request: ChatRequest,
    db: Session,
    messages: list[ChatMessage],
) -> list[str]:
    if request.client_id is None:
        return []

    client = fetch_client_data(db, request.client_id)
    if client is None:
        return []

    last_user_text = _find_last_user_text(messages)
    portfolio_summary_only = _is_portfolio_summary_only_request(last_user_text)

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    if not effective_portfolio and request.client_id is not None:
        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded

    if portfolio_summary_only:
        if effective_portfolio and len(effective_portfolio) > 0:
            context_parts: list[str] = []
            context_parts.extend(
                build_pension_portfolio_context(
                    effective_portfolio,
                    user_message=last_user_text,
                    snapshot_at=effective_snapshot_at,
                )
            )
            context_parts.append("")
            context_parts.append(
                "**הנחיה לסוכן:** זהו שלב 1 (נתונים גולמיים). הצג רק את הנתונים שמופיעים בתיק הפנסיוני למעלה. "
                "אל תשתמש במקורות אחרים במערכת (תרחישים/נכסים/מעסיקים) ואל תוסיף פרשנות רגולטורית ללא עמודה/שדה מפורש."
            )
            return context_parts
        return []

    age = client.get_age() if hasattr(client, "get_age") else None
    analysis_default_retirement_age: int | None = None
    if is_portfolio_analysis_request(last_user_text):
        try:
            from app.services.retirement_age_service import get_retirement_age_simple

            legal_ret_age = None
            try:
                if getattr(client, "birth_date", None) and getattr(client, "gender", None):
                    legal_ret_age = int(get_retirement_age_simple(client.birth_date, client.gender))
            except Exception:
                legal_ret_age = None

            if legal_ret_age is not None:
                analysis_default_retirement_age = max(int(legal_ret_age), int(age or legal_ret_age))
            else:
                analysis_default_retirement_age = int(age) if age is not None else None
        except Exception:
            analysis_default_retirement_age = None

    client_parts: list[str] = []
    if client.full_name:
        client_parts.append(f"שם: {client.full_name}")
    if age is not None:
        client_parts.append(f"גיל: {age}")
    if client.gender:
        client_parts.append(f"מין: {client.gender}")
    if client.marital_status:
        client_parts.append(f"מצב משפחתי: {client.marital_status}")
    if client.annual_salary is not None:
        monthly_salary = client.annual_salary / 12
        client_parts.append(f"שכר חודשי: {monthly_salary:,.0f} ₪")

    pension_funds = db.query(PensionFund).filter(PensionFund.client_id == request.client_id).all()

    capital_assets = db.query(CapitalAsset).filter(CapitalAsset.client_id == request.client_id).all()

    total_pension_balance: float = 0.0
    total_existing_pension: float = 0.0
    total_capital_value: float = 0.0
    pension_sources_list: list[str] = []

    for pf in pension_funds:
        balance = float(pf.balance or 0)
        existing_pension = float(pf.pension_amount or 0)
        total_pension_balance += balance
        total_existing_pension += existing_pension

        if balance > 0 or existing_pension > 0:
            source_desc = f"• {pf.fund_name or 'קרן ללא שם'} ({pf.fund_type or 'לא ידוע'})"
            if existing_pension > 0:
                source_desc += f": קצבה קיימת {existing_pension:,.0f} ₪/חודש"
            elif balance > 0:
                source_desc += f": יתרה {balance:,.0f} ₪"
            pension_sources_list.append(source_desc)

    for ca in capital_assets:
        value = float(ca.current_value or 0)
        if value <= 0:
            value = float(ca.monthly_income or 0)
        total_capital_value += value

        if value > 0:
            pension_sources_list.append(
                f"• {ca.asset_name or 'נכס ללא שם'} ({ca.asset_type or 'הון'}): {value:,.0f} ₪"
            )

    scenarios_summary_parts: list[str] = []
    retirement_age_for_summary: int | None = None
    best_pension: float = 0.0
    best_capital: float = 0.0
    best_npv: float = 0.0

    scenarios = (
        db.query(Scenario)
        .filter(Scenario.client_id == request.client_id)
        .order_by(Scenario.created_at.desc())
        .limit(30)
        .all()
    )

    def _build_organized_scenarios(*, require_retirement_age: int | None) -> tuple[dict[str, dict], int | None, float, float, float]:
        organized_local: dict[str, dict] = {}
        retirement_age_local: int | None = None
        best_pension_local: float = 0.0
        best_capital_local: float = 0.0
        best_npv_local: float = 0.0

        for scenario in scenarios:
            try:
                params = json.loads(scenario.parameters) if scenario.parameters else {}
                scenario_type = params.get("scenario_type", "unknown")
                age_param = params.get("retirement_age")
                if require_retirement_age is not None and age_param != require_retirement_age:
                    continue
                if retirement_age_local is None and isinstance(age_param, int):
                    retirement_age_local = age_param

                if scenario.summary_results:
                    summary_data = json.loads(scenario.summary_results)
                    organized_local[scenario_type] = summary_data

                    pension_val = summary_data.get("total_pension_monthly", 0) or 0
                    capital_val = summary_data.get("total_capital", 0) or 0
                    npv_val = summary_data.get("estimated_npv", 0) or 0

                    if pension_val > best_pension_local:
                        best_pension_local = pension_val
                    if capital_val > best_capital_local:
                        best_capital_local = capital_val
                    if npv_val > best_npv_local:
                        best_npv_local = npv_val
            except Exception:
                continue

        return (
            organized_local,
            retirement_age_local,
            best_pension_local,
            best_capital_local,
            best_npv_local,
        )

    organized, retirement_age_for_summary, best_pension, best_capital, best_npv = _build_organized_scenarios(
        require_retirement_age=analysis_default_retirement_age
    )
    if (not organized) and analysis_default_retirement_age is not None:
        organized, retirement_age_for_summary, best_pension, best_capital, best_npv = _build_organized_scenarios(
            require_retirement_age=None
        )

    if organized:
        ordered_keys = [
            ("scenario_1_max_pension", "תרחיש 1"),
            ("scenario_2_max_capital", "תרחיש 2"),
            ("scenario_3_max_npv", "תרחיש 3"),
        ]
        seen = set()

        for key, label in ordered_keys:
            if key not in organized:
                continue
            s = organized.get(key) or {}
            total_pension = s.get("total_pension_monthly", 0) or 0
            total_capital = s.get("total_capital", 0) or 0
            estimated_npv = s.get("estimated_npv", 0) or 0

            advantage = ""
            if "max_pension" in key:
                advantage = " [ממקסם קצבה]"
            elif "max_capital" in key:
                advantage = " [ממקסם הון]"
            elif "max_npv" in key:
                advantage = " [ממקסם ערך נוכחי]"

            scenarios_summary_parts.append(
                f"• {label}{advantage}: קצבה {total_pension:,.0f} ₪/חודש, "
                f"הון {total_capital:,.0f} ₪, NPV {estimated_npv:,.0f} ₪"
            )
            seen.add(key)

        extra_keys = [k for k in organized.keys() if k not in seen]
        extra_idx = 4
        for key in sorted(extra_keys):
            s = organized.get(key) or {}
            total_pension = s.get("total_pension_monthly", 0) or 0
            total_capital = s.get("total_capital", 0) or 0
            estimated_npv = s.get("estimated_npv", 0) or 0
            scenarios_summary_parts.append(
                f"• תרחיש {extra_idx}: קצבה {total_pension:,.0f} ₪/חודש, "
                f"הון {total_capital:,.0f} ₪, NPV {estimated_npv:,.0f} ₪"
            )
            extra_idx += 1

    fixation_info: dict = {}
    latest_fixation = (
        db.query(FixationResult)
        .filter(FixationResult.client_id == request.client_id)
        .order_by(FixationResult.created_at.desc())
        .first()
    )
    if latest_fixation and latest_fixation.raw_result:
        try:
            fixation_data = (
                latest_fixation.raw_result
                if isinstance(latest_fixation.raw_result, dict)
                else json.loads(latest_fixation.raw_result)
            )
            fixation_info = {
                "exempt_capital_remaining": latest_fixation.exempt_capital_remaining or 0,
                "used_commutation": latest_fixation.used_commutation or 0,
                "exempt_pension_percentage": fixation_data.get("exemption_summary", {}).get(
                    "exempt_pension_percentage", 0
                ),
            }
        except Exception:
            pass

    current_employers = db.query(CurrentEmployer).filter(CurrentEmployer.client_id == request.client_id).all()

    employers_info: list[str] = []
    total_severance: float = 0.0
    for emp in current_employers:
        years_worked = 0
        if emp.start_date:
            years_worked = (date.today() - emp.start_date).days / 365.25
        severance = float(emp.severance_accrued or 0)
        total_severance += severance

        emp_desc = f"• {emp.employer_name}: {years_worked:.1f} שנים"
        if severance > 0:
            emp_desc += f", פיצויים צבורים: {severance:,.0f} ₪"
        if emp.last_salary:
            emp_desc += f", שכר אחרון: {emp.last_salary:,.0f} ₪"
        employers_info.append(emp_desc)

    commutations = (
        db.query(Commutation)
        .join(PensionFund, Commutation.pension_id == PensionFund.id)
        .filter(PensionFund.client_id == request.client_id)
        .all()
    )

    total_commutation: float = 0.0
    commutation_info: list[str] = []
    for comm in commutations:
        amount = float(comm.commutation_amount or 0)
        total_commutation += amount
        if amount > 0:
            commutation_info.append(
                f"• היוון {amount:,.0f} ₪ (פגיעה בפטור: {comm.impact_on_exemption or 0:,.0f} ₪)"
            )

    additional_incomes = db.query(AdditionalIncome).filter(AdditionalIncome.client_id == request.client_id).all()

    total_additional_income: float = 0.0
    additional_income_info: list[str] = []
    for inc in additional_incomes:
        monthly = float(inc.monthly_amount or 0)
        total_additional_income += monthly
        if monthly > 0:
            tax_status = "פטור" if inc.tax_treatment == "exempt" else "חייב במס"
            additional_income_info.append(
                f"• {inc.income_name or 'הכנסה'}: {monthly:,.0f} ₪/חודש ({tax_status})"
            )

    context_parts: list[str] = []

    if client_parts:
        context_parts.append("📋 **פרטי הלקוח**")
        context_parts.append(" | ".join(client_parts))

    financial_summary: list[str] = []
    if total_pension_balance > 0:
        financial_summary.append(f"יתרות בקרנות: {total_pension_balance:,.0f} ₪")
    if total_existing_pension > 0:
        financial_summary.append(f"קצבאות קיימות: {total_existing_pension:,.0f} ₪/חודש")
    if total_capital_value > 0:
        financial_summary.append(f"נכסי הון: {total_capital_value:,.0f} ₪")
    if total_severance > 0:
        financial_summary.append(f"פיצויים צבורים: {total_severance:,.0f} ₪")
    if total_additional_income > 0:
        financial_summary.append(f"הכנסות נוספות: {total_additional_income:,.0f} ₪/חודש")

    if financial_summary:
        context_parts.append("")
        context_parts.append("💰 **סיכום פיננסי**")
        context_parts.append(" | ".join(financial_summary))

    if fixation_info:
        context_parts.append("")
        context_parts.append("📜 **קיבוע זכויות**")
        exempt_cap = fixation_info.get("exempt_capital_remaining", 0)
        exempt_pct = fixation_info.get("exempt_pension_percentage", 0) * 100
        used_comm = fixation_info.get("used_commutation", 0)
        context_parts.append(
            f"יתרת הון פטורה: {exempt_cap:,.0f} ₪ | "
            f"אחוז קצבה פטורה: {exempt_pct:.1f}% | "
            f"היוונים שנוצלו: {used_comm:,.0f} ₪"
        )

    if employers_info:
        context_parts.append("")
        context_parts.append("🏢 **מעסיקים**")
        for emp_line in employers_info[:3]:
            context_parts.append(emp_line)
        if len(employers_info) > 3:
            context_parts.append(f"  (ועוד {len(employers_info) - 3} מעסיקים)")

    if commutation_info:
        context_parts.append("")
        context_parts.append("💸 **היוונים**")
        context_parts.append(f"סה\"כ היוונים: {total_commutation:,.0f} ₪")

    if additional_income_info:
        context_parts.append("")
        context_parts.append("💵 **הכנסות נוספות**")
        for inc_line in additional_income_info[:3]:
            context_parts.append(inc_line)

    if pension_sources_list:
        context_parts.append("")
        context_parts.append("📊 **מקורות קצבה עיקריים**")
        for source in pension_sources_list[:5]:
            context_parts.append(source)
        if len(pension_sources_list) > 5:
            context_parts.append(f"  (ועוד {len(pension_sources_list) - 5} מקורות נוספים)")

    if scenarios_summary_parts:
        age_text = f" לגיל {retirement_age_for_summary}" if retirement_age_for_summary else ""
        context_parts.append("")
        context_parts.append(f"🎯 **תרחישי פרישה{age_text}**")
        for scenario_line in scenarios_summary_parts:
            context_parts.append(scenario_line)

        context_parts.append("")
        context_parts.append("📈 **סיכום תרחישים**")
        context_parts.append(
            f"קצבה מקסימלית אפשרית: {best_pension:,.0f} ₪/חודש | "
            f"הון מקסימלי: {best_capital:,.0f} ₪ | "
            f"NPV מקסימלי: {best_npv:,.0f} ₪"
        )

    if best_pension > 0 or total_existing_pension > 0:
        context_parts.append("")
        context_parts.append("🔍 **ניתוח מצב**")
        current_pension = total_existing_pension + best_pension
        if client.annual_salary:
            target_pension = (client.annual_salary / 12) * 0.7
            gap = target_pension - current_pension
            if gap > 0:
                context_parts.append(
                    f"יעד מומלץ (70% מהשכר): {target_pension:,.0f} ₪/חודש | "
                    f"פער מהיעד: {gap:,.0f} ₪/חודש"
                )
            else:
                context_parts.append(
                    f"✅ הקצבה הצפויה ({current_pension:,.0f} ₪) עומדת ביעד של 70% מהשכר"
                )
    elif not pension_sources_list and not scenarios_summary_parts:
        context_parts.append("")
        context_parts.append("⚠️ **שים לב**: לא נמצאו מקורות קצבה או תרחישים שמורים ללקוח זה.")
        context_parts.append("ייתכן שצריך להעלות תיק פנסיוני ולהריץ תרחישי פרישה.")

    try:
        if client.birth_date and client.gender:
            retirement_info = calculate_retirement_age(client.birth_date, client.gender)
            try:
                legal_retirement_age = int(retirement_info.get("age_years") or 67)
                legal_retirement_age = legal_retirement_age + (
                    1 if int(retirement_info.get("age_months") or 0) > 0 else 0
                )
            except Exception:
                legal_retirement_age = 67
            retirement_date = retirement_info.get("retirement_date")

            context_parts.append("")
            context_parts.append("👤 **גיל פרישה חוקי**")
            if client.gender == "נקבה":
                context_parts.append(
                    f"גיל פרישה חוקי: {legal_retirement_age} (נשים לפי תאריך לידה)"
                )
            else:
                context_parts.append(f"גיל פרישה חוקי: {legal_retirement_age}")
            if retirement_date:
                context_parts.append(f"תאריך זכאות: {retirement_date}")
    except Exception:
        pass

    try:
        _unused_current_year = date.today().year
        _unused_tax_brackets = TaxBracketsService.get_tax_brackets(_unused_current_year)
    except Exception:
        pass

    if len(organized) >= 2:
        context_parts.append("")
        context_parts.append("⚖️ **השוואת תרחישים**")

        best_for_pension = max(organized.items(), key=lambda x: x[1].get("total_pension_monthly", 0))
        best_for_capital = max(organized.items(), key=lambda x: x[1].get("total_capital", 0))
        best_for_npv = max(organized.items(), key=lambda x: x[1].get("estimated_npv", 0))

        context_parts.append(
            f"  • הכי טוב לקצבה: {best_for_pension[0]} ({best_for_pension[1].get('total_pension_monthly', 0):,.0f} ₪/חודש)"
        )
        context_parts.append(
            f"  • הכי טוב להון: {best_for_capital[0]} ({best_for_capital[1].get('total_capital', 0):,.0f} ₪)"
        )
        context_parts.append(
            f"  • הכי טוב ל-NPV: {best_for_npv[0]} ({best_for_npv[1].get('estimated_npv', 0):,.0f} ₪)"
        )

    executed_tools = extract_executed_tools_from_history(messages)
    if executed_tools:
        context_parts.append("")
        context_parts.append("🔧 **כלים שכבר הופעלו בשיחה זו:**")
        tool_names_hebrew = {
            "RUN_RETIREMENT_SCENARIOS": "הרצת תרחישי פרישה",
            "EXECUTE_RETIREMENT_SCENARIO": "החלת תרחיש",
            "CHECK_DATA_COMPLETENESS": "בדיקת שלמות נתונים",
            "GET_TAX_PROJECTION": "הערכת מס",
            "SELECT_TARGET_PENSION_SCENARIO": "בחירת תרחיש ליעד",
            "BUILD_TARGET_PENSION_PLAN": "בניית תכנית קצבה",
            "FIND_OPTIMAL_SCENARIO": "מציאת תרחיש אופטימלי",
        }
        for tool in executed_tools:
            hebrew_name = tool_names_hebrew.get(tool, tool)
            context_parts.append(f"  • {hebrew_name}")
        context_parts.append("**אל תפעיל כלים אלה שוב אלא אם הלקוח מבקש במפורש!**")

    if effective_portfolio and len(effective_portfolio) > 0:
        portfolio_context = build_pension_portfolio_context(
            effective_portfolio,
            user_message=last_user_text,
            snapshot_at=effective_snapshot_at,
        )
        context_parts.extend(portfolio_context)
        logger.info(
            "Added pension portfolio context with %d accounts",
            len(effective_portfolio),
        )

    user_messages = [m for m in messages if m.role == "user"]
    if user_messages and request.client_id is not None:
        last_user_msg = user_messages[-1].content

        agent_state = get_agent_state_json(client_id=request.client_id, db=db)

        context_parts.append("")
        context_parts.append("🏗️ **סטטוס מערכת (State):**")
        context_parts.append(f"```json\n{agent_state}\n```")

        intent_tool = ""
        computed_data = None

        history = []
        logger.info("Prepared agent state for context")

    context_parts.append("")
    context_parts.append(
        "**הנחיה לסוכן:** הנתונים למעלה הם נתוני מערכת/מסלקה. תוצאות מחושבות מופיעות רק אם קיימת הודעת system מסוג Tool Result. "
        "אם אין Tool Result רלוונטי — אסור לטעון שבוצע חישוב או שיש 'מקדמים אמיתיים'."
    )

    return context_parts


def build_full_context_for_llm(
    *,
    request: ChatRequest,
    db: Session,
    messages: list[ChatMessage],
) -> Optional[str]:
    parts = build_llm_context_parts(request=request, db=db, messages=messages)
    if not parts:
        return None
    return "\n".join(parts)
