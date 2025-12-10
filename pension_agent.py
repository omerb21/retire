import sys
from typing import Dict, Any, List

from langchain.tools import tool
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


# --- שלב 1: פונקציית הליבה (MOCK) של מערכת תכנון הפרישה ---

def execute_retirement_plan(
    age: int,
    current_savings: float,
    monthly_contribution: float,
) -> Dict[str, float]:
    """\
    פונקציית MOCK שמדמה את מנוע תכנון הפרישה האמיתי.

    הפרמטרים:
    - age: גיל נוכחי של הלקוח בשנים.
    - current_savings: סכום החיסכון הפנסיוני הנוכחי בשקלים.
    - monthly_contribution: סכום ההפקדה החודשית העתידית בשקלים.

    הפונקציה מחזירה:
    - future_capital: הון עתידי משוער בגיל 65.
    - monthly_pension_estimate: קצבה חודשית מוערכת על בסיס כלל משיכה שמרני.
    """
    retirement_age = 65
    years_to_retirement = retirement_age - age

    if years_to_retirement <= 0:
        return {
            "error": "הגיל הנוכחי גבוה או שווה לגיל הפרישה. לא ניתן לבצע חישוב פנסיוני.",
            "future_capital": float(current_savings),
            "monthly_pension_estimate": 0.0,
        }

    annual_rate = 0.06  # תשואה שנתית נטו (לצורך הדגמה בלבד)

    # ערך עתידי של החיסכון הקיים
    future_savings = current_savings * ((1 + annual_rate) ** years_to_retirement)

    # ערך עתידי של ההפקדות החודשיות (כסדרת תשלומים)
    annual_contribution = monthly_contribution * 12.0
    if annual_rate == 0:
        future_contributions = annual_contribution * years_to_retirement
    else:
        future_contributions = annual_contribution * (
            ((1 + annual_rate) ** years_to_retirement - 1) / annual_rate
        )

    future_capital = future_savings + future_contributions

    # אומדן קצבה חודשית על בסיס כלל 4% משיכה שנתית
    monthly_pension_estimate = (future_capital * 0.04) / 12.0

    return {
        "future_capital": round(future_capital, 2),
        "monthly_pension_estimate": round(monthly_pension_estimate, 2),
    }


@tool
def calculate_pension_flow(
    age: int,
    current_savings: float,
    monthly_contribution: float,
) -> Dict[str, Any]:
    """מחשב את תזרים הפנסיה הצפוי עבור גיל, חיסכון נוכחי והפקדה חודשית נתונים."""
    print(
        f"\n[calculate_pension_flow] running mock engine with age={age}, "
        f"current_savings={current_savings}, monthly_contribution={monthly_contribution}"
    )
    return execute_retirement_plan(
        age=age,
        current_savings=current_savings,
        monthly_contribution=monthly_contribution,
    )


# --- שלב 3: חיבור ל-LLM וניהול שיחה ---


SYSTEM_PROMPT = (
    "אתה יועץ פנסיוני מקצועי, אמפתי וממוקד מטרה.\n"
    "המטרה שלך היא לעזור ללקוח להבין את מצבו הפנסיוני ואת ההשפעה של שינויים בהפקדות.\n\n"
    "תהליך העבודה שלך:\n"
    "1. בתחילת השיחה שאל בעדינות את הלקוח על הגיל הנוכחי שלו, החיסכון הפנסיוני הנוכחי שלו, והגובה שבו הוא מתכנן להפקיד בכל חודש.\n"
    "2. אם אחד מהנתונים חסר, שאל רק עליו בלי לחזור על כל שאר הפרטים.\n"
    "3. לאחר שנאספו שלושת הנתונים, מנוע חישוב חיצוני ירוץ מאחורי הקלעים ויחזיר לך תוצאה מספרית.\n"
    "   כאשר תראה בטקסט שהועבר אליך תיאור של נתוני קלט ותוצאות חישוב, הסבר ללקוח במילים פשוטות מה המשמעות.\n"
    "4. כאשר מוצג בפניך תרחיש 'מה אם' עם שינוי בהפקדה החודשית, השווה בקצרה בין התוצאה החדשה לישנה והדגש את ההשפעה על ההון העתידי והקצבה.\n"
    "5. היה ממוקד, ידידותי ולא טכני מדי, ותמיד הזמן את הלקוח לשאול שאלות נוספות או לבחון עוד תרחישים.\n"
)


def run_chat_demo() -> None:
    """מדגים שיחה שלמה עם היועץ, כולל תרחיש 'מה אם'."""
    try:
        llm = ChatOllama(
            model="gemma3:4b",
            base_url="http://localhost:11434",
        )
    except Exception as exc:
        print(
            "שגיאה בחיבור ל-Ollama (gemma3:4b). ודא שאולמה רץ ושמודל 'gemma3:4b' מותקן.",
            file=sys.stderr,
        )
        raise exc

    history: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]

    def step(user_input: str) -> None:
        nonlocal history
        print(f"\n>>> לקוח: {user_input}")
        history.append(HumanMessage(content=user_input))
        ai_message = llm.invoke(history)
        history.append(ai_message)
        print(f"\n<<< סוכן: {ai_message.content}")
        print("-" * 60)

    print("=== הדגמת יועץ פרישה (MOCK) ===")

    # שלב 1–3: איסוף נתונים בסיסיים מהלקוח
    step("שלום, אני רוצה לחשב את הפנסיה שלי.")
    step("אני בן 40 ומפקיד 3000 שח בחודש.")
    step("החיסכון הנוכחי שלי הוא 950000 שח.")

    # הרצת חישוב בסיסי באמצעות ה"כלי"
    base_args = {"age": 40, "current_savings": 950000.0, "monthly_contribution": 3000.0}
    base_result = calculate_pension_flow.invoke(base_args)

    explain_prompt = (
        "סיכום ביניים: ללקוח יש גיל 40, חיסכון פנסיוני נוכחי של 950,000 ש""ח "
        "והפקדה חודשית של 3,000 ש""ח. מנוע החישוב החזיר הון עתידי משוער של "
        f"{base_result.get('future_capital')} ש""ח וקצבה חודשית מוערכת של "
        f"{base_result.get('monthly_pension_estimate')} ש""ח. "
        "נא הסבר ללקוח בעברית פשוטה מה המשמעות של המספרים האלה לגיל הפרישה שלו."
    )
    step(explain_prompt)

    # תרחיש "מה אם" – הגדלת ההפקדה החודשית
    what_if_args = {"age": 40, "current_savings": 950000.0, "monthly_contribution": 5000.0}
    what_if_result = calculate_pension_flow.invoke(what_if_args)

    what_if_prompt = (
        "הלקוח מבקש תרחיש 'מה אם' שבו ההפקדה החודשית גדלה מ-3,000 ש""ח ל-5,000 ש""ח.\n"
        f"בתרחיש המקורי: הון עתידי משוער {base_result.get('future_capital')} ש""ח, "
        f"קצבה חודשית מוערכת {base_result.get('monthly_pension_estimate')} ש""ח.\n"
        f"בתרחיש החדש: הון עתידי משוער {what_if_result.get('future_capital')} ש""ח, "
        f"קצבה חודשית מוערכת {what_if_result.get('monthly_pension_estimate')} ש""ח.\n"
        "הסבר ללקוח באופן השוואתי מה ההשפעה של הגדלת ההפקדה על עתידו הפנסיוני."
    )
    step(what_if_prompt)

    print("=== סוף הדגמה ===")


if __name__ == "__main__":
    run_chat_demo()
