from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import json
from datetime import date

from app.database import get_db, SessionLocal  # Added SessionLocal
from app.models import (
    Client,
    Scenario,
    FixationResult,
    CurrentEmployer,
    PensionFund,
    CapitalAsset,
    AdditionalIncome,
    Commutation,
)
from app.schemas.llm_chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    LlmProviderUpdateRequest,
    LlmProviderUpdateResponse,
    ComputedPensionData,
    PensionPortfolioAccount,
)
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.documents.data_fetchers.client_data import fetch_client_data
from app.services.tax_data import TaxBracketsService
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.retirement_age_service import calculate_retirement_age
from app.utils.llm_chat_log import generate_request_id, log_llm_event
from app.utils.playbook_loader import get_relevant_example, get_condensed_workflow_example, format_example_as_few_shot

logger = logging.getLogger("app.llm_chat")


MAX_NON_SYSTEM_MESSAGES = 12

router = APIRouter(prefix="/api/v1/llm", tags=["llm-agent"])


def _is_net_pension_request(user_message: str) -> bool:
    """
    בודק אם המשתמש ביקש קצבה נטו (אחרי מס).
    מחפש מילות מפתח: נטו, ביד, אחרי מס, נקי.
    """
    net_keywords = ["נטו", "ביד", "אחרי מס", "נקי", "net"]
    message_lower = user_message.lower()
    return any(keyword in message_lower for keyword in net_keywords)


def _is_max_exemption_request(user_message: str) -> bool:
    """בודק אם המשתמש מבקש במפורש פטור מקסימלי/מיצוי פטור בקצבה."""
    if not user_message:
        return False
    keywords = [
        "פטור מקסימלי",
        "מיצוי הפטור המקסימלי",
        "מיצוי פטור מלא",
        "פטור מלא על הקצבה",
        "פטור מלא לקצבה",
        "קיבוע זכויות",
        "max exemption",
        "maximum exemption",
    ]
    lowered = user_message.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _extract_achieved_pension_from_result(tool_result: str) -> float | None:
    """
    מחלץ את ערך הקצבה שהושגה (Achieved) מתוצאת BUILD_TARGET_PENSION_PLAN.
    """
    import re
    # מחפש תבנית כמו "Achieved: 25,000" או "Achieved: 25000"
    match = re.search(r"Achieved:\s*([\d,]+)", tool_result)
    if match:
        value_str = match.group(1).replace(",", "")
        try:
            return float(value_str)
        except ValueError:
            return None
    return None


def _extract_gross_income_for_tax(tool_name: str, tool_result: str) -> float | None:
    """מחלץ סכום ברוטו חודשי רלוונטי למס מתוצאת כלי.

    עבור BUILD_TARGET_PENSION_PLAN – משתמש בקצבה שהושגה (Achieved).
    עבור RUN_RETIREMENT_CASHFLOW_ANALYSIS – משתמש בהכנסה המובטחת החודשית הכוללת (total_guaranteed_income).
    """

    # BUILD_TARGET_PENSION_PLAN מחזיר טקסט חופשי, נשתמש ברגקס הקיים
    if tool_name == "BUILD_TARGET_PENSION_PLAN":
        return _extract_achieved_pension_from_result(tool_result)

    # RUN_RETIREMENT_CASHFLOW_ANALYSIS מחזיר JSON (result בלבד)
    if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        try:
            data = json.loads(tool_result)
            value = data.get("total_guaranteed_income")
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    return None


def _extract_executed_tools_from_history(messages: list[ChatMessage]) -> set[str]:
    """
    מזהה כלים שכבר הופעלו בשיחה הנוכחית לפי הודעות קודמות.
    מחזיר set של מחרוזות בפורמט "TOOL_NAME:param_value" למניעת כפילויות.
    """
    executed = set()
    tool_indicators = {
        "✅ המערכת יצרה תרחישי פרישה": "RUN_RETIREMENT_SCENARIOS",
        "✅ התרחיש הוחל בהצלחה": "EXECUTE_RETIREMENT_SCENARIO",
        "📋 **בדיקת שלמות נתונים**": "CHECK_DATA_COMPLETENESS",
        "💵 **הערכת מס בפרישה**": "GET_TAX_PROJECTION",
        "✅ **נמצא תרחיש שמגיע ליעד": "SELECT_TARGET_PENSION_SCENARIO",
        "✅ **התכנית הושלמה בהצלחה**": "BUILD_TARGET_PENSION_PLAN",
        "ניתוח רגישות": "FIND_OPTIMAL_SCENARIO",
    }
    
    for msg in messages:
        if msg.role == "assistant":
            for indicator, tool_name in tool_indicators.items():
                if indicator in msg.content:
                    executed.add(tool_name)
    
    return executed


def _find_last_user_message(messages: list[ChatMessage]) -> str:
    """מוצא את תוכן ההודעה האחרונה שהיא מסוג user."""
    if not messages:
        return ""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


def _extract_target_pension_from_message(message: str) -> float:
    """
    מחלץ יעד קצבה מהודעת המשתמש.
    מחפש תבניות כמו: 23K, 23000, 23,000, 23 אלף וכו'.
    """
    import re
    
    # נרמול - הסר תווים מיוחדים
    normalized = message.replace(",", "").replace("₪", "").replace("ש\"ח", "")
    
    # חיפוש תבניות שונות
    patterns = [
        # 23K או 23k לחודש/נטו
        r'(\d+)\s*[kK]\s*(?:נטו|לחודש|חודשי|בחודש)?',
        # 23000 או 23,000 לחודש/נטו
        r'(\d{4,6})\s*(?:נטו|לחודש|חודשי|בחודש)',
        # קצבה של/בגובה 23000
        r'קצבה\s*(?:של|בגובה|בסך)\s*(\d+)',
        # יעד של 23000
        r'יעד\s*(?:של|בגובה|בסך)?\s*(\d+)',
        # זקוק ל-23000
        r'זקוק\s*ל[־-]?\s*(\d+)',
        # 23 אלף
        r'(\d+)\s*אלף',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            # אם זה K או אלף, הכפל ב-1000
            if 'k' in pattern.lower() or 'אלף' in pattern:
                value *= 1000
            # אם המספר קטן מ-100, כנראה זה אלפים
            if value < 100:
                value *= 1000
            # וידוא שהערך סביר (1,000 - 100,000)
            if 1000 <= value <= 100000:
                return value
    
    # ברירת מחדל - 70% משכר ממוצע במשק
    return 15000.0


def _get_agent_state(client_id: int, db: Session) -> str:
    """
    בונה אובייקט מצב (State) המייצג את הסטטוס הנוכחי של התיק.
    """
    # בדיקת נתוני מסלקה/תיק
    pension_count = db.query(PensionFund).filter(PensionFund.client_id == client_id).count()
    capital_count = db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).count()
    # has_portfolio = (pension_count + capital_count) > 0
    
    # --- עקיפה זמנית לבדיקות ---
    has_portfolio = True
    # ---------------------------

    # בדיקת תרחישים
    scenarios_count = db.query(Scenario).filter(Scenario.client_id == client_id).count()
    
    # בדיקת תכנית מחושבת (אם קיימת בזיכרון האחרון - כרגע נבדוק רק אם יש תרחישים)
    # בעתיד נרצה לשמור ב-DB דגל אם חושבה תכנית משיכה ספציפית
    
    state = {
        "maslaka_loaded": has_portfolio,
        "pension_plan_calculated": scenarios_count > 0,
        "rights_fixation_done": False, # כרגע אין אינדיקציה ברורה ב-DB, נניח False
        "current_target_pension": None, # יתעדכן בשיחה
        "products_count": pension_count + capital_count
    }
    return json.dumps(state, indent=2)


def _get_tools_definitions() -> str:
    """
    מחזיר את הגדרות הכלים (Tools) בפורמט JSON Schema.
    """
    tools = [
        {
            "name": "BUILD_TARGET_PENSION_PLAN",
            "description": "כלי לתכנון מתווה משיכה אופטימלי מכל המקורות להשגת יעד קצבה חודשי נטו.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_monthly_pension": {
                        "type": "integer",
                        "description": "יעד הקצבה החודשי המבוקש בשקלים (למשל: 20000)"
                    }
                },
                "required": ["target_monthly_pension"]
            }
        },
        {
            "name": "GET_TAX_PROJECTION",
            "description": "כלי לחישוב הערכת מס מפורטת על קצבה חודשית ברוטו.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gross_monthly_pension": {
                        "type": "integer",
                        "description": "סכום הקצבה החודשית ברוטו עליה יש לחשב מס"
                    }
                },
                "required": ["gross_monthly_pension"]
            }
        },
        {
            "name": "GET_PENSION_PRODUCTS",
            "description": "Retrieves a detailed list of all pension products and capital assets in the client's portfolio, including balances and types.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "CALCULATE_TAX_EXEMPT_PENSION",
            "description": "Calculates the tax-exempt monthly pension benefit (קיבוע זכויות), including a simulation of how the client's current severance pay exemption impacts the final exempt pension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_tax_exempt_grant_amount": {
                        "type": "integer",
                        "description": "The amount of tax-exempt grant (severance) the client considers taking now."
                    }
                },
                "required": ["current_tax_exempt_grant_amount"]
            }
        },
        {
            "name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            "description": "כלי מרכזי לניתוח תזרים פרישה. מחשב קצבה ברוטו, מס הכנסה, קצבה נטו, ופטור מקיבוע זכויות. השתמש בכלי זה כאשר הלקוח שואל 'כמה אקבל נטו', 'אחרי מס', 'פטור מקסימלי' או 'קיבוע זכויות'. דוגמה: ###TOOL_CALL### {\"name\": \"RUN_RETIREMENT_CASHFLOW_ANALYSIS\", \"arguments\": {\"retirement_date\": \"2028-01-01\", \"apply_max_exemption\": true}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "retirement_date": {
                        "type": "string",
                        "description": "תאריך פרישה בפורמט YYYY-MM-DD. אם הלקוח נתן רק שנה (למשל 2028), השתמש ב-01-01 של אותה שנה."
                    },
                    "desired_monthly_income": {
                        "type": "integer",
                        "description": "יעד הכנסה חודשית נטו בשקלים (אופציונלי, ברירת מחדל: 70% מהשכר)."
                    },
                    "apply_max_exemption": {
                        "type": "boolean",
                        "description": "הפעל פטור מקסימלי מקיבוע זכויות. חובה להפעיל (true) כאשר הלקוח מבקש 'פטור מקסימלי' או 'קיבוע זכויות'."
                    }
                },
                "required": ["retirement_date"]
            }
        },
        {
            "name": "CALCULATE_PENSION_COMMUTATION",
            "description": "כלי לחישוב היוון קצבה - המרת חלק מהקצבה החודשית לסכום חד-פעמי (Lump Sum). השתמש בכלי זה כאשר הלקוח שואל 'כמה כסף אקבל אם אוותר על X שקל מהקצבה', 'היוון קצבה', 'לקבל סכום חד-פעמי במקום קצבה'. דוגמה: ###TOOL_CALL### {\"name\": \"CALCULATE_PENSION_COMMUTATION\", \"arguments\": {\"target_monthly_pension_reduction\": 2000, \"retirement_date\": \"2028-01-01\"}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_monthly_pension_reduction": {
                        "type": "number",
                        "description": "הסכום החודשי שהלקוח מוכן להפחית מהקצבה העתידית (ברוטו) בתמורה לסכום חד-פעמי."
                    },
                    "retirement_date": {
                        "type": "string",
                        "description": "תאריך פרישה בפורמט YYYY-MM-DD."
                    }
                },
                "required": ["target_monthly_pension_reduction", "retirement_date"]
            }
        },
        {
            "name": "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
            "description": "כלי לחישוב מס על משיכת כספי הון (קופת גמל, קרן השתלמות, תגמולים נזילים). השתמש בכלי זה כאשר הלקוח שואל 'כמה מס אשלם אם אמשוך X שקל מהקופה', 'משיכה מקופת גמל', 'משיכה מקרן השתלמות', 'כמה נשאר לי נטו אחרי משיכה'. דוגמה: ###TOOL_CALL### {\"name\": \"CALCULATE_CAPITAL_WITHDRAWAL_TAX\", \"arguments\": {\"withdrawal_amount_gross\": 100000, \"withdrawal_year\": 2025}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "withdrawal_amount_gross": {
                        "type": "number",
                        "description": "סכום המשיכה ברוטו מכספי ההון."
                    },
                    "withdrawal_year": {
                        "type": "integer",
                        "description": "שנת המשיכה המתוכננת (לקביעת מדרגות המס). ברירת מחדל: 2025."
                    }
                },
                "required": ["withdrawal_amount_gross"]
            }
        }
    ]
    return json.dumps(tools, indent=2, ensure_ascii=False)


# --- פונקציה ישנה שהופסקה ---
# def _detect_intent_and_auto_run(...) -> ... 
# (הלוגיקה בוטלה לבקשת המשתמש כדי לאפשר לסוכן להחליט)


def _build_pension_portfolio_context(
    portfolio: list[PensionPortfolioAccount],
) -> list[str]:
    """
    ממפה את נתוני התיק הפנסיוני מה-UI לפורמט קריא לסוכן.
    מציג רק נתונים גולמיים - הסוכן חייב להריץ חישובים לקבלת קצבה.
    """
    if not portfolio:
        return []
    
    context_lines: list[str] = []
    context_lines.append("")
    context_lines.append("📂 **תיק פנסיוני (נתונים גולמיים מקובץ מסלקה)**")
    context_lines.append("⚠️ **חובה:** להפעיל BUILD_TARGET_PENSION_PLAN לקבלת קצבה מחושבת עם מקדמים אמיתיים!")
    context_lines.append("")
    
    total_balance = 0.0
    total_severance = 0.0
    total_tagmulim = 0.0
    products_list: list[dict] = []
    
    for acc in portfolio:
        balance = float(acc.יתרה or 0)
        if balance <= 0:
            continue
        
        total_balance += balance
        
        # חישוב פיצויים
        severance_current = float(acc.פיצויים_מעסיק_נוכחי or 0)
        severance_past = float(acc.פיצויים_ממעסיקים_קודמים_רצף_קצבה or 0)
        total_severance += severance_current + severance_past
        
        # חישוב תגמולים
        tagmulim = float(acc.תגמולים or acc.סך_תגמולים or 0)
        total_tagmulim += tagmulim
        
        # זיהוי סוג מוצר
        product_type = acc.סוג_מוצר or "לא ידוע"
        product_lower = product_type.lower()
        
        # קביעת האם המוצר הוא הוני או קצבתי
        is_capital_only = False
        if "השתלמות" in product_lower:
            is_capital_only = True
            category = "הון בלבד"
        elif "גמל להשקעה" in product_lower:
            is_capital_only = True
            category = "הון (ניתן להמרה)"
        elif "קרן פנסיה" in product_lower or "פנסיה" in product_lower:
            category = "קצבתי"
        elif "ביטוח מנהלים" in product_lower or "ביטוח" in product_lower:
            category = "קצבתי"
        elif "קופת גמל" in product_lower:
            category = "קצבתי/הוני"
        elif "חיסכון" in product_lower:
            category = "הוני"
        else:
            category = "לחישוב"
        
        products_list.append({
            "name": acc.שם_תכנית or "ללא שם",
            "company": acc.חברה_מנהלת or "",
            "type": product_type,
            "category": category,
            "balance": balance,
            "severance": severance_current + severance_past,
            "tagmulim": tagmulim,
            "is_capital_only": is_capital_only,
        })
    
    # יצירת טבלה עם נתונים גולמיים בלבד - ללא קצבה משוערת!
    context_lines.append("| מוצר | סוג | סיווג | יתרה (₪) |")
    context_lines.append("|------|------|-------|----------|")
    
    for p in products_list:
        context_lines.append(
            f"| {p['name'][:30]} | {p['type'][:20]} | {p['category']} | {p['balance']:,.0f} |"
        )
    
    context_lines.append("")
    context_lines.append(f"**סיכום נתונים גולמיים:**")
    context_lines.append(f"  • סה\"כ יתרות: {total_balance:,.0f} ₪")
    if total_severance > 0:
        context_lines.append(f"  • מתוכם פיצויים: {total_severance:,.0f} ₪")
    if total_tagmulim > 0:
        context_lines.append(f"  • מתוכם תגמולים: {total_tagmulim:,.0f} ₪")
    
    total_capital_only = sum(p['balance'] for p in products_list if p['is_capital_only'])
    if total_capital_only > 0:
        context_lines.append(f"  • הון שלא ניתן להמרה: {total_capital_only:,.0f} ₪")
    
    context_lines.append("")
    context_lines.append("🔧 **לקבלת קצבה מחושבת:** הפעל BUILD_TARGET_PENSION_PLAN עם יעד קצבה (למשל 20000)")
    context_lines.append("   הכלי יחזיר מקדמים אמיתיים לפי גיל, מין וסוג מוצר.")
    
    return context_lines


def _prepare_messages_with_context(
    request: ChatRequest, db: Session
) -> tuple[list[ChatMessage], ComputedPensionData | None]:
    """מכין את ההודעות עם הקשר לקוח, מקורות קצבה ותרחישים.
    
    Returns:
        tuple of (messages, computed_data) where computed_data contains
        pension calculations for direct frontend display.
    """
    messages = list(request.messages)
    computed_pension_data: ComputedPensionData | None = None

    # הנחיית בסיס גלובלית לסוכן (אישיות, שימוש בכלים, פורמט תשובה)
    global_system_prompt = (
        "אתה יועץ פרישה פנסיוני דיגיטלי. אתה מדבר תמיד בעברית פשוטה ומסביר ללקוח קצה את מצב הפרישה שלו. "
        "המערכת מחשבת ומציגה מס הכנסה בלבד על קצבאות והכנסות רלוונטיות – אין לכלול או להסביר ללקוח ביטוח לאומי, מס בריאות או כל ניכוי אחר שאינו מס הכנסה ישיר. "
        "אל תחזיר לעולם JSON גולמי או מבני נתונים טכניים – תמיד סכם אותם לטקסט קריא.\n\n"
        "כאשר בשאלה נדרשים מספרים (לדוגמה קצבה נטו, אחרי מס, או השוואת שנות פרישה) עליך להסתמך רק על נתונים מהמערכת: "
        "או מתוצאות הכלים שנמצאות בהודעות system (Tool Result …) או באמצעות הרצת כלים דרך ###TOOL_CALL###. "
        "אסור להמציא מספרים שלא הופקו מהמערכת.\n\n"
        "כאשר יש לך נתונים מ‑RUN_RETIREMENT_CASHFLOW_ANALYSIS ו/או GET_TAX_PROJECTION, עליך לבנות תשובה אחת מאוחדת שמציגה: "
        "קצבה ברוטו, מס הכנסה, קצבה נטו, וכל פטור מקיבוע זכויות (אחוז הפטור וסכום הקצבה הפטורה). "
        "אם תוצאות הכלים כוללות שדות של ביטוח לאומי, מס בריאות או 'סך כל המס' – עליך להתעלם מהם לחלוטין, לא להשתמש בהם בחישוב שאתה מסביר, ולא להציג אותם ללקוח. "
        "אם הופעל פטור מקסימלי (apply_max_exemption או נתוני פטור אחרים), הדגש במפורש את השפעתו על מס ההכנסה ועל הנטו.\n\n"
        "כאשר אתה מסביר כמה זמן ההון הנזיל יספיק לכיסוי הגירעון החודשי, תמיד הצג במפורש את החישוב החודשי (לדוגמה: הון נזיל ÷ גירעון חודשי = מספר חודשים), "
        "לאחר מכן המר את מספר החודשים לשנים (עם עיגול סביר), והסבר את שתי התוצאות במילים פשוטות ללקוח.\n\n"
        "כלל קונטקסט קריטי: כאשר לקוח מגיב לניתוח שביצעת (לדוגמה שאלה על פער, קיימות הון או בקשת תרחישים), עליך להישאר צמוד לנתוני הניתוח האחרון "
        "ולפרמטרים העיקריים שלו (גיל פרישה, תאריך פרישה, קצבה מובטחת). אסור לשנות את גיל הפרישה או רמת הקצבה רק כדי 'להעלים' את הפער, אלא אם הלקוח ביקש במפורש "
        "לבחון גיל פרישה אחר או רמת קצבה אחרת. כאשר אתה מציע דרכים לסגירת פער, התמקד בשינויים ביעד ההכנסה החודשית, בשימוש או מכירת נכסים הוניים אחרים, או באופטימיזציה של מיסוי, "
        "תוך הישארות צמוד לנתונים שהופקו מהכלים בניתוח האחרון.\n\n"
        "בעת הצגת מס, התייחס תמיד רק למס הכנסה. מבחינתך 'מס' הוא מס ההכנסה על הקצבה בלבד. גם אם הלקוח שואל במפורש על ביטוח לאומי או מס בריאות, "
        "הסבר שהמערכת הנוכחית ממוקדת במס הכנסה בלבד, ולכן אינה מחשבת או מציגה בנפרד את רכיבי ביטוח לאומי ומס בריאות.\n\n"
        "לעולם אל תענה ללקוח שעליך 'להריץ חישוב' – החישובים מבוצעים על‑ידי הכלים. תפקידך הוא לפרש את התוצאות ולהסביר אותן בפשטות.\n\n"
        "תסריטי פעולה (Playbooks) עיקריים:\n"
        "1. חישוב קצבה נטו לתאריך פרישה – הרץ RUN_RETIREMENT_CASHFLOW_ANALYSIS (עם apply_max_exemption=True אם הלקוח מבקש פטור מקסימלי).\n"
        "2. השוואת תאריכי פרישה – הרץ RUN_RETIREMENT_CASHFLOW_ANALYSIS פעמיים (לכל תאריך) והשווה ברוטו, מס הכנסה ונטו.\n"
        "3. שאלות הסבר (מה זה קיבוע זכויות? וכו') – ענה מהידע התיאורטי ללא הפעלת כלים, והצע סימולציה אישית אם הלקוח רוצה.\n"
        "4. היוון קצבה – הרץ CALCULATE_PENSION_COMMUTATION כאשר הלקוח שואל על המרת קצבה לסכום חד-פעמי.\n"
        "5. משיכת כספי הון – הרץ CALCULATE_CAPITAL_WITHDRAWAL_TAX כאשר הלקוח שואל על משיכה מקופת גמל/קרן השתלמות.\n"
        "6. דו\"ח סיכום מובנה – כאשר הלקוח מבקש 'סכם את הנתונים', 'הפק דו\"ח', 'מה המסקנה הסופית?' או 'תן לי סיכום', הצג את התשובה בפורמט דו\"ח מובנה עם כותרת, מסקנות, טבלת תוצאות והמלצות."
    )
    
    # הוספת דוגמת Workflow קומפקטית לכל שיחה
    workflow_example = get_condensed_workflow_example()
    global_system_prompt += workflow_example

    messages.insert(0, ChatMessage(role="system", content=global_system_prompt))
    
    # הזרקת דוגמה רלוונטית לפי סוג השאלה (אם זוהי שאלה מורכבת)
    last_user_msg = _find_last_user_message(request.messages)
    if last_user_msg:
        relevant_example = get_relevant_example(last_user_msg)
        if relevant_example:
            example_msg = format_example_as_few_shot(relevant_example)
            messages.insert(1, ChatMessage(role="system", content=example_msg))

    if request.client_id is not None:
        client = fetch_client_data(db, request.client_id)
        if client is not None:
            age = client.get_age() if hasattr(client, "get_age") else None

            # === חלק 1: נתוני לקוח בסיסיים ===
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

            # === חלק 2: מקורות קצבה - קרנות פנסיה ונכסי הון ===
            pension_funds = db.query(PensionFund).filter(
                PensionFund.client_id == request.client_id
            ).all()
            
            capital_assets = db.query(CapitalAsset).filter(
                CapitalAsset.client_id == request.client_id
            ).all()

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

            # === חלק 3: תרחישי פרישה ===
            scenarios_summary_parts: list[str] = []
            retirement_age_for_summary: int | None = None
            best_pension: float = 0.0
            best_capital: float = 0.0
            best_npv: float = 0.0

            scenarios = (
                db.query(Scenario)
                .filter(Scenario.client_id == request.client_id)
                .order_by(Scenario.created_at.desc())
                .limit(10)
                .all()
            )

            organized: dict[str, dict] = {}
            for scenario in scenarios:
                try:
                    params = json.loads(scenario.parameters) if scenario.parameters else {}
                    scenario_type = params.get("scenario_type", "unknown")
                    age_param = params.get("retirement_age")
                    if retirement_age_for_summary is None and isinstance(age_param, int):
                        retirement_age_for_summary = age_param

                    if scenario.summary_results:
                        summary_data = json.loads(scenario.summary_results)
                        summary_data["scenario_id"] = scenario.id
                        organized[scenario_type] = summary_data
                        
                        pension_val = summary_data.get("total_pension_monthly", 0) or 0
                        capital_val = summary_data.get("total_capital", 0) or 0
                        npv_val = summary_data.get("estimated_npv", 0) or 0
                        
                        if pension_val > best_pension:
                            best_pension = pension_val
                        if capital_val > best_capital:
                            best_capital = capital_val
                        if npv_val > best_npv:
                            best_npv = npv_val
                except Exception:
                    continue

            if organized:
                for key, s in organized.items():
                    name = s.get("scenario_name") or key
                    total_pension = s.get("total_pension_monthly", 0) or 0
                    total_capital = s.get("total_capital", 0) or 0
                    estimated_npv = s.get("estimated_npv", 0) or 0
                    scenario_id = s.get("scenario_id")
                    
                    # הוספת תיאור קצר של היתרון העיקרי
                    advantage = ""
                    if "max_pension" in key or "קצבה" in name:
                        advantage = " [ממקסם קצבה]"
                    elif "max_capital" in key or "הון" in name:
                        advantage = " [ממקסם הון]"
                    elif "max_npv" in key or "NPV" in name:
                        advantage = " [ממקסם ערך נוכחי]"
                    
                    scenarios_summary_parts.append(
                        f"• {name}{advantage}: קצבה {total_pension:,.0f} ₪/חודש, "
                        f"הון {total_capital:,.0f} ₪, NPV {estimated_npv:,.0f} ₪ (מזהה: {scenario_id})"
                    )

            # === חלק 4: קיבוע זכויות ===
            fixation_info: dict = {}
            latest_fixation = (
                db.query(FixationResult)
                .filter(FixationResult.client_id == request.client_id)
                .order_by(FixationResult.created_at.desc())
                .first()
            )
            if latest_fixation and latest_fixation.raw_result:
                try:
                    fixation_data = latest_fixation.raw_result if isinstance(latest_fixation.raw_result, dict) else json.loads(latest_fixation.raw_result)
                    fixation_info = {
                        "exempt_capital_remaining": latest_fixation.exempt_capital_remaining or 0,
                        "used_commutation": latest_fixation.used_commutation or 0,
                        "exempt_pension_percentage": fixation_data.get("exemption_summary", {}).get("exempt_pension_percentage", 0),
                    }
                except Exception:
                    pass

            # === חלק 5: מעסיקים נוכחיים ===
            current_employers = db.query(CurrentEmployer).filter(
                CurrentEmployer.client_id == request.client_id
            ).all()
            
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

            # === חלק 6: היוונים ===
            commutations = db.query(Commutation).join(
                PensionFund, Commutation.pension_id == PensionFund.id
            ).filter(
                PensionFund.client_id == request.client_id
            ).all()
            
            total_commutation: float = 0.0
            commutation_info: list[str] = []
            for comm in commutations:
                amount = float(comm.commutation_amount or 0)
                total_commutation += amount
                if amount > 0:
                    commutation_info.append(
                        f"• היוון {amount:,.0f} ₪ (פגיעה בפטור: {comm.impact_on_exemption or 0:,.0f} ₪)"
                    )

            # === חלק 7: הכנסות נוספות ===
            additional_incomes = db.query(AdditionalIncome).filter(
                AdditionalIncome.client_id == request.client_id
            ).all()
            
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

            # === בניית הודעת הקשר מלאה ===
            context_parts: list[str] = []
            
            # פרטי לקוח
            if client_parts:
                context_parts.append("📋 **פרטי הלקוח**")
                context_parts.append(" | ".join(client_parts))
            
            # סיכום פיננסי מורחב
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
            
            # קיבוע זכויות
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
            
            # מעסיקים
            if employers_info:
                context_parts.append("")
                context_parts.append("🏢 **מעסיקים**")
                for emp_line in employers_info[:3]:
                    context_parts.append(emp_line)
                if len(employers_info) > 3:
                    context_parts.append(f"  (ועוד {len(employers_info) - 3} מעסיקים)")
            
            # היוונים
            if commutation_info:
                context_parts.append("")
                context_parts.append("💸 **היוונים**")
                context_parts.append(f"סה\"כ היוונים: {total_commutation:,.0f} ₪")
            
            # הכנסות נוספות
            if additional_income_info:
                context_parts.append("")
                context_parts.append("💵 **הכנסות נוספות**")
                for inc_line in additional_income_info[:3]:
                    context_parts.append(inc_line)
            
            # מקורות קצבה מפורטים
            if pension_sources_list:
                context_parts.append("")
                context_parts.append("📊 **מקורות קצבה עיקריים**")
                for source in pension_sources_list[:5]:
                    context_parts.append(source)
                if len(pension_sources_list) > 5:
                    context_parts.append(f"  (ועוד {len(pension_sources_list) - 5} מקורות נוספים)")
            
            # תרחישי פרישה
            if scenarios_summary_parts:
                age_text = f" לגיל {retirement_age_for_summary}" if retirement_age_for_summary else ""
                context_parts.append("")
                context_parts.append(f"🎯 **תרחישי פרישה{age_text}**")
                for scenario_line in scenarios_summary_parts:
                    context_parts.append(scenario_line)
                
                # סיכום מהיר
                context_parts.append("")
                context_parts.append("📈 **סיכום תרחישים**")
                context_parts.append(
                    f"קצבה מקסימלית אפשרית: {best_pension:,.0f} ₪/חודש | "
                    f"הון מקסימלי: {best_capital:,.0f} ₪ | "
                    f"NPV מקסימלי: {best_npv:,.0f} ₪"
                )
            
            # ניתוח פערים אוטומטי
            if best_pension > 0 or total_existing_pension > 0:
                context_parts.append("")
                context_parts.append("🔍 **ניתוח מצב**")
                current_pension = total_existing_pension + best_pension
                # הערכת יעד סביר (70% מהשכר)
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
            
            # === חלק 8: גיל פרישה חוקי ומס ===
            try:
                if client.birth_date and client.gender:
                    retirement_info = calculate_retirement_age(client.birth_date, client.gender)
                    legal_retirement_age = retirement_info.get("retirement_age_years", 67)
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
            
            # מידע על מס
            try:
                current_year = date.today().year
                tax_brackets = TaxBracketsService.get_tax_brackets(current_year)
                if tax_brackets:
                    context_parts.append("")
                    context_parts.append("💵 **מדרגות מס (שנתי)**")
                    # הצג רק 3 מדרגות ראשונות
                    for bracket in tax_brackets[:3]:
                        rate_pct = int(bracket["rate"] * 100)
                        context_parts.append(
                            f"  • עד {bracket['max_income']:,} ₪: {rate_pct}%"
                        )
                    context_parts.append(f"  • (ועוד {len(tax_brackets) - 3} מדרגות גבוהות יותר)")
            except Exception:
                pass
            
            # === חלק 9: השוואת תרחישים עם ניקוד ===
            if len(organized) >= 2:
                context_parts.append("")
                context_parts.append("⚖️ **השוואת תרחישים**")
                
                # מצא את התרחיש הטוב ביותר לכל קריטריון
                best_for_pension = max(organized.items(), key=lambda x: x[1].get("total_pension_monthly", 0))
                best_for_capital = max(organized.items(), key=lambda x: x[1].get("total_capital", 0))
                best_for_npv = max(organized.items(), key=lambda x: x[1].get("estimated_npv", 0))
                
                context_parts.append(f"  • הכי טוב לקצבה: {best_for_pension[0]} ({best_for_pension[1].get('total_pension_monthly', 0):,.0f} ₪/חודש)")
                context_parts.append(f"  • הכי טוב להון: {best_for_capital[0]} ({best_for_capital[1].get('total_capital', 0):,.0f} ₪)")
                context_parts.append(f"  • הכי טוב ל-NPV: {best_for_npv[0]} ({best_for_npv[1].get('estimated_npv', 0):,.0f} ₪)")
            
            # === חלק 10: זיהוי כלים שכבר הופעלו בשיחה ===
            executed_tools = _extract_executed_tools_from_history(messages)
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
            
            # === חלק 11: תיק פנסיוני מה-UI (אם נשלח) ===
            if request.pension_portfolio and len(request.pension_portfolio) > 0:
                portfolio_context = _build_pension_portfolio_context(request.pension_portfolio)
                context_parts.extend(portfolio_context)
                logger.info("Added pension portfolio context with %d accounts", len(request.pension_portfolio))
            
            # === חלק 12: הרצת כלים אוטומטית לפי כוונת המשתמש ===
            # מזהה את ההודעה האחרונה של המשתמש ומריץ כלים מתאימים
            user_messages = [m for m in messages if m.role == "user"]
            if user_messages and request.client_id is not None:
                last_user_msg = user_messages[-1].content
                # --- לוגיקה ישנה מבוטלת: הרצת כלים אוטומטית לפי מילות מפתח ---
                # intent_tool, intent_context, computed_data = _detect_intent_and_auto_run(
                #     user_message=user_message,
                #     client_id=client_id,
                #     db=db,
                #     executed_tools=executed_tools
                # )
                # if intent_tool:
                #     executed_tools.add(intent_tool)
                #     system_context_lines.extend(intent_context)
                # -------------------------------------------------------------
                
                # הוספת State ו-Tools לקונטקסט
                agent_state = _get_agent_state(request.client_id, db)
                tools_schema = _get_tools_definitions()
                
                context_parts.append("")
                context_parts.append("🏗️ **סטטוס מערכת (State):**")
                context_parts.append(f"```json\n{agent_state}\n```")
                context_parts.append("")
                context_parts.append("🛠️ **כלים זמינים (Tools):**")
                context_parts.append(f"```json\n{tools_schema}\n```")
                context_parts.append("")
                context_parts.append("⚡ **הנחיה לפעולה:**")
                context_parts.append("אם חסר לך מידע או נדרש חישוב, אל תענה מיד. במקום זאת, הוצא פקודה להרצת כלי בפורמט הבא:")
                context_parts.append('###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {"arg": "value"}}')
                context_parts.append("")
                
                intent_tool = ""
                computed_data = None  # כרגע אין נתונים מחושבים אוטומטית, הסוכן צריך לבקש
                
                # 3. הכנת היסטוריית ההודעות ל-LLM
                history = []
                logger.info("Prepared agent state and tools schema for context")
            
            context_parts.append("")
            context_parts.append("**הנחיה לסוכן:** הנתונים למעלה כוללים חישובים אוטומטיים עם מקדמים אמיתיים. השתמש בהם ישירות בתשובתך! אל תגיד 'צריך להריץ חישוב' - החישוב כבר בוצע.")
            
            if context_parts:
                full_context = "\n".join(context_parts)
                
                # שילוב הקונטקסט ישירות בהודעת המשתמש האחרונה
                # כך ה-LLM יראה את הנתונים בצורה ברורה יותר (במיוחד Ollama)
                user_messages_in_list = [i for i, m in enumerate(messages) if m.role == "user"]
                if user_messages_in_list:
                    last_user_idx = user_messages_in_list[-1]
                    original_content = messages[last_user_idx].content
                    enhanced_content = f"""להלן נתוני הלקוח האמיתיים מהמערכת (חובה להשתמש בהם!):

{full_context}

---
שאלת המשתמש: {original_content}

**חשוב:** ענה רק על בסיס הנתונים האמיתיים למעלה. אל תמציא נתונים!"""
                    messages[last_user_idx] = ChatMessage(role="user", content=enhanced_content)
                    logger.debug("Enhanced user message with context for client %s: %d chars", request.client_id, len(enhanced_content))
                else:
                    # Fallback - שלח כהודעת system אם אין הודעות משתמש
                    context_msg = ChatMessage(role="system", content=full_context)
                    messages = [context_msg, *messages]
                    logger.debug("Prepared context for client %s: %d chars", request.client_id, len(full_context))

    system_messages = [m for m in messages if m.role == "system"]
    non_system_messages = [m for m in messages if m.role != "system"]
    if len(non_system_messages) > MAX_NON_SYSTEM_MESSAGES:
        non_system_messages = non_system_messages[-MAX_NON_SYSTEM_MESSAGES:]
    final_messages = [*system_messages, *non_system_messages]
    return final_messages, computed_pension_data


@router.get("/status")
async def get_llm_status() -> dict[str, str | None]:
    """מחזיר מידע על ספק ה-LLM והמודל הפעיל לצורך חיווי ב-UI."""
    return pension_llm_service.get_status()


@router.post("/provider", response_model=LlmProviderUpdateResponse)
async def update_llm_provider(payload: LlmProviderUpdateRequest) -> LlmProviderUpdateResponse:
    """מחליף ספק/מודל LLM בזמן ריצה ומחזיר את המצב החדש."""
    status = pension_llm_service.set_provider(payload.provider, payload.model_name)
    return LlmProviderUpdateResponse(**status)



def _execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[List[Any]] = None,
    force_max_exemption: bool = False,
) -> str:
    """
    מבצע את הקריאה בפועל לפונקציה המתאימה ומחזיר את הפלט כטקסט.
    """
    logger.info("⚡ Executing Tool: %s with args: %s", tool_name, args)
    
    # שליפת אובייקט הלקוח כדי להזריקו לשירות (Data Injection)
    # זה מבטיח שהשירות מקבל את אותו הקונטקסט שקיים ב-Router
    client_obj = db.query(Client).filter(Client.id == client_id).first()
    
    # הזרקת נתוני תיק פנסיוני גולמיים אם קיימים (עוקף בעיות DB Session)
    agent_tools = AgentToolsService(
        db, 
        client_id, 
        client_object=client_obj,
        pension_portfolio_data=pension_portfolio
    )

    try:
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            target = args.get("target_monthly_pension")
            if not target:
                return "Error: Missing argument 'target_monthly_pension'"
            
            result = agent_tools.build_target_pension_plan(target_monthly_pension=float(target))
            if not result.get("success"):
                return f"Tool Error: {result.get('error', 'Unknown error')}"
            
            # בניית תשובה טקסטואלית מסכמת
            plan_res = result.get("result", {})
            summary = (
                f"Calculation Complete:\n"
                f"- Target: {plan_res.get('target_monthly_pension'):,.0f}\n"
                f"- Achieved: {plan_res.get('accumulated_pension'):,.0f}\n"
                f"- Remaining Capital: {plan_res.get('remaining_capital'):,.0f}\n"
                f"- Status: {'Success' if plan_res.get('target_achieved') else 'Partial'}\n"
                f"Details: {result.get('explanation')}"
            )
            return summary

        elif tool_name == "GET_TAX_PROJECTION":
            gross = args.get("gross_monthly_pension")
            if not gross:
                return "Error: Missing argument 'gross_monthly_pension'"
            
            result = agent_tools.get_tax_projection(monthly_pension=float(gross))
            return f"Tax Projection Result:\n{result.get('explanation', 'No details available')}"

        elif tool_name == "GET_PENSION_PRODUCTS":
            result = agent_tools.get_pension_products()
            if not result.get("success"):
                return f"Tool Error: {result.get('explanation')}"
            
            # החזרת התוצאה כ-JSON כדי שה-LLM יוכל לפרמט טבלה
            return json.dumps(result.get("result"), ensure_ascii=False)
            
        elif tool_name == "CALCULATE_TAX_EXEMPT_PENSION":
            grant_amount = args.get("current_tax_exempt_grant_amount")
            if grant_amount is None:
                return "Error: Missing argument 'current_tax_exempt_grant_amount'"
            
            result = agent_tools.calculate_tax_exempt_pension(current_tax_exempt_grant_amount=float(grant_amount))
            if not result.get("success"):
                return f"Tool Error: {result.get('explanation')}"
            
            return json.dumps(result.get("result"), ensure_ascii=False)

        elif tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
            date_str = args.get("retirement_date")
            income = args.get("desired_monthly_income")
            apply_max_exemption_arg = args.get("apply_max_exemption", False)

            if not date_str:
                return "Error: Missing argument 'retirement_date'"

            income_val = float(income) if income else None

            # נרמול apply_max_exemption שמגיע מה-LLM (יכול להיות מחרוזת "true"/"false")
            if isinstance(apply_max_exemption_arg, str):
                apply_max_exemption = apply_max_exemption_arg.strip().lower() in {"true", "1", "yes", "y"}
            else:
                apply_max_exemption = bool(apply_max_exemption_arg)

            # אם המשתמש ביקש במפורש "פטור מקסימלי" – נכפה apply_max_exemption=True
            if force_max_exemption:
                apply_max_exemption = True

            result = agent_tools.run_retirement_cashflow_analysis(
                retirement_date=date_str,
                desired_monthly_income=income_val,
                apply_max_exemption=apply_max_exemption,
            )
            
            if not result.get("success"):
                return f"Tool Error: {result.get('explanation')}"
            
            return json.dumps(result.get("result"), ensure_ascii=False)

        elif tool_name == "CALCULATE_PENSION_COMMUTATION":
            reduction = args.get("target_monthly_pension_reduction")
            date_str = args.get("retirement_date")
            
            if reduction is None:
                return "Error: Missing argument 'target_monthly_pension_reduction'"
            if not date_str:
                return "Error: Missing argument 'retirement_date'"
            
            result = agent_tools.calculate_pension_commutation(
                target_monthly_pension_reduction=float(reduction),
                retirement_date=date_str,
            )
            
            if not result.get("success"):
                return f"Tool Error: {result.get('explanation')}"
            
            commutation_result = result.get("result", {})
            
            # === Force Chaining: הפעלת RUN_RETIREMENT_CASHFLOW_ANALYSIS אוטומטית ===
            # מטרה: לספק ללקוח תמונה מלאה - מה הקצבה הנטו המלאה ללא היוון
            try:
                cashflow_result = agent_tools.run_retirement_cashflow_analysis(
                    retirement_date=date_str,
                    desired_monthly_income=None,
                    apply_max_exemption=True,
                )
                
                if cashflow_result.get("success"):
                    cashflow_data = cashflow_result.get("result", {})
                    
                    # הוספת נתוני הקצבה המלאה לתוצאה המשולבת
                    combined_result = {
                        "commutation": commutation_result,
                        "full_pension_comparison": {
                            "total_gross_pension": cashflow_data.get("total_guaranteed_income", 0),
                            "income_tax": cashflow_data.get("income_tax", 0),
                            "net_pension": cashflow_data.get("net_income", 0),
                            "exemption_percentage": cashflow_data.get("exemption_percentage", 0),
                        },
                        "comparison_summary": {
                            "lump_sum_net": commutation_result.get("lump_sum_net", 0),
                            "monthly_pension_lost": commutation_result.get("target_monthly_pension_reduction", 0),
                            "full_net_pension_without_commutation": cashflow_data.get("net_income", 0),
                            "recommendation": commutation_result.get("recommendation", "unknown"),
                        },
                        "_force_chained": True,
                    }
                    return json.dumps(combined_result, ensure_ascii=False)
            except Exception as chain_err:
                logger.warning("Force chaining failed for CALCULATE_PENSION_COMMUTATION: %s", chain_err)
            
            # אם השרשור נכשל, מחזירים רק את תוצאת ההיוון
            return json.dumps(commutation_result, ensure_ascii=False)

        elif tool_name == "CALCULATE_CAPITAL_WITHDRAWAL_TAX":
            amount = args.get("withdrawal_amount_gross")
            year = args.get("withdrawal_year", 2025)
            
            if amount is None:
                return "Error: Missing argument 'withdrawal_amount_gross'"
            
            result = agent_tools.calculate_capital_withdrawal_tax(
                withdrawal_amount_gross=float(amount),
                withdrawal_year=int(year),
            )
            
            if not result.get("success"):
                return f"Tool Error: {result.get('explanation')}"
            
            return json.dumps(result.get("result"), ensure_ascii=False)

        else:
            return f"Error: Tool '{tool_name}' not found."

    except Exception as e:
        logger.error("Tool execution failed: %s", e, exc_info=True)
        return f"System Error while executing tool: {str(e)}"


@router.post("/pension-chat", response_model=ChatResponse)
async def pension_chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """נקודת קצה לצ'אט עם סוכן ה-LLM הפנסיוני - כולל לולאת הרצה (Execution Loop)."""
    
    # Generate unique request_id for this conversation turn
    request_id = generate_request_id()
    
    # 1. הכנת הודעות התחלתיות עם קונטקסט
    messages, computed_data = _prepare_messages_with_context(request, db)
    original_user_msg = _find_last_user_message(request.messages)
    is_net_request = _is_net_pension_request(original_user_msg)
    force_max_exemption = _is_max_exemption_request(original_user_msg)
    
    # Log user message
    log_llm_event(
        request_id=request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
    )
    
    # 2. לולאת הרצה (Max 5 steps)
    max_steps = 5
    current_step = 0
    final_reply = ""
    
    while current_step < max_steps:
        logger.info("🔄 Agent Loop Step %d/%d for client %s", current_step + 1, max_steps, request.client_id)
        
        # שליחה ל-LLM
        raw_reply = pension_llm_service.chat(messages, request.client_id)
        
        # בדיקה האם יש קריאה לכלי (TOOL_CALL)
        if "###TOOL_CALL###" in raw_reply:
            # פירוק התשובה לטקסט + קריאת כלי
            parts = raw_reply.split("###TOOL_CALL###")
            text_part = parts[0].strip()
            tool_part = parts[1].strip()
            
            # אם יש טקסט לפני הכלי, נשמור אותו בהיסטוריה
            if text_part:
                messages.append(ChatMessage(role="assistant", content=text_part))
            
            # ניסיון פענוח JSON
            try:
                # מנקה שאריות כמו סימני Markdown
                tool_json_str = tool_part.strip('`').strip()
                tool_json_str = tool_json_str.splitlines()[0]
                
                tool_call_data = json.loads(tool_json_str)
                tool_name = tool_call_data.get("name")
                tool_args = tool_call_data.get("arguments", {})
                
                # Log tool call
                log_llm_event(
                    request_id=request_id,
                    event_type="tool_call",
                    payload={"name": tool_name, "arguments": tool_args},
                    client_id=request.client_id,
                )
                
                # אם המשתמש ביקש במפורש פטור מקסימלי, נוודא שה-LLM מפעיל apply_max_exemption
                if force_max_exemption and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
                    tool_args["apply_max_exemption"] = True
                
                # הוספת הודעת המודל (הבקשה להרצת כלי) להיסטוריה
                tool_msg_content = f"###TOOL_CALL### {json.dumps(tool_call_data)}"
                messages.append(ChatMessage(role="assistant", content=tool_msg_content))

                # הרצת הכלי בפועל
                tool_result = _execute_tool_call(
                    tool_name,
                    tool_args,
                    request.client_id,
                    db,
                    pension_portfolio=request.pension_portfolio,
                    force_max_exemption=force_max_exemption,
                )
                
                # Log tool result
                log_llm_event(
                    request_id=request_id,
                    event_type="tool_result",
                    payload={"tool_name": tool_name, "result": tool_result},
                    client_id=request.client_id,
                )
                
                # הזרקת התוצאה חזרה ל-LLM כהודעת System
                result_msg = (
                    f"🔧 **Tool Result ({tool_name}):**\n"
                    f"{tool_result}\n\n"
                    "הנחיות למודל: השתמש בנתוני הכלי האלה (ברוטו, נטו, מס, ופרטי פטור אם קיימים) כדי לבנות תשובה אחת סופית וברורה למשתמש על הקצבה נטו אחרי מס. "
                    "אל תחזור על ה-JSON הגולמי ואל תיתן תשובה נפרדת רק עבור הכלי עצמו."
                )
                messages.append(ChatMessage(role="system", content=result_msg))
                
                # === FORCE CHAINING: אכיפת שרשור ניתוח -> מס (BUILD/CASHFLOW -> TAX) ===
                # אם הופעל אחד מכלי הניתוח המרכזיים והמשתמש ביקש נטו, נריץ אוטומטית GET_TAX_PROJECTION
                original_user_msg = _find_last_user_message(request.messages)
                is_net = _is_net_pension_request(original_user_msg)
                
                gross_for_tax = None
                if is_net and tool_name in {"BUILD_TARGET_PENSION_PLAN", "RUN_RETIREMENT_CASHFLOW_ANALYSIS"}:
                    gross_for_tax = _extract_gross_income_for_tax(tool_name, tool_result)

                logger.info(
                    "🔗 Checking Force Chaining: Tool=%s, IsNet=%s, GrossForTax=%s, Msg='%s'",
                    tool_name,
                    is_net,
                    gross_for_tax,
                    original_user_msg[:50],
                )

                if is_net and gross_for_tax and gross_for_tax > 0:
                    logger.info("🔗 Force Chaining: Running GET_TAX_PROJECTION with gross=%s", gross_for_tax)
                    tax_result = _execute_tool_call(
                        "GET_TAX_PROJECTION",
                        {"gross_monthly_pension": gross_for_tax},
                        request.client_id,
                        db,
                        pension_portfolio=request.pension_portfolio,
                        force_max_exemption=force_max_exemption,
                    )
                    tax_msg = (
                        f"🔧 **Tool Result (GET_TAX_PROJECTION - Auto-chained):**\n{tax_result}\n\n"
                        "הנחיות למודל: שלב את תוצאת GET_TAX_PROJECTION (שיעור מס אפקטיבי, מס חודשי וכו') יחד עם נתוני RUN_RETIREMENT_CASHFLOW_ANALYSIS שכבר קיבלת. "
                        "עליך להסביר ללקוח קצבה ברוטו, מס, וקצבה נטו, ולהדגיש את השפעת הפטור המקסימלי (אם הופעל) על המס והנטו. אל תחזיר פלט כפול או לא מאוחד."
                    )
                    messages.append(ChatMessage(role="system", content=tax_msg))
                
                # ממשיכים לאיטרציה הבאה
                current_step += 1
                continue

            except json.JSONDecodeError:
                logger.error("Failed to parse TOOL_CALL JSON: %s", tool_part)
                messages.append(ChatMessage(role="system", content="Error: Invalid JSON in TOOL_CALL. Please try again."))
                current_step += 1
                continue
        
        else:
            # אין קריאה לכלי - זו התשובה הסופית
            final_reply = raw_reply
            break
    
    # Log final answer
    log_llm_event(
        request_id=request_id,
        event_type="final_answer",
        payload=final_reply,
        client_id=request.client_id,
    )
    
    if current_step >= max_steps:
        final_reply += "\n\n(הערה: עצרתי את רצף הפעולות האוטומטי כדי למנוע לולאה אינסופית)"

    return ChatResponse(
        reply=final_reply,
        computed_data=computed_data 
    )


@router.post("/pension-chat-stream")
async def pension_chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """נקודת קצה לצ'אט עם סוכן ה-LLM הפנסיוני בזרימה (streaming).
    
    כרגע תומך רק במחזור אחד (ללא לולאת סוכן מלאה), אך מזהה TOOL_CALL ומריץ אותו.
    """
    # Generate unique request_id for this conversation turn
    stream_request_id = generate_request_id()
    
    messages, computed_data = _prepare_messages_with_context(request, db)
    original_user_msg = _find_last_user_message(request.messages)
    is_net_request = _is_net_pension_request(original_user_msg)
    force_max_exemption = _is_max_exemption_request(original_user_msg)
    
    # Log user message
    log_llm_event(
        request_id=stream_request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    def generate(force_max_exemption_val: bool, req_id: str):
        # שלח נתונים מחושבים מהמערכת לפני תשובת ה-LLM
        if computed_data is not None:
            computed_json = json.dumps({
                "type": "computed_data",
                "data": computed_data.model_dump()
            }, ensure_ascii=False)
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        tool_call_marker = "###TOOL_CALL###"
        max_steps = 5
        current_step = 0

        # נשתמש בעותק מקומי של ההודעות כדי שנוכל לעדכן היסטוריה בין צעדים
        history_messages: list[ChatMessage] = list(messages)

        while current_step < max_steps:
            current_step += 1
            full_response = ""

            # הרצת המודל לצעד הנוכחי – ללא הזרמת טקסט חופשי למשתמש
            for chunk in pension_llm_service.chat_stream(history_messages, request.client_id):
                full_response += chunk

            # אם אין TOOL_CALL בתשובה – זו מועמדת להיות תשובה סופית
            if tool_call_marker not in full_response:
                # בשאלות נטו/אחרי מס, אם עדיין אין תוצאות כלים בהיסטוריה – אל תחזיר טקסט חופשי, דרוש מהמנוע TOOL_CALL בלבד
                has_tool_results = any(
                    m.role == "system" and "Tool Result (" in m.content
                    for m in history_messages
                )
                if is_net_request and not has_tool_results:
                    warning_msg = (
                        "אזהרה: אסור לך לענות על שאלות נטו או אחרי מס ללא הרצת כלים. "
                        "התשובה האחרונה שלך בוטלה. כעת עליך להחזיר רק בלוק יחיד בפורמט "
                        "###TOOL_CALL### {\"name\": \"TOOL_NAME\", \"arguments\": {...}} ללא טקסט נוסף."
                    )
                    history_messages.append(ChatMessage(role="system", content=warning_msg))
                    continue

                # אחרת – זו תשובה סופית, נחזיר אותה למשתמש
                # Log final answer (stream)
                log_llm_event(
                    request_id=req_id,
                    event_type="final_answer",
                    payload=full_response,
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )
                yield full_response
                break

            # ניסיון לפענח TOOL_CALL אחד מתוך התשובה האחרונה
            try:
                parts = full_response.split(tool_call_marker)
                if len(parts) <= 1:
                    break

                text_part = parts[0].strip()
                tool_part = parts[1].strip()
                tool_json_str = tool_part.strip('`').splitlines()[0]

                tool_data = json.loads(tool_json_str)
                tool_name = tool_data.get("name")
                tool_args = tool_data.get("arguments", {})
                
                # Log tool call (stream)
                log_llm_event(
                    request_id=req_id,
                    event_type="tool_call",
                    payload={"name": tool_name, "arguments": tool_args},
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )

                # אם המשתמש ביקש במפורש פטור מקסימלי, נוודא שה-LLM מפעיל apply_max_exemption
                if force_max_exemption_val and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
                    tool_args["apply_max_exemption"] = True

                # עדכון היסטוריית השיחה עם טקסט המודל וקריאת הכלי (הטקסט לא מוזרם ללקוח)
                if text_part:
                    history_messages.append(ChatMessage(role="assistant", content=text_part))

                tool_msg_content = f"###TOOL_CALL### {json.dumps(tool_data, ensure_ascii=False)}"
                history_messages.append(ChatMessage(role="assistant", content=tool_msg_content))

                # הרצת הכלי בפועל עם Session נפרד
                tool_db = SessionLocal()
                try:
                    tool_result = _execute_tool_call(
                        tool_name,
                        tool_args,
                        request.client_id,
                        tool_db,
                        pension_portfolio=request.pension_portfolio,
                        force_max_exemption=force_max_exemption_val,
                    )

                    # שליחת תוצאת הכלי ללקוח לשקיפות (ללא JSON גולמי עבור ניתוח פרישה)
                    user_tool_output = tool_result
                    if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
                        try:
                            data = json.loads(tool_result)
                            gross = data.get("total_guaranteed_income") or data.get("projected_pension")
                            net = data.get("total_guaranteed_income_net") or data.get("projected_pension_net")
                            income_tax = data.get("monthly_income_tax")
                            health_tax = data.get("monthly_health_tax")
                            total_tax = data.get("monthly_tax_deduction")
                            exempt_pct = data.get("exemption_percentage")
                            exempt_amount = data.get("exempt_pension_monthly")

                            lines: list[str] = []
                            lines.append("ניתוח פרישה – עיקרי התוצאות (חודשיות):")
                            if gross is not None:
                                lines.append(f"• קצבה ברוטו: {gross:,.0f} ₪")
                            if income_tax is not None or total_tax is not None:
                                tax_to_show = income_tax if income_tax is not None else total_tax
                                if tax_to_show is not None:
                                    lines.append(f"• מס הכנסה חודשי על הקצבה: {tax_to_show:,.0f} ₪")
                            if net is not None:
                                lines.append(f"• קצבה נטו לאחר מס: {net:,.0f} ₪")
                            if exempt_pct is not None or exempt_amount is not None:
                                extra_parts: list[str] = []
                                if exempt_pct is not None:
                                    extra_parts.append(f"אחוז קצבה פטורה: {exempt_pct:.1f}%")
                                if exempt_amount is not None:
                                    extra_parts.append(f"סכום קצבה פטורה חודשי: {exempt_amount:,.0f} ₪")
                                if extra_parts:
                                    lines.append("• פטור מקסימלי מקיבוע זכויות: " + " | ".join(extra_parts))

                            user_tool_output = "\n".join(lines)
                        except Exception:
                            user_tool_output = tool_result

                    yield f"\n\n🔧 **Tool Output ({tool_name}):**\n{user_tool_output}"
                    
                    # Log tool result (stream)
                    log_llm_event(
                        request_id=req_id,
                        event_type="tool_result",
                        payload={"tool_name": tool_name, "result": tool_result},
                        client_id=request.client_id,
                        extra={"endpoint": "stream"},
                    )

                    # הזרקת תוצאת הכלי חזרה להיסטוריה כהודעת System
                    history_messages.append(
                        ChatMessage(
                            role="system",
                            content=(
                                f"Tool Result ({tool_name}): {tool_result}\n\n"
                                "הנחיות למודל: שלב את נתוני הכלי (ברוטו, נטו, מס ופרטי פטור) בתוך תשובה אחת סופית וברורה ללקוח על הקצבה נטו, "
                                "ואל תחזור על ה-JSON עצמו כלשונו."
                            ),
                        )
                    )

                    # === FORCE CHAINING: אכיפת שרשור ניתוח -> מס (Stream) ===
                    original_user_msg = _find_last_user_message(request.messages)
                    is_net = _is_net_pension_request(original_user_msg)

                    logger.info(
                        "🔗 Checking Force Chaining (Stream): Tool=%s, IsNet=%s, Msg='%s'",
                        tool_name,
                        is_net,
                        original_user_msg[:50],
                    )

                    gross_for_tax = None
                    if is_net and tool_name in {"BUILD_TARGET_PENSION_PLAN", "RUN_RETIREMENT_CASHFLOW_ANALYSIS"}:
                        gross_for_tax = _extract_gross_income_for_tax(tool_name, tool_result)

                    logger.info(
                        "🔗 Force Chaining (Stream): Tool=%s, IsNet=%s, GrossForTax=%s",
                        tool_name,
                        is_net,
                        gross_for_tax,
                    )

                    if is_net and gross_for_tax and gross_for_tax > 0:
                        logger.info(
                            "🔗 Force Chaining (Stream): Running GET_TAX_PROJECTION with gross=%s",
                            gross_for_tax,
                        )
                        tax_result = _execute_tool_call(
                            "GET_TAX_PROJECTION",
                            {"gross_monthly_pension": gross_for_tax},
                            request.client_id,
                            tool_db,
                            pension_portfolio=request.pension_portfolio,
                            force_max_exemption=force_max_exemption_val,
                        )
                        yield f"\n\n🔧 **Tool Output (GET_TAX_PROJECTION - Auto-chained):**\n{tax_result}"
                        history_messages.append(
                            ChatMessage(
                                role="system",
                                content=(
                                    f"Tool Result (GET_TAX_PROJECTION): {tax_result}\n\n"
                                    "הנחיות למודל: שלב את נתוני המס (שיעור מס אפקטיבי, מס חודשי וכו') יחד עם תוצאת ניתוח הפרישה הקודמת, "
                                    "ונתֵח עבור הלקוח את הקצבה ברוטו, המס והקצבה נטו, תוך הדגשת תרומת הפטור המקסימלי אם הופעל."
                                ),
                            )
                        )

                finally:
                    tool_db.close()

            except Exception as e:
                logger.error("Stream Tool Execution Failed: %s", e)
                yield f"\n\n(Error executing tool: {str(e)})"
                break

    return StreamingResponse(generate(force_max_exemption, stream_request_id), media_type="text/plain; charset=utf-8")
