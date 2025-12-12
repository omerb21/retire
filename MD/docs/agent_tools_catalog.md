# Agent Tools Catalog

קטלוג זה מתעד את הכלים המרכזיים שהסוכן (LLM) יכול להפעיל דרך `AgentToolsService`.
המטרה היא לתת מיפוי ברור בין השם שה‑LLM רואה לבין הפונקציה במערכת, הפרמטרים, והפלט המשמעותי ללקוח.

## פורמט כללי לכלי

לכל כלי יש מבנה פלט אחיד:

- success: האם ההרצה הצליחה.
- tool_name: שם הכלי כפי שהסוכן מכיר אותו.
- result: מילון נתונים מובנים לשימוש פנימי של הסוכן.
- explanation: הסבר טקסטואלי קצר לסוכן, שנועד לעזור לו לסכם ללקוח.

---

## CHECK_DATA_COMPLETENESS

- שם כלי ל‑LLM: CHECK_DATA_COMPLETENESS
- פונקציה: AgentToolsService.check_data_completeness
- קלט:
  - ללא פרמטרים (משתמש ב‑client_id מתוך השירות).
- פלט עיקרי ב‑result:
  - complete (bool): האם הנתונים הקריטיים קיימים.
  - missing (list[str]): שדות קריטיים שחסרים (למשל תאריך לידה).
  - warnings (list[str]): אזהרות על נתונים חלקיים/חסרים.
  - recommendations (list[str]): המלצות פרקטיות להשלמת נתונים.
  - pension_funds_count (int): מספר מוצרים פנסיוניים שנמצאו.
  - scenarios_count (int): מספר תרחישי פרישה שמורים.
  - fixation_exists (bool): האם קיים קיבוע זכויות.
  - employers_count (int): מספר מעסיקים נוכחיים.
- שימושים מומלצים לסוכן:
  - לפני הרצת תרחישי פרישה/חישובי מס, כדי להבין האם חסר מידע.
  - להסביר ללקוח מה עוד צריך להשלים במערכת.

---

## GET_SAVED_SCENARIOS

- שם כלי ל‑LLM: GET_SAVED_SCENARIOS
- פונקציה: AgentToolsService.get_saved_scenarios_summary
- קלט:
  - retirement_age (אופציונלי, int): סינון תרחישים לפי גיל פרישה.
- פלט עיקרי ב‑result:
  - scenarios (list[dict]): רשימת תרחישים שמורים, כולל:
    - scenario_id (int)
    - scenario_name (str)
    - retirement_age (int | None)
    - total_pension_monthly (float)
    - total_capital (float)
    - estimated_npv (float)
  - count (int): מספר התרחישים שנמצאו.
- שימושים מומלצים לסוכן:
  - כשלקוח שואל על "תרחישים שכבר הרצנו".
  - כהכנה לבחירת תרחיש אופטימלי ליעד קצבה.

---

## SELECT_TARGET_PENSION_SCENARIO

- שם כלי ל‑LLM: SELECT_TARGET_PENSION_SCENARIO
- פונקציה: AgentToolsService.select_optimal_scenario_for_target_pension
- קלט:
  - target_monthly_pension (float): יעד קצבה חודשי ב‑₪.
  - retirement_age (אופציונלי, int): אם רוצים להגביל לגיל פרישה מסוים.
- פלט עיקרי ב‑result:
  - target_achieved (bool): האם יש תרחיש שמגיע ליעד.
  - selected_scenario (dict | None): התרחיש המומלץ.
  - alternatives_count (int, במידה ויש): מספר אלטרנטיבות שעומדות ביעד.
  - all_achieving (list[dict], במידה ויש): כל התרחישים שמגיעים ליעד.
- שימושים מומלצים לסוכן:
  - כשלקוח מביע יעד נטו/ברוטו חודשי, והמערכת כבר כוללת תרחישים שמורים.
  - כחלק מהסבר: "איזה תרחיש הכי קרוב ליעד שלך".

---

## RUN_RETIREMENT_SCENARIOS

- שם כלי ל‑LLM: RUN_RETIREMENT_SCENARIOS
- פונקציה: AgentToolsService.run_retirement_scenarios
- קלט:
  - retirement_age (int): גיל פרישה יעד (50–80, בהתאם לבדיקות בקוד).
  - pension_portfolio (אופציונלי, list[dict]): תיק פנסיוני מותאם (אם רוצים לעקוף את מה שב‑DB).
  - include_current_employer_termination (bool): האם לקחת בחשבון פיצויי פיטורין ממעסיק נוכחי.
- פלט עיקרי ב‑result:
  - retirement_age (int): גיל הפרישה שהורץ.
  - scenarios (list[dict]): סיכום של תרחישים שנשמרו:
    - scenario_id, scenario_key, scenario_name,
    - total_pension_monthly, total_capital, estimated_npv.
  - max_pension (float): קצבה חודשית מקסימלית בין התרחישים.
  - max_capital (float): הון מקסימלי בין התרחישים.
  - max_npv (float): NPV מקסימלי בין התרחישים.
- שימושים מומלצים לסוכן:
  - כשלקוח מבקש "תרחישי פרישה" לגיל מסוים.
  - כבסיס להשוואה בין תרחישים (קצבה מקסימלית, הון מקסימלי, NPV מקסימלי).

---

## FIND_OPTIMAL_SCENARIO

- שם כלי ל‑LLM: FIND_OPTIMAL_SCENARIO
- פונקציה: AgentToolsService.find_optimal_scenario_for_target
- קלט:
  - target_monthly_pension (float): יעד קצבה חודשי.
  - min_retirement_age (אופציונלי, int): גיל פרישה מינימלי לבדיקה.
  - max_retirement_age (אופציונלי, int): גיל פרישה מקסימלי לבדיקה.
- פלט עיקרי ב‑result:
  - target_monthly_pension (float): היעד שנבדק.
  - selected_scenario (dict): התרחיש המומלץ (או התרחיש עם הקצבה הגבוהה ביותר במידה ולא מגיעים ליעד).
  - target_achieved (bool): האם נמצא תרחיש שמגיע ליעד.
  - ages_checked (list[int]): גילי פרישה שנבדקו.
  - sensitivity_analysis (list[dict]): ניתוח רגישות של קצבה לפי גיל פרישה.
- שימושים מומלצים לסוכן:
  - כשלקוח אומר "אני רוצה X ₪ בחודש, באיזה גיל כדאי לי לפרוש".
  - לבניית הסבר על איך דחיית/הקדמת גיל פרישה משפיעה על הקצבה.

---

## RUN_RETIREMENT_CASHFLOW_ANALYSIS

- שם כלי ל‑LLM: RUN_RETIREMENT_CASHFLOW_ANALYSIS
- פונקציה: AgentToolsService.run_retirement_cashflow_analysis
- קלט:
  - retirement_date (str): תאריך פרישה בפורמט YYYY-MM-DD.
  - desired_monthly_income (אופציונלי, float): יעד הכנסה חודשית נטו/ברוטו לפרישה. אם לא סופק – ברירת מחדל: כ‑70% מהשכר האחרון או 15,000 ₪.
  - apply_max_exemption (bool): האם להחיל פטור מקסימלי מקיבוע זכויות על הקצבה החודשית (כבר מחובר ללוגיקת קיבוע זכויות).
- פלט עיקרי ב‑result:
  - retirement_date (str), retirement_age (int).
  - projected_pension (float): קצבת פנסיה חודשית ברוטו.
  - social_security (float): קצבת אזרח ותיק (ביטוח לאומי) חודשית.
  - total_guaranteed_income (float): הכנסה חודשית ברוטו מובטחת (קצבה + ביטוח לאומי).
  - apply_max_exemption (bool): האם הופעל פטור מקסימלי.
  - exemption_percentage (float): אחוז פטור מהקצבה (באחוזים).
  - exempt_pension_monthly (float): חלק מהקצבה החודשית הפטורה ממס.
  - monthly_income_tax (float): מס הכנסה חודשי על הקצבה.
  - monthly_health_tax (float): מס בריאות חודשי.
  - monthly_tax_deduction (float): סה"כ ניכויי מס חודשיים.
  - projected_pension_net (float): קצבת פנסיה חודשית נטו.
  - total_guaranteed_income_net (float): הכנסה חודשית נטו מובטחת (קצבה נטו + ביטוח לאומי).
  - desired_monthly_income (float): היעד כפי שנלקח לקלט.
  - monthly_deficit_or_surplus (float): עודף/גירעון חודשי ביחס ליעד (שלילי = גירעון).
  - required_capital_withdrawal (float): משיכת הון חודשית נדרשת כדי לסגור את הפער.
  - total_liquid_capital (float): סה"כ הון נזיל שנלקח בחשבון.
  - capital_sufficiency_years (float): כמה שנים ההון יספיק לכסות את הגירעון.
  - is_sustainable (bool): האם המצב בר־קיימא (ההון מספיק עד תוחלת החיים).
- שימושים מומלצים לסוכן:
  - כשלקוח שואל על "כמה אקבל נטו בפרישה בתאריך/שנה מסוימת".
  - כשצריך לשלב ברוטו, מס, נטו והון לכיסוי גירעון בתשובה אחת.
  - כשלקוח מדבר על "פטור מקסימלי" / "קיבוע זכויות" – להפעיל את הכלי עם apply_max_exemption=True.

---

## GET_TAX_PROJECTION

- שם כלי ל‑LLM: GET_TAX_PROJECTION
- פונקציה: AgentToolsService.get_tax_projection
- קלט:
  - monthly_pension (אופציונלי, float): קצבה חודשית ברוטו לחישוב המס. אם לא סופק – נלקח מתרחיש פרישה אחרון במערכת.
  - additional_income (אופציונלי, float): הכנסות חודשיות נוספות (שכר, הכנסות אחרות).
- פלט עיקרי ב‑result:
  - monthly_pension (float): הקצבה שנלקחה לחישוב.
  - additional_income (float): הכנסות נוספות.
  - total_annual_income (float): סה"כ הכנסה שנתית.
  - annual_tax (float): מס שנתי משוער.
  - monthly_tax (float): מס חודשי משוער.
  - effective_rate (float): שיעור מס אפקטיבי (באחוזים מההכנסה).
  - exempt_pension_percentage (float): אחוז מהקצבה הפטור ממס (אם יש נתוני קיבוע זכויות).
  - tax_breakdown (list[dict]): פירוט לפי מדרגות מס.
- שימושים מומלצים לסוכן:
  - כשצריך להעמיק בחישוב המס מעבר למה שמובנה ב‑RUN_RETIREMENT_CASHFLOW_ANALYSIS.
  - כשלקוח שואל ספציפית על שיעור מס אפקטיבי או פירוט מדרגות.
  - כחלק משרשרת: הפקת ברוטו מכלי אחר → קריאה ל‑GET_TAX_PROJECTION → הסבר ללקוח.

---

## CALCULATE_REQUIRED_GROSS_WITHDRAWAL

- שם כלי ל‑LLM: CALCULATE_REQUIRED_GROSS_WITHDRAWAL
- פונקציה: AgentToolsService.calculate_required_gross_withdrawal
- קלט:
  - desired_net_income (float): יעד הכנסה חודשית נטו (קצבה מובטחת + משיכה מהון).
  - guaranteed_pension (float): קצבה חודשית מובטחת (לפני משיכה מההון).
  - retirement_date (אופציונלי, str): תאריך פרישה (לצורך בחירת שנת מס).
- פלט עיקרי ב‑result:
  - required_gross_withdrawal (float): משיכת ברוטו חודשית נדרשת מההון.
  - total_gross_income (float): סך ההכנסה החודשית ברוטו (קצבה + משיכה).
  - final_net_income (float): ההכנסה החודשית נטו שמתקבלת בפועל.
  - tax_amount (float): סה"כ מס חודשי על כל ההכנסה.
  - is_net_goal_achieved (bool): האם יעד הנטו הושג.
  - tax_exemption_applied (float): פטור קצבה חודשי שנוצל בפועל.
  - exemption_source (str): מקור נתוני הפטור (FixationResult, ברירת מחדל וכו').
- שימושים מומלצים לסוכן:
  - כשלקוח אומר: "אני צריך X ₪ נטו בחודש – כמה אני צריך למשוך מההון בנוסף לקצבה?".
  - כשצריך לתכנן יחס בין קצבה קבועה לבין משיכה מההון לאורך זמן.

---

## BUILD_TARGET_PENSION_PLAN

- שם כלי ל‑LLM: BUILD_TARGET_PENSION_PLAN
- פונקציה: AgentToolsService.build_target_pension_plan
- קלט:
  - target_monthly_pension (float): יעד קצבה חודשי.
  - retirement_age (אופציונלי, int): גיל פרישה מתוכנן. אם לא סופק – נקבע לפי גיל נוכחי וברירת מחדל.
- פלט עיקרי ב‑result:
  - target_monthly_pension (float): יעד הקצבה.
  - retirement_age (int): גיל הפרישה שבו התכנית נבנתה.
  - target_achieved (bool): האם ניתן להגיע ליעד.
  - accumulated_pension (float): קצבה חודשית שתתקבל לפי התכנית.
  - gap_to_target (float): פער מהיעד (אם יש).
  - remaining_capital (float): הון שנשאר כהון (לא הומר לקצבה).
  - plan_steps (list[dict]): צעדים מפורטים – אילו מוצרים ממירים, בכמה, ואיזו קצבה מוסיפים.
  - sources_used (list[dict]): מקורות קצבה שנוצלו (כולל האם חלקי/מלא).
  - sources_not_used (list[dict]): מקורות שנותרו כהון.
  - advantages (list[str]), disadvantages (list[str]): יתרונות וחסרונות התכנית.
- שימושים מומלצים לסוכן:
  - כשלקוח אומר "אני רוצה X ₪ קצבה – מאיזה מוצרים כדאי לבנות את זה?".
  - להצגת תכנית פעולה מפורטת: אילו קופות מומלץ להפוך לקצבה, ומה נשאר כהון.

---

## GET_PENSION_PRODUCTS

- שם כלי ל‑LLM: GET_PENSION_PRODUCTS
- פונקציה: AgentToolsService.get_pension_products
- קלט:
  - ללא פרמטרים – מבוסס על הלקוח הנוכחי.
- פלט עיקרי ב‑result:
  - products (list[dict]): רשימת מוצרים (פנסיוניים והוניים) עם שדות כלליים כמו:
    - Product Name, Managing Company, Type, Accumulated Balance, Monthly Deposit, Management Fee, Status.
  - total_balance (float): סך הצבירה בכלל המוצרים.
  - total_monthly_deposit (float): סך ההפקדות החודשיות.
  - count (int): מספר המוצרים.
- שימושים מומלצים לסוכן:
  - כשלקוח שואל על "סיכום התיק" – אילו מוצרים יש לו ומה הסכומים.
  - כבסיס להסברים לפני כניסה לתרחישי פרישה.

---

## CALCULATE_TAX_EXEMPT_PENSION

- שם כלי ל‑LLM: CALCULATE_TAX_EXEMPT_PENSION
- פונקציה: AgentToolsService.calculate_tax_exempt_pension
- קלט:
  - current_tax_exempt_grant_amount (float): סכום מענק חד‑פעמי פטור ממס (למשל מענק פרישה) שבוחנים.
- פלט עיקרי ב‑result:
  - initial_exempt_pension (float): קצבה פטורה חודשית לפני משיכת המענק.
  - final_exempt_pension (float): קצבה פטורה חודשית אחרי משיכת המענק.
  - exempt_grant_used (float): גובה המענק שנבחן.
  - monthly_pension_loss (float): כמה קצבה פטורה חודשית תאבד בעקבות משיכת המענק (לכל החיים).
  - total_capital_offset (float): כמה הון פטור "נשרף" לצורך המענק (לפי נוסחת הקיזוז).
  - remaining_exempt_capital (float): הון פטור שנשאר לאחר המענק.
  - scenarios_text (dict): טקסטים מוכנים לשני תרחישים (לפני/אחרי משיכת מענק) לשימוש הסוכן.
- שימושים מומלצים לסוכן:
  - כשלקוח מתלבט אם למשוך מענק פטור או להשאיר פטור לקצבה.
  - להסביר ללקוח בצורה אינטואיטיבית "כמה קצבה פטורה לכל החיים אתה מקריב בשביל מענק חד‑פעמי".

---

## הערות כלליות להמשך

- ייתכן שקיימים כלים נוספים ב‑AgentToolsService או בכל שכבת השירותים שיוחשפו לסוכן בעתיד.
- בכל פעם שנוסיף כלי חדש לסוכן או נרחיב פונקציה קיימת, יש:
  - לעדכן כאן את שם הכלי, הקלט, הפלט ושימושי ההמלצה.
  - לוודא שה‑system messages וה‑playbooks מתייחסים אליו באופן עקבי.
