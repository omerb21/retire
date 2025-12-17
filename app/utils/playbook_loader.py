"""
Playbook Loader – טעינת דוגמאות Playbook לשימוש כ-Few-Shot Examples

מודול זה טוען דוגמאות שיחה מתוך agent_conversation_examples.md
ומספק אותן בפורמט מוכן להזרקה ל-System Prompt או כ-Few-Shot.
"""
import os
from pathlib import Path
from typing import Optional

# נתיב לקובץ הדוגמאות
EXAMPLES_FILE = Path(__file__).parent.parent.parent / "MD" / "docs" / "agent_conversation_examples.md"


def _load_examples_file() -> str:
    """טוען את קובץ הדוגמאות אם קיים."""
    if not EXAMPLES_FILE.exists():
        return ""
    try:
        with open(EXAMPLES_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _extract_example_by_number(content: str, example_num: int) -> str:
    """מחלץ דוגמה ספציפית לפי מספר (1-6)."""
    if not content:
        return ""
    
    # מחפש את הכותרת של הדוגמה
    start_marker = f"## דוגמה {example_num} –"
    end_marker = "## דוגמה"
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        return ""
    
    # מחפש את סוף הדוגמה (תחילת הדוגמה הבאה או סוף הקובץ)
    remaining = content[start_idx + len(start_marker):]
    end_idx = remaining.find(end_marker)
    
    if end_idx == -1:
        # אם אין דוגמה הבאה, לוקח עד סוף הקובץ (או עד "איך להשתמש")
        usage_marker = "## איך להשתמש"
        usage_idx = remaining.find(usage_marker)
        if usage_idx != -1:
            end_idx = usage_idx
        else:
            end_idx = len(remaining)
    
    example_text = content[start_idx:start_idx + len(start_marker) + end_idx].strip()
    return example_text


def get_net_pension_example() -> str:
    """
    מחזיר דוגמה לחישוב קצבה נטו עם פטור מקסימלי (Playbook #1).
    זו הדוגמה הכי חשובה לחיזוק השימוש ב-RUN_RETIREMENT_CASHFLOW_ANALYSIS.
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 1)


def get_comparison_example() -> str:
    """
    מחזיר דוגמה להשוואת תאריכי פרישה (Playbook #2).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 2)


def get_explanation_example() -> str:
    """
    מחזיר דוגמה לשאלת הסבר בלבד (Playbook #4 במסמך).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 4)


def get_commutation_example() -> str:
    """
    מחזיר דוגמה להיוון קצבה (Playbook #6).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 6)


def get_capital_withdrawal_example() -> str:
    """
    מחזיר דוגמה למשיכת כספי הון (Playbook #7).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 7)


def get_summary_report_example() -> str:
    """
    מחזיר דוגמה לדו"ח סיכום מובנה (Playbook #8).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 8)


def get_out_of_scope_example() -> str:
    """
    מחזיר דוגמה לטיפול בבקשות מחוץ לתחום (Playbook #9).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 9)


def get_contextual_narrative_example() -> str:
    """
    מחזיר דוגמה לנרטיב השוואתי (Playbook #10 - Contextual Narrative).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 10)


def get_pre_tool_check_example() -> str:
    """
    מחזיר דוגמה לזיהוי פערי מידע (Playbook #11 - Pre-Tool Check).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 11)


def get_minimum_pension_rule_example() -> str:
    """
    מחזיר דוגמה לדחייה רגולטורית - קצבת מינימום מזכה (Playbook #12).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 12)


def get_job_termination_whatif_example() -> str:
    """
    מחזיר דוגמה לניתוח רגישות עזיבת עבודה (Playbook #13 - What-If Analysis).
    """
    content = _load_examples_file()
    return _extract_example_by_number(content, 13)


def get_relevant_example(user_message: str) -> Optional[str]:
    """
    מזהה את סוג השאלה ומחזיר דוגמה רלוונטית.
    
    Args:
        user_message: הודעת המשתמש האחרונה
        
    Returns:
        דוגמה רלוונטית או None אם אין התאמה ברורה
    """
    if not user_message:
        return None
    
    msg_lower = user_message.lower()
    
    # זיהוי שאלות השוואה
    comparison_keywords = ["להשוות", "השוואה", "מול", "לעומת", "או", "עדיף"]
    if any(kw in msg_lower for kw in comparison_keywords):
        # בודק אם יש שני תאריכים/שנים/גילאים
        import re
        years = re.findall(r'\b(20\d{2})\b', user_message)
        ages = re.findall(r'\b(6[0-9]|7[0-5])\b', user_message)
        if len(years) >= 2 or len(ages) >= 2:
            return get_comparison_example()
    
    # זיהוי שאלות היוון קצבה
    commutation_keywords = ["היוון", "לוותר על", "אוותר על", "סכום חד-פעמי", "חד פעמי", "במקום קצבה", "להמיר קצבה"]
    if any(kw in msg_lower for kw in commutation_keywords):
        return get_commutation_example()
    
    # זיהוי שאלות משיכת כספי הון
    withdrawal_keywords = ["משיכה מקופת", "משיכה מקרן", "למשוך כסף", "למשוך מהקופה", "למשוך מהחיסכון", "משיכת כספים", "אמשוך"]
    if any(kw in msg_lower for kw in withdrawal_keywords):
        return get_capital_withdrawal_example()
    
    # זיהוי בקשות לדו"ח סיכום
    report_keywords = ["סכם את", "תן לי סיכום", "הפק דו\"ח", "דו\"ח מסכם", "מסקנה סופית", "סיכום של", "לראות את כל המידע"]
    if any(kw in msg_lower for kw in report_keywords):
        return get_summary_report_example()
    
    # זיהוי בקשות מחוץ לתחום (השקעות, נדל"ן, קריפטו וכו')
    out_of_scope_keywords = [
        "להשקיע", "השקעה", "מניות", "בורסה", "קריפטו", "ביטקוין", "נדל\"ן", 
        "לקנות דירה", "משכנתא", "תיק השקעות", "קרן נאמנות", "מט\"ח",
        "ביטוח רכב", "ביטוח בריאות", "ביטוח דירה", "תספר בדיחה"
    ]
    if any(kw in msg_lower for kw in out_of_scope_keywords):
        return get_out_of_scope_example()
    
    # זיהוי שאלות עזיבת עבודה / פיצויים (What-If Analysis)
    job_termination_keywords = [
        "עזבתי עבודה", "פוטרתי", "התפטרתי", "פיצויים", "פיצויי פיטורין",
        "מה לעשות עם הכסף", "למשוך או להשאיר", "רצף קצבה", "רצף הון",
        "עזיבת עבודה", "סיום עבודה"
    ]
    if any(kw in msg_lower for kw in job_termination_keywords):
        return get_job_termination_whatif_example()
    
    # זיהוי שאלות הסבר
    explanation_keywords = ["מה זה", "תסביר", "איך עובד", "איך מחשבים", "הסבר"]
    if any(kw in msg_lower for kw in explanation_keywords):
        return get_explanation_example()
    
    # זיהוי שאלות נטו/חישוב (ברירת מחדל לשאלות מספריות)
    net_keywords = ["נטו", "אחרי מס", "כמה אקבל", "כמה נשאר", "פטור מקסימלי", "קיבוע"]
    if any(kw in msg_lower for kw in net_keywords):
        return get_net_pension_example()
    
    # אם יש אזכור של שנה או גיל פרישה, כנראה שאלת חישוב
    import re
    if re.search(r'\b(20\d{2})\b', user_message) or re.search(r'גיל\s*(6[0-9]|7[0-5])', user_message):
        return get_net_pension_example()
    
    return None


def format_example_as_few_shot(example: str) -> str:
    """
    מעצב דוגמה לפורמט Few-Shot מתאים להזרקה ל-context.
    """
    if not example:
        return ""
    
    return (
        "\n\n---\n"
        "📚 **דוגמה להתנהגות נכונה:**\n\n"
        f"{example}\n"
        "---\n"
    )


def get_condensed_workflow_example() -> str:
    """
    מחזיר דוגמה מקוצרת של Workflow לחישוב נטו.
    זו גרסה קומפקטית שמתאימה להזרקה לכל שיחה.
    """
    return """
📋 **דוגמת Workflow – חישוב קצבה נטו:**

**שאלת לקוח:** "כמה אקבל נטו אם אפרוש ב-2028 עם פטור מקסימלי?"

**פעולת הסוכן:**
1. מפעיל: `###TOOL_CALL### {"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {"retirement_date": "2028-01-01", "apply_max_exemption": true}}`
2. מקבל תוצאות מהכלי (ברוטו, מס הכנסה, נטו, פטור)
3. מסכם ללקוח בעברית פשוטה:
   - קצבה ברוטו: X ₪
   - מס הכנסה חודשי: Y ₪
   - קצבה נטו: Z ₪
   - פטור מקיבוע זכויות: W% (סכום פטור: V ₪)
"""
