def get_tool_display_name_hebrew(tool_name: str | None) -> str:
    if not isinstance(tool_name, str) or not tool_name.strip():
        return "כלי"

    mapping = {
        "BUILD_TARGET_PENSION_PLAN": "בניית תכנית קצבה",
        "GET_TAX_PROJECTION": "הערכת מס",
        "GET_TAX_PARAMS": "פרמטרי מס",
        "GET_PENSION_PRODUCTS": "שליפת מוצרים בתיק",
        "CHECK_DATA_COMPLETENESS": "בדיקת שלמות נתונים",
        "CALCULATE_TAX_EXEMPT_PENSION": "חישוב קצבה פטורה",
        "RUN_RETIREMENT_CASHFLOW_ANALYSIS": "ניתוח פרישה",
        "RUN_RETIREMENT_SCENARIOS": "הרצת תרחישי פרישה",
        "SELECT_TARGET_PENSION_SCENARIO": "בחירת תרחיש ליעד",
        "FIND_OPTIMAL_SCENARIO": "מציאת תרחיש אופטימלי",
        "EXECUTE_RETIREMENT_SCENARIO": "החלת תרחיש",
        "CALCULATE_PENSION_COMMUTATION": "חישוב היוון קצבה",
        "CALCULATE_FIXATION_OF_RIGHTS": "חישוב קיבוע זכויות",
        "CALCULATE_CAPITAL_WITHDRAWAL_TAX": "חישוב מס על משיכת הון",
        "CALCULATE_TAX_SPREAD_BENEFIT": "חישוב הטבת מס בפריסה",
        "PROCESS_TERMINATION": "עזיבת עבודה (מעסיק נוכחי)",
        "PROJECT_TOTAL_ANNUITY": "חישוב קצבה כוללת",
        "GET_ACCOUNT_DETAILS": "שליפת פרטי חשבון",
        "SUBMIT_TAX_COMMUTATION": "ביצוע קיבוע/היוון/פריסה",
        "EXECUTE_PENSION_COMMUTATION": "ביצוע היוון קצבה",
        "GENERATE_FULL_REPORT": "הפקת דוח",
        "GENERATE_TAX_DEDUCTION_DOCUMENTS": "הפקת מסמכי מס",
        "TRANSFORM_FUNDS_TO_ASSETS": "המרת תיק לנכסים",
        "CREATE_INDIVIDUAL_ASSET": "יצירת נכס ידני",
        "CREATE_TAX_EXEMPT_GRANT": "יצירת מענק פטור",
        "SET_CURRENT_EMPLOYER_DETAILS": "עדכון פרטי מעסיק נוכחי",
        "EXECUTE_WORK_TERMINATION": "ביצוע עזיבת עבודה",
        "GET_CLIENT_SNAPSHOT": "שליפת מצב לקוח",
    }
    return mapping.get(tool_name, tool_name)


def normalize_tool_name(tool_name: str | None) -> str | None:
    if tool_name is None:
        return None

    if not isinstance(tool_name, str):
        return tool_name

    normalized = tool_name.strip()
    if not normalized:
        return tool_name

    upper = normalized.upper()
    known_constants = {
        "BUILD_TARGET_PENSION_PLAN",
        "GET_TAX_PROJECTION",
        "GET_TAX_PARAMS",
        "GET_PENSION_PRODUCTS",
        "CHECK_DATA_COMPLETENESS",
        "CALCULATE_TAX_EXEMPT_PENSION",
        "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        "RUN_RETIREMENT_SCENARIOS",
        "SELECT_TARGET_PENSION_SCENARIO",
        "FIND_OPTIMAL_SCENARIO",
        "EXECUTE_RETIREMENT_SCENARIO",
        "CALCULATE_PENSION_COMMUTATION",
        "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
        "CALCULATE_TAX_SPREAD_BENEFIT",
        "PROCESS_TERMINATION",
        "PROJECT_TOTAL_ANNUITY",
        "GET_ACCOUNT_DETAILS",
        "SUBMIT_TAX_COMMUTATION",
        "EXECUTE_PENSION_COMMUTATION",
        "GENERATE_FULL_REPORT",
        "GENERATE_TAX_DEDUCTION_DOCUMENTS",
        "TRANSFORM_FUNDS_TO_ASSETS",
        "CREATE_INDIVIDUAL_ASSET",
        "CREATE_TAX_EXEMPT_GRANT",
        "CREATE_ADDITIONAL_INCOME",
        "SET_CURRENT_EMPLOYER_DETAILS",
        "EXECUTE_WORK_TERMINATION",
        "CALCULATE_FIXATION_OF_RIGHTS",
        "GET_CLIENT_SNAPSHOT",
    }
    if upper in known_constants:
        return upper

    lowered = normalized.lower()
    hebrew_map = {
        "סיום עבודה": "PROCESS_TERMINATION",
        "עזיבת עבודה": "PROCESS_TERMINATION",
        "עזיבת עבודה (מעסיק נוכחי)": "PROCESS_TERMINATION",
        "סיום עבודה (מעסיק נוכחי)": "PROCESS_TERMINATION",
        "סיום עבודה למעסיק הנוכחי": "PROCESS_TERMINATION",
        "ביצוע עזיבת עבודה": "PROCESS_TERMINATION",
        "בצע עזיבת עבודה": "PROCESS_TERMINATION",
        "המרת תיק לנכסים": "TRANSFORM_FUNDS_TO_ASSETS",
        "ניתוח פרישה": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        "הערכת מס": "GET_TAX_PROJECTION",
        "בניית תכנית קצבה": "BUILD_TARGET_PENSION_PLAN",
        "קיבוע": "CALCULATE_FIXATION_OF_RIGHTS",
        "קיבוע זכויות": "CALCULATE_FIXATION_OF_RIGHTS",
        "חשב קיבוע": "CALCULATE_FIXATION_OF_RIGHTS",
        "חשב קיבוע זכויות": "CALCULATE_FIXATION_OF_RIGHTS",
        "חישוב קיבוע": "CALCULATE_FIXATION_OF_RIGHTS",
        "חישוב קיבוע זכויות": "CALCULATE_FIXATION_OF_RIGHTS",
    }
    mapped = hebrew_map.get(lowered)
    if mapped:
        return mapped

    return tool_name
