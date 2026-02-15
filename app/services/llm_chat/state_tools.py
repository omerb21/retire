import json

from sqlalchemy.orm import Session

from ...models import PensionFund, CapitalAsset, Scenario


def _get_snapshot_portfolio_count(client_id: int, db: Session) -> int:
    snapshot = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )

    if snapshot is None or not snapshot.parameters:
        return 0

    try:
        params = json.loads(snapshot.parameters)
    except Exception:
        return 0

    portfolio = params.get("pension_portfolio")
    return len(portfolio) if isinstance(portfolio, list) else 0


def get_agent_state_json(client_id: int, db: Session) -> str:
    pension_count = db.query(PensionFund).filter(PensionFund.client_id == client_id).count()
    capital_count = db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).count()
    snapshot_count = _get_snapshot_portfolio_count(client_id=client_id, db=db)
    has_portfolio = (pension_count + capital_count) > 0 or snapshot_count > 0

    scenarios_count = db.query(Scenario).filter(Scenario.client_id == client_id).count()

    state = {
        "maslaka_loaded": has_portfolio,
        "pension_plan_calculated": scenarios_count > 0,
        "rights_fixation_done": False,
        "current_target_pension": None,
        "products_count": pension_count + capital_count + snapshot_count,
        "maslaka_accounts_count": snapshot_count,
    }
    return json.dumps(state, indent=2)


def get_tools_definitions_json() -> str:
    tools = [
        {
            "name": "GET_SYSTEM_STATE_SNAPSHOT",
            "description": "מחזיר snapshot מלא של כל הנתונים הקיימים בפועל במערכת עבור הלקוח (DB) כולל קצבאות, היוונים, הכנסות נוספות, נכסי הון, מענקים, מעסיק נוכחי/עזיבת עבודה, קיבוע זכויות, ותרחישים/תוצאות. חובה להשתמש בכלי זה כאשר המשתמש שואל 'מה יש במערכת' או מבקש פירוט מצב בפועל, במקום לנחש או להסתמך על טבלת מוצרים בלבד.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "GET_CLIENT_SNAPSHOT",
            "description": "מחזיר snapshot info עבור הלקוח דרך /api/v1/clients/{client_id}/snapshot/info. מציג כמה קצבאות, נכסי הון, הכנסות נוספות, מענקים, האם יש מעסיק נוכחי, עזיבת עבודה, וקיבוע זכויות. השתמש בכלי זה כאשר הלקוח שואל 'מה יש לי במערכת', 'תראה לי סיכום', 'כמה מוצרים יש לי'. כאשר המשתמש מבקש 'רק JSON' או 'בלי הסברים' — החזר פלט JSON בלבד ללא טקסט נוסף.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "GET_FIXATION_STATUS_SNAPSHOT",
            "description": "מחזיר סטטוס מכני (yes/no/unknown) של קיבוע זכויות והמסמכים/אירועים הנלווים כפי שהם קיימים בפועל במערכת (DB), כולל רשימת חוסרים. הכלי לא מבצע חישובים ולא מחזיר מספרים.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "GET_SYSTEM_NUMERIC_CONSTANTS",
            "description": "מחזיר קבועים מספריים מאושרים מהמערכת (למשל MINIMUM_PENSION) לצורך שימוש בטקסט/הסבר בלי לבצע חישוב עצמאי ובלי להמציא מספרים.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "BUILD_TARGET_PENSION_PLAN",
            "description": "כלי לתכנון מתווה משיכה אופטימלי מכל המקורות להשגת יעד קצבה חודשי נטו.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_monthly_pension": {
                        "type": "integer",
                        "description": "יעד הקצבה החודשי המבוקש בשקלים (למשל: 20000)",
                    }
                    ,
                    "target_is_net": {
                        "type": "boolean",
                        "description": "האם היעד שניתן הוא נטו (אחרי מס הכנסה). true=נטו, false=ברוטו. אם המשתמש כתב במפורש 'נטו' חובה לשלוח true.",
                    },
                    "retirement_age": {
                        "type": "integer",
                        "description": "אופציונלי: גיל פרישה לחישוב (50-80). אם לא סופק, הכלי ישתמש בגיל חוקי/נוכחי לפי הלקוח.",
                    }
                },
                "required": ["target_monthly_pension"],
            },
        },
        {
            "name": "GET_TAX_PROJECTION",
            "description": "כלי לחישוב הערכת מס מפורטת על קצבה חודשית ברוטו.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gross_monthly_pension": {
                        "type": "integer",
                        "description": "סכום הקצבה החודשית ברוטו עליה יש לחשב מס",
                    }
                },
                "required": ["gross_monthly_pension"],
            },
        },
        {
            "name": "GET_TAX_PARAMS",
            "description": "מחזיר פרמטרי מס (מדרגות, תקרות, CPI וכו') לשימוש בחישובי מס והצגה.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tax_year": {
                        "type": "integer",
                        "description": "שנת מס (אופציונלי). אם לא סופק - השנה הנוכחית.",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "GET_PENSION_PRODUCTS",
            "description": "Retrieves a detailed list of all pension products and capital assets in the client's portfolio, including balances and types.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "CHECK_DATA_COMPLETENESS",
            "description": "Checks whether the client has all required data for retirement planning (portfolio, scenarios, fixation results, employer details, and missing fields).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "CALCULATE_TAX_EXEMPT_PENSION",
            "description": "Calculates the tax-exempt monthly pension benefit (קיבוע זכויות), including a simulation of how the client's current severance pay exemption impacts the final exempt pension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_tax_exempt_grant_amount": {
                        "type": "integer",
                        "description": "The amount of tax-exempt grant (severance) the client considers taking now.",
                    }
                },
                "required": ["current_tax_exempt_grant_amount"],
            },
        },
        {
            "name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            "description": "כלי מרכזי לניתוח תזרים פרישה. מחשב קצבה ברוטו, מס הכנסה, קצבה נטו, ופטור מקיבוע זכויות. השתמש בכלי זה כאשר הלקוח שואל 'כמה אקבל נטו', 'אחרי מס', 'פטור מקסימלי' או 'קיבוע זכויות'. דוגמה: ###TOOL_CALL### {\"name\": \"RUN_RETIREMENT_CASHFLOW_ANALYSIS\", \"arguments\": {\"retirement_date\": \"2028-01-01\", \"apply_max_exemption\": true}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "retirement_date": {
                        "type": "string",
                        "description": "תאריך פרישה בפורמט YYYY-MM-DD. אם הלקוח נתן רק שנה (למשל 2028), השתמש ב-01-01 של אותה שנה.",
                    },
                    "desired_monthly_income": {
                        "type": "integer",
                        "description": "יעד הכנסה חודשית נטו בשקלים (אופציונלי, ברירת מחדל: 70% מהשכר).",
                    },
                    "apply_max_exemption": {
                        "type": "boolean",
                        "description": "הפעל פטור מקסימלי מקיבוע זכויות. חובה להפעיל (true) כאשר הלקוח מבקש 'פטור מקסימלי' או 'קיבוע זכויות'.",
                    },
                },
                "required": ["retirement_date"],
            },
        },
        {
            "name": "RUN_RETIREMENT_SCENARIOS",
            "description": "כלי להרצת 3 תרחישי פרישה (מקסימום קצבה / מקסימום הון / מקסימום NPV) ולשמירתם במערכת. מחזיר מזהי תרחישים וסיכום (קצבה/הון/NPV) לכל תרחיש.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retirement_age": {
                        "type": "integer",
                        "description": "גיל פרישה לחישוב (50-80).",
                    },
                    "include_current_employer_termination": {
                        "type": "boolean",
                        "description": "האם לכלול סימולציה של עזיבת עבודה (מעסיק נוכחי) כחלק מבניית התרחישים. ברירת מחדל: false.",
                    },
                },
                "required": ["retirement_age"],
            },
        },
        {
            "name": "SELECT_TARGET_PENSION_SCENARIO",
            "description": "כלי לבחירת תרחיש אופטימלי מבין תרחישים שמורים כדי להגיע ליעד קצבה. אם יש כמה שמגיעים ליעד - נבחר זה עם NPV הכי גבוה. אם אין שמגיעים - נבחר זה עם הקצבה הגבוהה ביותר.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_monthly_pension": {
                        "type": "number",
                        "description": "יעד קצבה חודשי בשקלים.",
                    },
                    "retirement_age": {
                        "type": "integer",
                        "description": "אופציונלי: לסנן תרחישים לגיל פרישה מסוים.",
                    },
                },
                "required": ["target_monthly_pension"],
            },
        },
        {
            "name": "FIND_OPTIMAL_SCENARIO",
            "description": "כלי שמריץ תרחישים למספר גילי פרישה ובוחר את התרחיש האופטימלי להשגת יעד קצבה. מחזיר גם ניתוח רגישות (קצבה לפי גיל פרישה).",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_monthly_pension": {
                        "type": "number",
                        "description": "יעד קצבה חודשי בשקלים.",
                    },
                    "min_retirement_age": {
                        "type": "integer",
                        "description": "אופציונלי: גיל פרישה מינימלי לבדיקה.",
                    },
                    "max_retirement_age": {
                        "type": "integer",
                        "description": "אופציונלי: גיל פרישה מקסימלי לבדיקה.",
                    },
                },
                "required": ["target_monthly_pension"],
            },
        },
        {
            "name": "EXECUTE_RETIREMENT_SCENARIO",
            "description": "🔴 כלי ביצוע (Execution Tool) - מבצע בפועל תרחיש פרישה שמור לפי scenario_id. כולל ניקוי תוצאות ישנות, סימולציית עזיבת עבודה (אם מוגדר בתרחיש), וקיבוע זכויות אוטומטי.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "integer",
                        "description": "מזהה תרחיש שמור לביצוע.",
                    }
                },
                "required": ["scenario_id"],
            },
        },
        {
            "name": "CALCULATE_PENSION_COMMUTATION",
            "description": "כלי לחישוב היוון קצבה - המרת חלק מהקצבה החודשית לסכום חד-פעמי (Lump Sum). השתמש בכלי זה כאשר הלקוח שואל 'כמה כסף אקבל אם אוותר על X שקל מהקצבה', 'היוון קצבה', 'לקבל סכום חד-פעמי במקום קצבה'. דוגמה: ###TOOL_CALL### {\"name\": \"CALCULATE_PENSION_COMMUTATION\", \"arguments\": {\"target_monthly_pension_reduction\": 2000, \"retirement_date\": \"2028-01-01\"}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_monthly_pension_reduction": {
                        "type": "number",
                        "description": "הסכום החודשי שהלקוח מוכן להפחית מהקצבה העתידית (ברוטו) בתמורה לסכום חד-פעמי.",
                    },
                    "retirement_date": {
                        "type": "string",
                        "description": "תאריך פרישה בפורמט YYYY-MM-DD.",
                    },
                },
                "required": ["target_monthly_pension_reduction", "retirement_date"],
            },
        },
        {
            "name": "EXECUTE_PENSION_COMMUTATION",
            "description": "🔴 כלי ביצוע (Execution Tool) - ביצוע היוון קצבה בפועל: יצירת נכס הון מסוג 'היוון' (asset_type=deposits) עם הערת COMMUTATION, והפחתת היתרה/קצבה במקור הקצבה (PensionFund). השתמש בכלי זה רק כאשר המשתמש מאשר לבצע היוון קיים במערכת, כולל בחירת קצבה ספציפית, סכום ותאריך. דוגמה: ###TOOL_CALL### {\"name\": \"EXECUTE_PENSION_COMMUTATION\", \"arguments\": {\"pension_fund_id\": 12, \"commutation_amount\": 50000, \"commutation_date\": \"2025-01-01\", \"commutation_type\": \"exempt\", \"confirmed\": true}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "pension_fund_id": {
                        "type": "integer",
                        "description": "מזהה מקור הקצבה (PensionFund) שממנו מבוצע ההיוון.",
                    },
                    "commutation_amount": {
                        "type": "number",
                        "description": "סכום ההיוון (ברוטו) בשקלים.",
                    },
                    "commutation_date": {
                        "type": "string",
                        "description": "תאריך ההיוון בפורמט YYYY-MM-DD.",
                    },
                    "commutation_type": {
                        "type": "string",
                        "enum": ["exempt", "taxable"],
                        "description": "יחס מס לנכס ההיוון: exempt (פטור) או taxable (חייב). אם הקצבה פטורה ממס, ניתן לבחור רק exempt.",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "האם המשתמש אישר את הביצוע. חובה להיות true.",
                    },
                },
                "required": [
                    "pension_fund_id",
                    "commutation_amount",
                    "commutation_date",
                    "commutation_type",
                    "confirmed",
                ],
            },
        },
        {
            "name": "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
            "description": "כלי לחישוב מס על משיכת כספי הון (קופת גמל, קרן השתלמות, תגמולים נזילים). השתמש בכלי זה כאשר הלקוח שואל 'כמה מס אשלם אם אמשוך X שקל מהקופה', 'משיכה מקופת גמל', 'משיכה מקרן השתלמות', 'כמה נשאר לי נטו אחרי משיכה'. דוגמה: ###TOOL_CALL### {\"name\": \"CALCULATE_CAPITAL_WITHDRAWAL_TAX\", \"arguments\": {\"withdrawal_amount_gross\": 100000, \"withdrawal_year\": 2025}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "withdrawal_amount_gross": {
                        "type": "number",
                        "description": "סכום המשיכה ברוטו מכספי ההון.",
                    },
                    "withdrawal_year": {
                        "type": "integer",
                        "description": "שנת המשיכה המתוכננת (לקביעת מדרגות המס). ברירת מחדל: 2025.",
                    },
                },
                "required": ["withdrawal_amount_gross"],
            },
        },
        {
            "name": "CALCULATE_TAX_SPREAD_BENEFIT",
            "description": "כלי לחישוב הטבת המס בפריסה על מספר שנים. משווה בין משיכה מיידית (מס מלא) לבין פריסת מס. השתמש בכלי זה לאחר CALCULATE_CAPITAL_WITHDRAWAL_TAX כדי להציג ללקוח את האפשרות לחסוך במס באמצעות פריסה. דוגמה: ###TOOL_CALL### {\"name\": \"CALCULATE_TAX_SPREAD_BENEFIT\", \"arguments\": {\"gross_amount\": 735000, \"spread_years\": 6}}",
            "parameters": {
                "type": "object",
                "properties": {
                    "gross_amount": {
                        "type": "number",
                        "description": "סכום ברוטו חייב במס (החלק החייב של הפיצויים).",
                    },
                    "spread_years": {
                        "type": "integer",
                        "description": "מספר שנות פריסה (1-6). מקסימום 6 שנים לפי החוק.",
                    },
                },
                "required": ["gross_amount", "spread_years"],
            },
        },
        {
            "name": "PROCESS_TERMINATION",
            "description": "🔴 כלי ביצוע (Execution Tool) - עזיבת עבודה/פיצויים בלבד. חוק: הסוכן שולח רק confirmed + exempt_choice + taxable_choice (ואופציונלי use_employer_completion=true). הסוכן לא שולח סכומים. השרת משלים את termination_date והסכומים ממסך המעסיק הנוכחי / חישוב פיצויים קיים. השתמש בכלי זה **רק** כאשר ההקשר הוא עזיבת עבודה והלקוח מאשר לבצע החלטה על פיצויים (משיכה / רצף קצבה / פיצול). אם ההקשר הוא קיבוע זכויות/היוון/פריסת מס/אישור פטור – השתמש ב-SUBMIT_TAX_COMMUTATION ולא בכלי זה.",
            "parameters": {
                "type": "object",
                "properties": {
                    "use_employer_completion": {
                        "type": "boolean",
                        "description": "האם תבוצע השלמת מעסיק (ברירת מחדל: true).",
                    },
                    "exempt_choice": {
                        "type": "string",
                        "enum": ["redeem_with_exemption", "redeem_no_exemption", "annuity"],
                        "description": "בחירה לחלק הפטור: redeem_with_exemption (משיכה עם פטור), redeem_no_exemption (משיכה ללא פטור), annuity (רצף קצבה).",
                    },
                    "taxable_choice": {
                        "type": "string",
                        "enum": ["redeem_no_exemption", "annuity", "split"],
                        "description": "בחירה לחלק החייב: redeem_no_exemption (משיכה עם פריסת מס), annuity (רצף קצבה), split (פיצול - השתמש ב-taxable_annuity_amount ו-taxable_capital_amount).",
                    },
                    "taxable_annuity_amount": {
                        "type": "number",
                        "description": "D4.1: סכום מדויק מתוך היתרה החייבת שיועבר לרצף קצבה. רלוונטי כאשר taxable_choice=split או כאשר רוצים לפצל את הסכום החייב.",
                    },
                    "taxable_capital_amount": {
                        "type": "number",
                        "description": "D4.1: סכום מדויק מתוך היתרה החייבת שיועבר למענק הוני (כפוף למס/פריסה). רלוונטי כאשר taxable_choice=split או כאשר רוצים לפצל את הסכום החייב.",
                    },
                    "tax_spread_years": {
                        "type": "integer",
                        "description": "מספר שנות פריסת מס (1-6). רלוונטי רק אם taxable_choice = redeem_no_exemption או אם יש taxable_capital_amount.",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "האם הלקוח אישר את הפעולה. חובה להיות true לביצוע.",
                    },
                    "plan_details": {
                        "type": "string",
                        "description": "JSON של פרטי התכניות הפנסיוניות שמהן נלקחים הפיצויים. כל תכנית כוללת: plan_name (שם התכנית), plan_start_date (תאריך התחלה), product_type (סוג מוצר: קרן פנסיה/ביטוח מנהלים/קופת גמל), amount (סכום). אם לא מועבר, המערכת תנסה לבנות אוטומטית מהפורטפוליו.",
                    },
                },
                "required": [
                    "exempt_choice",
                    "taxable_choice",
                    "confirmed",
                ],
            },
        },
        {
            "name": "PROJECT_TOTAL_ANNUITY",
            "description": "D10.1: כלי להקרנת קצבה חודשית כוללת מכל המוצרים בפורטפוליו. מחשב כמה קצבה חודשית הלקוח יקבל בפרישה מכל קרנות הפנסיה, ביטוחי המנהלים וקופות הגמל. השתמש בכלי זה כאשר הלקוח שואל 'כמה קצבה אקבל', 'מה הפנסיה שלי', 'כמה אקבל בפרישה'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retirement_age": {
                        "type": "integer",
                        "description": "גיל פרישה (ברירת מחדל: 67). אם הלקוח ציין גיל אחר, השתמש בו.",
                    },
                    "retirement_date": {
                        "type": "string",
                        "description": "תאריך פרישה בפורמט YYYY-MM-DD (אופציונלי). אם לא מסופק, יחושב לפי גיל הפרישה.",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "GET_ACCOUNT_DETAILS",
            "description": "D11.1: כלי לשליפת פרטים מלאים על חשבון פנסיה ספציפי. השתמש בכלי זה כאשר הלקוח שואל על מוצר ספציפי, כגון 'מה הסטטוס של הראל', 'פרטים על מקפת', 'כמה יש לי במיטב'. מחזיר יתרה, סוג מוצר, שם חברה, פיצויים צבורים, ואם המוצר ברצף זכויות.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "מחרוזת חיפוש - שם קרן, שם חברה, או חלק משם המוצר. לדוגמה: 'הראל', 'מקפת', 'מיטב', 'ביטוח מנהלים'.",
                    }
                },
                "required": ["search_term"],
            },
        },
        {
            "name": "SUBMIT_TAX_COMMUTATION",
            "description": "🔴 כלי ביצוע (Execution Tool) - קיבוע זכויות/היוון קצבה/פריסת מס/אישור פטור בלבד (לא עזיבת עבודה). מפעיל Workflow אוטומטי לביצוע סופי לאחר שהלקוח אישר תוצאות חישוב תיאורטי (מ-CALCULATE_PENSION_COMMUTATION, GET_TAX_PROJECTION, או CALCULATE_TAX_SPREAD_BENEFIT). טריגרים לדוגמה: 'בצע קיבוע', 'אשר את הפטור', 'הגש לרשות המיסים', 'סיים את התהליך', 'אני מאשר'. אם ההקשר הוא עזיבת עבודה/פיצויים (משיכה/רצף קצבה/פיצול) – השתמש ב-PROCESS_TERMINATION. שדה client_id הוא אופציונלי (נלקח מהבקשה/הקשר).",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "integer",
                        "description": "מזהה הלקוח במערכת.",
                    },
                    "commutation_type": {
                        "type": "string",
                        "enum": ["היוון קצבה", "פטור על פיצויים", "פריסת מס", "קיבוע זכויות"],
                        "description": "סוג הקיבוע/אישור המס המבוצע.",
                    },
                    "tax_projection_id": {
                        "type": "string",
                        "description": "מזהה ייחודי המקשר את הביצוע לתוצאת חישוב המס התיאורטי שבוצע קודם לכן.",
                    },
                    "final_net_amount": {
                        "type": "number",
                        "description": "הסכום נטו הסופי שאושר ללקוח (לצורך תיעוד).",
                    },
                    "distribution_schedule": {
                        "type": "string",
                        "description": "אם סוג הקיבוע הוא פריסת מס, יש לציין את משך הפריסה (לדוגמה: '6 שנים'). אופציונלי.",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "האם הלקוח אישר את הפעולה. חובה להיות true לביצוע.",
                    },
                },
                "required": ["commutation_type", "tax_projection_id", "final_net_amount", "confirmed"],
            },
        },
        {
            "name": "GENERATE_FULL_REPORT",
            "description": "📄 כלי להצגת דוח פרישה מלא בממשק. ברירת מחדל: פתיחת עמוד התוצאות (HTML) בדיוק כמו משתמש אנושי (/clients/:id/reports) והפעלת דוח ה-HTML. אופציונלי: ניתן לבקש גם הפקת PDF ע\"י output_format=pdf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "enum": ["retirement_plan", "tax_analysis", "cashflow", "full"],
                        "description": "סוג הדוח: retirement_plan (תכנית פרישה), tax_analysis (ניתוח מס), cashflow (תזרים), full (דוח מלא).",
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["html", "pdf"],
                        "description": "פלט: html (ברירת מחדל - פתיחת דוח HTML בממשק) או pdf (יצירת קובץ PDF להורדה).",
                    },
                    "include_charts": {
                        "type": "boolean",
                        "description": "האם לכלול גרפים בדוח. ברירת מחדל: true.",
                    },
                    "retirement_date": {
                        "type": "string",
                        "description": "תאריך פרישה בפורמט YYYY-MM-DD לצורך הבטחת ניתוח עדכני לפני הפקת הדוח. אם לא נשלח, המערכת תנסה להשתמש בתאריך פרישה חוקי מתוך נתוני הלקוח.",
                    },
                    "ensure_analysis": {
                        "type": "boolean",
                        "description": "האם לוודא שניתוח פרישה (RUN_RETIREMENT_CASHFLOW_ANALYSIS) בוצע לפני הפקת הדוח. ברירת מחדל: true.",
                    },
                },
                "required": ["report_type"],
            },
        },
        {
            "name": "GENERATE_TAX_DEDUCTION_DOCUMENTS",
            "description": "📄 כלי להפקת מסמכי קיבוע זכויות ואישורי מס בפורמט PDF. השתמש בכלי זה כאשר הלקוח מבקש מסמכי קיבוע זכויות, אישורי פטור, או טפסי מס. טריגרים: 'מסמכי קיבוע', 'אישור פטור', 'טופס 161', 'מסמכים לרשות המיסים'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "enum": ["kibua_zechuyot", "ptor_pitzuim", "form_161", "tax_spread"],
                        "description": "סוג המסמך: kibua_zechuyot (קיבוע זכויות), ptor_pitzuim (פטור פיצויים), form_161 (טופס 161), tax_spread (פריסת מס).",
                    },
                },
                "required": ["document_type"],
            },
        },
        # ===== OPERATION TOOLS - Data Input & Transformation =====
        {
            "name": "TRANSFORM_FUNDS_TO_ASSETS",
            "description": "🔄 כלי תפעול להמרת כספים גלובליים (מטבלת מוצרים/מסלקה) לנכסי קצבה והון ספציפיים. השתמש בכלי זה כאשר הלקוח מבקש להמיר חשבונות פנסיוניים לנכסים במערכת. טריגרים: 'המר את הכספים', 'צור נכסים מהמסלקה', 'העבר לנכסים'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pension_start_date": {
                        "type": "string",
                        "description": "תאריך מימוש/תחילת קצבה בפורמט ISO (YYYY-MM-DD). אם מסופק ותאריך עתידי, המערכת תבצע projection ליתרות ותחשב מקדמים לפי הגיל בפועל בתאריך זה (כמו בכפתורי המערכת).",
                    },
                    "accounts": {
                        "type": "array",
                        "description": "רשימת חשבונות להמרה. מומלץ להעביר גם מזהים ותאריכים כדי לאפשר מניעת כפילויות וחישוב מקדמי קצבה מדויקים.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "account_name": {
                                    "type": "string",
                                    "description": "שם התכנית/החשבון (למשל: 'כלל תמר').",
                                },
                                "balance": {
                                    "type": "number",
                                    "description": "יתרה נוכחית (₪).",
                                },
                                "product_type": {
                                    "type": "string",
                                    "description": "סוג מוצר (למשל: 'קופת גמל', 'קרן פנסיה', 'ביטוח מנהלים').",
                                },
                                "company": {
                                    "type": "string",
                                    "description": "חברה מנהלת (אם קיימת).",
                                },
                                "account_number": {
                                    "type": "string",
                                    "description": "מספר חשבון/תיק ניכויים לזיהוי חד-חד ערכי (מומלץ מאוד לאידמפוטנטיות).",
                                },
                                "start_date": {
                                    "type": "string",
                                    "description": "תאריך התחלת תכנית בפורמט ISO (YYYY-MM-DD). משמש לזיהוי דור פוליסה/מקדמים.",
                                },
                                "pension_start_date": {
                                    "type": "string",
                                    "description": "תאריך מימוש/תחילת קצבה בפורמט ISO (YYYY-MM-DD). אם מסופק, יעקוף את pension_start_date הכללי עבור חשבון זה.",
                                },
                                "conversion_type": {
                                    "type": "string",
                                    "enum": ["pension", "capital_asset"],
                                    "description": "סוג המרה מפורש (pension/capital_asset). אם לא נשלח, המערכת תנסה לסווג אוטומטית.",
                                },
                                "שם_תכנית": {"type": "string"},
                                "יתרה": {"type": "number"},
                                "סוג_מוצר": {"type": "string"},
                                "חברה_מנהלת": {"type": "string"},
                                "מספר_חשבון": {"type": "string"},
                                "תאריך_התחלה": {"type": "string"},
                                "תאריך_מימוש": {"type": "string"},
                            },
                            "required": ["balance"],
                        },
                    },
                    "default_conversion_type": {
                        "type": "string",
                        "enum": ["pension", "capital_asset"],
                        "description": "סוג המרה ברירת מחדל: pension (קצבה) או capital_asset (נכס הון). ברירת מחדל: pension.",
                    },
                    "commute_pension_components": {
                        "type": "boolean",
                        "description": "כאשר ברירת המחדל היא המרה להון, האם לבצע היוון (COMMUTATION) לרכיבים קצבתיים שאינם ניתנים למשיכה כהון במקום להמיר אותם לנכס קצבה.",
                    },
                    "ignore_blocked_balances": {
                        "type": "boolean",
                        "description": "האם להתעלם מיתרות חסומות (פיצויים שלא עברו התחשבנות / רצף זכויות / פיצויי מעסיק נוכחי) ולהמיר רק רכיבים שמותרים להמרה. ברירת מחדל: false.",
                    },
                    "skip_non_convertible_accounts": {
                        "type": "boolean",
                        "description": "האם לדלג על חשבונות שלא ניתנים להמרה (למשל ללא פירוט רכיבים עבור נכס הון) במקום להחזיר שגיאת ולידציה. ברירת מחדל: false.",
                    },
                },
                "required": ["accounts"],
            },
        },
        {
            "name": "CREATE_TAX_EXEMPT_GRANT",
            "description": "🎁 כלי תפעול ליצירת מענק פטור ממס ממעסיק קודם. השתמש בכלי זה כאשר הלקוח מדווח על מענק פיצויים פטור שקיבל בעבר. טריגרים: 'קיבלתי פיצויים פטורים', 'מענק ממעסיק קודם', 'הוסף מענק פטור'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employer_name": {
                        "type": "string",
                        "description": "שם המעסיק שממנו התקבל המענק.",
                    },
                    "grant_amount": {
                        "type": "number",
                        "description": "סכום המענק בשקלים.",
                    },
                    "work_start_date": {
                        "type": "string",
                        "description": "תאריך תחילת עבודה אצל המעסיק (YYYY-MM-DD).",
                    },
                    "work_end_date": {
                        "type": "string",
                        "description": "תאריך סיום עבודה אצל המעסיק (YYYY-MM-DD).",
                    },
                    "grant_date": {
                        "type": "string",
                        "description": "תאריך קבלת המענק (YYYY-MM-DD). אם לא צוין, ישמש תאריך סיום העבודה.",
                    },
                },
                "required": ["employer_name", "grant_amount", "work_start_date", "work_end_date"],
            },
        },
        {
            "name": "CREATE_ADDITIONAL_INCOME",
            "description": "💰 כלי תפעול ליצירת הכנסה נוספת (שכירות, דיבידנדים, פנסיה מחו\"ל וכו'). השתמש בכלי זה כאשר הלקוח מדווח על הכנסות נוספות מעבר לקצבה. טריגרים: 'יש לי הכנסה משכירות', 'מקבל דיבידנדים', 'הכנסה נוספת', 'פנסיה מחו\"ל'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_type": {
                        "type": "string",
                        "enum": ["rental", "dividends", "interest", "foreign_pension", "social_security", "other"],
                        "description": "סוג מקור ההכנסה: rental (שכירות), dividends (דיבידנדים), interest (ריבית), foreign_pension (פנסיה מחו\"ל), social_security (ביטוח לאומי), other (אחר).",
                    },
                    "amount": {
                        "type": "number",
                        "description": "סכום ההכנסה.",
                    },
                    "frequency": {
                        "type": "string",
                        "enum": ["monthly", "quarterly", "annual", "one_time"],
                        "description": "תדירות התשלום: monthly (חודשי), quarterly (רבעוני), annual (שנתי), one_time (חד פעמי).",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "תאריך תחילת ההכנסה (YYYY-MM-DD).",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "תאריך סיום ההכנסה (YYYY-MM-DD). אופציונלי - אם לא צוין, ההכנסה נחשבת כמתמשכת.",
                    },
                    "tax_treatment": {
                        "type": "string",
                        "enum": ["taxable", "exempt", "fixed_rate"],
                        "description": "יחס מס: taxable (חייב במס שולי), exempt (פטור), fixed_rate (שיעור קבוע).",
                    },
                    "tax_rate": {
                        "type": "number",
                        "description": "שיעור מס קבוע (0-100). רלוונטי רק אם tax_treatment=fixed_rate.",
                    },
                    "description": {
                        "type": "string",
                        "description": "תיאור ההכנסה (אופציונלי).",
                    },
                },
                "required": ["source_type", "amount", "frequency", "start_date"],
            },
        },
        {
            "name": "CREATE_INDIVIDUAL_ASSET",
            "description": "🏦 כלי תפעול ליצירת נכס קצבה או הון באופן עצמאי (ללא המרה מהמסלקה). השתמש בכלי זה כאשר הלקוח רוצה להוסיף נכס ידנית. טריגרים: 'הוסף קרן פנסיה', 'יש לי ביטוח מנהלים', 'הוסף נכס הון', 'קופת גמל'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_category": {
                        "type": "string",
                        "enum": ["pension", "capital"],
                        "description": "קטגוריית הנכס: pension (קצבה - קרן פנסיה/ביטוח מנהלים) או capital (הון - קופת גמל/חיסכון).",
                    },
                    "asset_name": {
                        "type": "string",
                        "description": "שם הנכס (למשל: 'מקפת אישית', 'הראל פנסיה').",
                    },
                    "asset_type": {
                        "type": "string",
                        "description": "סוג הנכס: לקצבה - 'קרן פנסיה', 'ביטוח מנהלים', 'קופת גמל'. להון - 'provident_fund', 'savings', 'severance'.",
                    },
                    "balance": {
                        "type": "number",
                        "description": "יתרה/ערך נוכחי בשקלים.",
                    },
                    "monthly_amount": {
                        "type": "number",
                        "description": "סכום חודשי (לקצבה) או הכנסה חודשית (להון). אופציונלי.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "תאריך תחילה (YYYY-MM-DD).",
                    },
                    "tax_treatment": {
                        "type": "string",
                        "enum": ["taxable", "exempt", "capital_gains", "tax_spread"],
                        "description": "יחס מס: taxable (חייב), exempt (פטור), capital_gains (רווח הון), tax_spread (פריסת מס).",
                    },
                    "annuity_factor": {
                        "type": "number",
                        "description": "מקדם קצבה (רלוונטי לנכסי קצבה). אם לא צוין, יחושב אוטומטית.",
                    },
                },
                "required": ["asset_category", "asset_name", "balance", "start_date"],
            },
        },
        # ===== OPERATION TOOLS - Process Tools =====
        {
            "name": "SET_CURRENT_EMPLOYER_DETAILS",
            "description": "👔 כלי תפעול להזנת/עדכון פרטי המעסיק הנוכחי. השתמש בכלי זה כאשר הלקוח מספק פרטים על מקום עבודתו הנוכחי. טריגרים: 'אני עובד ב...', 'השכר שלי הוא...', 'התחלתי לעבוד ב...', 'עדכן פרטי מעסיק'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employer_name": {
                        "type": "string",
                        "description": "שם המעסיק.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "תאריך תחילת עבודה (YYYY-MM-DD).",
                    },
                    "last_salary": {
                        "type": "number",
                        "description": "שכר אחרון/נוכחי בשקלים.",
                    },
                    "severance_accrued": {
                        "type": "number",
                        "description": "פיצויים שנצברו בשקלים. אופציונלי.",
                    },
                    "expected_retirement_date": {
                        "type": "string",
                        "description": "תאריך פרישה צפוי (YYYY-MM-DD). אופציונלי.",
                    },
                    "employer_id_number": {
                        "type": "string",
                        "description": "מספר ח.פ./עוסק של המעסיק. אופציונלי.",
                    },
                },
                "required": ["employer_name", "start_date", "last_salary"],
            },
        },
        {
            "name": "EXECUTE_WORK_TERMINATION",
            "description": "🚪 כלי תפעול לביצוע תהליך עזיבת עבודה בפועל. שונה מ-PROCESS_TERMINATION שמטפל בהחלטות פיצויים - כלי זה מבצע את הפעולה הטכנית של סיום העסקה במערכת. טריגרים: 'עזבתי את העבודה', 'פוטרתי', 'התפטרתי', 'סיימתי לעבוד'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termination_date": {
                        "type": "string",
                        "description": "תאריך סיום העבודה (YYYY-MM-DD).",
                    },
                    "termination_reason": {
                        "type": "string",
                        "enum": ["resignation", "layoff", "retirement", "other"],
                        "description": "סיבת סיום: resignation (התפטרות), layoff (פיטורים), retirement (פרישה), other (אחר).",
                    },
                    "final_salary": {
                        "type": "number",
                        "description": "שכר אחרון (אם שונה מהשכר הרשום). אופציונלי.",
                    },
                    "calculate_severance": {
                        "type": "boolean",
                        "description": "האם לחשב פיצויים אוטומטית. ברירת מחדל: true.",
                    },
                },
                "required": ["termination_date", "termination_reason"],
            },
        },
        {
            "name": "CALCULATE_FIXATION_OF_RIGHTS",
            "description": "📋 כלי תפעול לחישוב קיבוע זכויות (פטור על קצבה). מבצע את החישוב המלא של הפטור המגיע ללקוח על בסיס המענקים הפטורים שקיבל בעבר. טריגרים: 'חשב קיבוע זכויות', 'כמה פטור מגיע לי', 'חישוב פטור על קצבה'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_current_employer": {
                        "type": "boolean",
                        "description": "האם לכלול את המעסיק הנוכחי בחישוב. ברירת מחדל: false.",
                    },
                    "save_result": {
                        "type": "boolean",
                        "description": "האם לשמור את תוצאת החישוב במערכת. ברירת מחדל: true.",
                    },
                },
                "required": [],
            },
        },
    ]
    return json.dumps(tools, indent=2, ensure_ascii=False)
