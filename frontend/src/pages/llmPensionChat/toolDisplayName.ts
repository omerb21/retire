export function getToolDisplayNameHebrew(toolName: string): string {
  const mapping: Record<string, string> = {
    RUN_RETIREMENT_SCENARIOS: "הרצת תרחישי פרישה",
    EXECUTE_RETIREMENT_SCENARIO: "החלת תרחיש",
    CHECK_DATA_COMPLETENESS: "בדיקת שלמות נתונים",
    GET_TAX_PROJECTION: "הערכת מס",
    SELECT_TARGET_PENSION_SCENARIO: "בחירת תרחיש ליעד",
    BUILD_TARGET_PENSION_PLAN: "בניית תכנית קצבה",
    FIND_OPTIMAL_SCENARIO: "מציאת תרחיש אופטימלי",
    RUN_RETIREMENT_CASHFLOW_ANALYSIS: "ניתוח פרישה",
    PROCESS_TERMINATION: "סיום עבודה",
    TRANSFORM_FUNDS_TO_ASSETS: "המרת תיק לנכסים",
    CALCULATE_CAPITAL_WITHDRAWAL_TAX: "חישוב מס על משיכת הון",
    CALCULATE_TAX_SPREAD_BENEFIT: "חישוב הטבת מס בפריסה",
    CALCULATE_TAX_EXEMPT_PENSION: "חישוב קצבה פטורה (קיבוע זכויות)",
    GENERATE_FULL_REPORT: "הפקת דוח",
    GENERATE_TAX_DEDUCTION_DOCUMENTS: "הפקת מסמכי מס",
    GET_ACCOUNT_DETAILS: "שליפת פרטי חשבון",
  };
  return mapping[toolName] || toolName;
}
