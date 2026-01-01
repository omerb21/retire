"""
LLM Agent Tools Service
שירות כלים לסוכן ה-LLM - מאפשר לסוכן להפעיל לוגיקות מערכת

כל כלי מחזיר מבנה אחיד:
{
    "success": bool,
    "tool_name": str,
    "result": dict,  # תוצאות הכלי
    "explanation": str,  # הסבר קצר לסוכן
}
"""
import json
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.scenario import Scenario
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.current_employment import CurrentEmployer
from app.services.retirement import RetirementScenariosBuilder
from app.services.retirement.constants import PENSION_COEFFICIENT, MINIMUM_PENSION
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.tax_calculator import TaxCalculator
from app.schemas.tax_schemas import TaxCalculationInput, PersonalDetails
from app.services.rights_fixation.exemption_caps import get_monthly_cap, get_exemption_percentage
from app.services.commutation_service import CommutationService
from app.services.capital_withdrawal_service import CapitalWithdrawalService
from datetime import date, datetime
from decimal import Decimal
from app.utils.date_serializer import parse_date_flexible
from app.services.pension_portfolio.conversion_rules import (
    COMPONENT_RULES,
    rule_for_tagmulim_by_product_type,
)

logger = logging.getLogger("app.llm_agent_tools")


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return _to_jsonable(dumped)
    dict_dump = getattr(value, "dict", None)
    if callable(dict_dump):
        dumped = dict_dump()
        return _to_jsonable(dumped)

    raw = getattr(value, "__dict__", None)
    if isinstance(raw, dict):
        return _to_jsonable(raw)

    return str(value)


class AgentToolsService:
    """שירות כלים לסוכן ה-LLM"""

    def __init__(self, db: Session, client_id: int, client_object: Optional[Client] = None, pension_portfolio_data: Optional[List[Any]] = None):
        self.db = db
        self.client_id = client_id
        self._client: Optional[Client] = client_object
        self.pension_portfolio_data = pension_portfolio_data

    @property
    def client(self) -> Optional[Client]:
        if self._client is None:
            self._client = self.db.query(Client).filter(
                Client.id == self.client_id
            ).first()
        return self._client

    def check_data_completeness(self) -> Dict[str, Any]:
        """בודק אם כל הנתונים הנדרשים לחישוב תרחישים קיימים"""
        missing_fields: List[str] = []
        warnings: List[str] = []

        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CHECK_DATA_COMPLETENESS",
                "result": {"complete": False, "missing": ["לקוח לא נמצא"]},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        # בדיקות נתונים קריטיים
        recommendations: list[str] = []
        
        if not client.birth_date:
            missing_fields.append("תאריך לידה")
            recommendations.append("הזן תאריך לידה בפרטי הלקוח")
        if not client.gender:
            missing_fields.append("מגדר")
            recommendations.append("הזן מגדר בפרטי הלקוח (משפיע על מקדמי קצבה)")
        if not client.annual_salary:
            warnings.append("לא הוגדר שכר שנתי")
            recommendations.append("הזן שכר שנתי לחישוב יעד קצבה מומלץ")

        # בדיקת קיום מוצרים פנסיוניים
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()

        if not pension_funds:
            warnings.append("לא נמצאו מוצרים פנסיוניים")
            recommendations.append("העלה תיק פנסיוני (קובץ XML מהמסלקה)")
        else:
            # בדיקה שיש יתרות/מקדמים
            funds_with_balance = [pf for pf in pension_funds if pf.balance and pf.balance > 0]
            funds_with_pension = [pf for pf in pension_funds if pf.pension_amount and pf.pension_amount > 0]
            if not funds_with_balance and not funds_with_pension:
                warnings.append("המוצרים הפנסיוניים ללא יתרות או קצבות")
                recommendations.append("וודא שהתיק הפנסיוני מכיל יתרות")

        # בדיקת תרחישים קיימים
        scenarios_count = self.db.query(Scenario).filter(
            Scenario.client_id == self.client_id
        ).count()
        
        if scenarios_count == 0:
            warnings.append("לא נמצאו תרחישי פרישה")
            recommendations.append("הרץ תרחישי פרישה לגיל הרצוי")

        # בדיקת קיבוע זכויות
        from app.models.fixation_result import FixationResult
        fixation_exists = self.db.query(FixationResult).filter(
            FixationResult.client_id == self.client_id
        ).first() is not None
        
        if not fixation_exists:
            warnings.append("לא בוצע קיבוע זכויות")
            recommendations.append("בצע קיבוע זכויות לחישוב פטור ממס")

        # בדיקת מעסיק נוכחי
        from app.models.current_employment.employer import CurrentEmployer
        employers_count = self.db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == self.client_id
        ).count()
        
        if employers_count == 0:
            warnings.append("לא הוגדר מעסיק נוכחי")
            recommendations.append("הזן פרטי מעסיק נוכחי לחישוב פיצויים")

        is_complete = len(missing_fields) == 0
        
        # בניית הסבר מפורט
        explanation_parts: list[str] = []
        
        if is_complete and not warnings:
            explanation_parts.append("✅ **כל הנתונים הנדרשים קיימים!**")
            explanation_parts.append("")
            explanation_parts.append("ניתן להמשיך בחישוב תרחישים ובניית תכניות פרישה.")
            explanation_parts.append(f"נמצאו {len(pension_funds)} מוצרים פנסיוניים ו-{scenarios_count} תרחישים שמורים.")
        elif is_complete and warnings:
            explanation_parts.append("⚠️ **הנתונים הבסיסיים קיימים, אך יש התראות:**")
            explanation_parts.append("")
            for w in warnings:
                explanation_parts.append(f"  • {w}")
            if recommendations:
                explanation_parts.append("")
                explanation_parts.append("**💡 המלצות:**")
                for r in recommendations[:3]:
                    explanation_parts.append(f"  • {r}")
        else:
            explanation_parts.append("❌ **חסרים נתונים קריטיים:**")
            explanation_parts.append("")
            for m in missing_fields:
                explanation_parts.append(f"  • {m}")
            if warnings:
                explanation_parts.append("")
                explanation_parts.append("**התראות נוספות:**")
                for w in warnings:
                    explanation_parts.append(f"  • {w}")
            explanation_parts.append("")
            explanation_parts.append("**💡 מה לעשות:**")
            for r in recommendations[:5]:
                explanation_parts.append(f"  • {r}")
        
        explanation = "\n".join(explanation_parts)

        return {
            "success": True,
            "tool_name": "CHECK_DATA_COMPLETENESS",
            "result": {
                "complete": is_complete,
                "missing": missing_fields,
                "warnings": warnings,
                "recommendations": recommendations,
                "pension_funds_count": len(pension_funds),
                "scenarios_count": scenarios_count,
                "fixation_exists": fixation_exists,
                "employers_count": employers_count,
            },
            "explanation": explanation,
        }

    def get_saved_scenarios_summary(self, retirement_age: Optional[int] = None) -> Dict[str, Any]:
        """מחזיר סיכום של התרחישים השמורים"""
        query = self.db.query(Scenario).filter(Scenario.client_id == self.client_id)

        if retirement_age:
            query = query.filter(
                Scenario.parameters.like(f'%"retirement_age": {retirement_age}%')
            )

        scenarios = query.order_by(Scenario.created_at.desc()).all()

        if not scenarios:
            return {
                "success": True,
                "tool_name": "GET_SAVED_SCENARIOS",
                "result": {"scenarios": [], "count": 0},
                "explanation": "לא נמצאו תרחישים שמורים ללקוח זה. יש להפיק תרחישים תחילה.",
            }

        scenarios_list = []
        for scenario in scenarios:
            try:
                params = json.loads(scenario.parameters) if scenario.parameters else {}
                summary = json.loads(scenario.summary_results) if scenario.summary_results else {}
                
                scenarios_list.append({
                    "scenario_id": scenario.id,
                    "scenario_name": summary.get("scenario_name", scenario.scenario_name),
                    "retirement_age": params.get("retirement_age"),
                    "total_pension_monthly": summary.get("total_pension_monthly", 0),
                    "total_capital": summary.get("total_capital", 0),
                    "estimated_npv": summary.get("estimated_npv", 0),
                })
            except Exception as e:
                logger.warning(f"Failed to parse scenario {scenario.id}: {e}")

        return {
            "success": True,
            "tool_name": "GET_SAVED_SCENARIOS",
            "result": {"scenarios": scenarios_list, "count": len(scenarios_list)},
            "explanation": f"נמצאו {len(scenarios_list)} תרחישים שמורים.",
        }

    def select_optimal_scenario_for_target_pension(
        self,
        target_monthly_pension: float,
        retirement_age: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        בוחר את התרחיש האופטימלי מבין התרחישים השמורים:
        - מסנן תרחישים שמגיעים ליעד הקצבה
        - מתוכם בוחר את זה עם ה-NPV הגבוה ביותר
        - אם אף תרחיש לא מגיע ליעד, בוחר את זה עם הקצבה הגבוהה ביותר
        """
        # שליפת התרחישים
        scenarios_result = self.get_saved_scenarios_summary(retirement_age)
        scenarios = scenarios_result["result"].get("scenarios", [])

        if not scenarios:
            return {
                "success": False,
                "tool_name": "SELECT_TARGET_PENSION_SCENARIO",
                "result": {
                    "target_achieved": False,
                    "selected_scenario": None,
                    "reason": "no_scenarios",
                },
                "explanation": (
                    f"לא נמצאו תרחישים שמורים. "
                    f"יש להפיק תרחישים תחילה באמצעות ACTION: RUN_RETIREMENT_SCENARIOS."
                ),
            }

        # סינון תרחישים שמגיעים ליעד
        target = float(target_monthly_pension)
        achieving_target = [
            s for s in scenarios
            if s.get("total_pension_monthly", 0) >= target
        ]

        # בניית הסבר מפורט
        explanation_parts: list[str] = []
        
        if achieving_target:
            # בוחרים את התרחיש עם ה-NPV הגבוה ביותר מבין אלו שמגיעים ליעד
            best = max(achieving_target, key=lambda s: s.get("estimated_npv", 0))
            
            explanation_parts.append(f"✅ **נמצא תרחיש שמגיע ליעד של {target:,.0f} ₪/חודש!**")
            explanation_parts.append("")
            explanation_parts.append("**🎯 התרחיש הנבחר:**")
            explanation_parts.append(f"  • שם: {best['scenario_name']}")
            explanation_parts.append(f"  • קצבה: {best['total_pension_monthly']:,.0f} ₪/חודש")
            explanation_parts.append(f"  • הון: {best.get('total_capital', 0):,.0f} ₪")
            explanation_parts.append(f"  • NPV: {best['estimated_npv']:,.0f} ₪")
            
            if len(achieving_target) > 1:
                explanation_parts.append("")
                explanation_parts.append(f"**📊 אלטרנטיבות ({len(achieving_target) - 1} נוספות):**")
                for alt in achieving_target:
                    if alt != best:
                        explanation_parts.append(
                            f"  • {alt['scenario_name']}: {alt['total_pension_monthly']:,.0f} ₪/חודש"
                        )
            
            # יתרונות וחסרונות
            explanation_parts.append("")
            explanation_parts.append("**💡 למה התרחיש הזה?**")
            explanation_parts.append("  • NPV הגבוה ביותר = ערך כלכלי מקסימלי")
            if best.get('total_capital', 0) > 0:
                explanation_parts.append(f"  • נשאר הון של {best.get('total_capital', 0):,.0f} ₪ לגמישות")
            
            return {
                "success": True,
                "tool_name": "SELECT_TARGET_PENSION_SCENARIO",
                "result": {
                    "target_achieved": True,
                    "target_monthly_pension": target,
                    "selected_scenario": best,
                    "alternatives_count": len(achieving_target) - 1,
                    "all_achieving": achieving_target,
                },
                "explanation": "\n".join(explanation_parts),
            }
        else:
            # אף תרחיש לא מגיע ליעד - בוחרים את זה עם הקצבה הגבוהה ביותר
            best = max(scenarios, key=lambda s: s.get("total_pension_monthly", 0))
            max_pension = best.get("total_pension_monthly", 0)
            gap = target - max_pension
            gap_pct = (gap / target * 100) if target > 0 else 0

            explanation_parts.append(f"❌ **לא נמצא תרחיש שמגיע ליעד של {target:,.0f} ₪/חודש**")
            explanation_parts.append("")
            explanation_parts.append("**📊 התרחיש הטוב ביותר:**")
            explanation_parts.append(f"  • שם: {best['scenario_name']}")
            explanation_parts.append(f"  • קצבה: {max_pension:,.0f} ₪/חודש")
            explanation_parts.append(f"  • פער מהיעד: {gap:,.0f} ₪/חודש ({gap_pct:.0f}%)")
            
            explanation_parts.append("")
            explanation_parts.append("**💡 איך לגשר על הפער?**")
            explanation_parts.append("  • דחיית גיל פרישה - כל שנה מגדילה את הקצבה")
            explanation_parts.append("  • הגדלת הפקדות שוטפות")
            explanation_parts.append("  • שקול להוריד את היעד ליעד ריאלי יותר")
            
            # בדוק אם יש תרחיש קרוב ליעד
            closest = min(scenarios, key=lambda s: abs(s.get("total_pension_monthly", 0) - target))
            if closest != best:
                explanation_parts.append("")
                explanation_parts.append(f"**🔍 תרחיש קרוב ליעד:** {closest['scenario_name']} ({closest['total_pension_monthly']:,.0f} ₪)")

            return {
                "success": True,
                "tool_name": "SELECT_TARGET_PENSION_SCENARIO",
                "result": {
                    "target_achieved": False,
                    "target_monthly_pension": target,
                    "selected_scenario": best,
                    "gap_to_target": gap,
                    "gap_percentage": gap_pct,
                },
                "explanation": "\n".join(explanation_parts),
            }

    def run_retirement_scenarios(
        self,
        retirement_age: int,
        pension_portfolio: Optional[List[Dict]] = None,
        include_current_employer_termination: bool = False,
    ) -> Dict[str, Any]:
        """
        מריץ את שלושת תרחישי הפרישה ושומר אותם במערכת.
        """
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_SCENARIOS",
                "result": {},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        # וולידציה
        current_age = client.get_age() if client.birth_date else None
        if current_age and retirement_age < current_age:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_SCENARIOS",
                "result": {},
                "explanation": f"גיל הפרישה ({retirement_age}) לא יכול להיות נמוך מהגיל הנוכחי ({current_age}).",
            }

        if retirement_age < 50 or retirement_age > 80:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_SCENARIOS",
                "result": {},
                "explanation": "גיל הפרישה חייב להיות בין 50 ל-80.",
            }

        try:
            pension_portfolio_serialized = (
                _to_jsonable(pension_portfolio) if pension_portfolio is not None else None
            )
            if pension_portfolio_serialized is not None and not isinstance(
                pension_portfolio_serialized, list
            ):
                pension_portfolio_serialized = None

            builder = RetirementScenariosBuilder(
                self.db,
                self.client_id,
                retirement_age,
                pension_portfolio_serialized,
                include_current_employer_termination,
            )
            scenarios = builder.build_all_scenarios()

            # שמירת התרחישים
            saved_ids = {}
            for scenario_key, scenario_data in scenarios.items():
                # מחיקת תרחישים קודמים
                self.db.query(Scenario).filter(
                    Scenario.client_id == self.client_id,
                    Scenario.scenario_name == scenario_data["scenario_name"],
                    Scenario.parameters.like(f'%"retirement_age": {retirement_age}%')
                ).delete(synchronize_session=False)

                new_scenario = Scenario(
                    client_id=self.client_id,
                    scenario_name=scenario_data["scenario_name"],
                    parameters=json.dumps({
                        "retirement_age": retirement_age,
                        "scenario_type": scenario_key,
                        "pension_portfolio": pension_portfolio_serialized,
                        "include_current_employer_termination": include_current_employer_termination,
                    }, ensure_ascii=False),
                    summary_results=json.dumps(scenario_data, ensure_ascii=False),
                )
                self.db.add(new_scenario)
                self.db.flush()
                saved_ids[scenario_key] = new_scenario.id

            self.db.commit()

            # בניית סיכום
            summary = []
            for key, data in scenarios.items():
                summary.append({
                    "scenario_id": saved_ids[key],
                    "scenario_key": key,
                    "scenario_name": data.get("scenario_name"),
                    "total_pension_monthly": data.get("total_pension_monthly", 0),
                    "total_capital": data.get("total_capital", 0),
                    "estimated_npv": data.get("estimated_npv", 0),
                })

            # חילוץ נתונים לסיכום
            max_pension_scenario = scenarios.get("scenario_1_max_pension", {})
            max_capital_scenario = scenarios.get("scenario_2_max_capital", {})
            max_npv_scenario = scenarios.get("scenario_3_max_npv", {})
            
            max_pension = max_pension_scenario.get("total_pension_monthly", 0)
            max_capital = max_capital_scenario.get("total_capital", 0)
            max_npv = max_npv_scenario.get("estimated_npv", 0)
            
            # בניית הסבר מפורט
            explanation_parts: list[str] = []
            explanation_parts.append(f"🎯 **תרחישי פרישה לגיל {retirement_age}**")
            explanation_parts.append("")
            
            # תרחיש 1 - קצבה מקסימלית
            explanation_parts.append(f"**1. {max_pension_scenario.get('scenario_name', 'קצבה מקסימלית')}** [ממקסם קצבה]")
            explanation_parts.append(f"   • קצבה: {max_pension:,.0f} ₪/חודש")
            explanation_parts.append(f"   • הון: {max_pension_scenario.get('total_capital', 0):,.0f} ₪")
            explanation_parts.append(f"   • מתאים ל: מי שרוצה הכנסה קבועה ויציבה לכל החיים")
            explanation_parts.append("")
            
            # תרחיש 2 - הון מקסימלי
            explanation_parts.append(f"**2. {max_capital_scenario.get('scenario_name', 'הון מקסימלי')}** [ממקסם הון]")
            explanation_parts.append(f"   • קצבה: {max_capital_scenario.get('total_pension_monthly', 0):,.0f} ₪/חודש")
            explanation_parts.append(f"   • הון: {max_capital:,.0f} ₪")
            explanation_parts.append(f"   • מתאים ל: מי שרוצה גמישות, הון לילדים, או הכנסות נוספות")
            explanation_parts.append("")
            
            # תרחיש 3 - NPV מקסימלי
            explanation_parts.append(f"**3. {max_npv_scenario.get('scenario_name', 'NPV מקסימלי')}** [ממקסם ערך נוכחי]")
            explanation_parts.append(f"   • קצבה: {max_npv_scenario.get('total_pension_monthly', 0):,.0f} ₪/חודש")
            explanation_parts.append(f"   • הון: {max_npv_scenario.get('total_capital', 0):,.0f} ₪")
            explanation_parts.append(f"   • NPV: {max_npv:,.0f} ₪")
            explanation_parts.append(f"   • מתאים ל: איזון אופטימלי בין קצבה להון")
            explanation_parts.append("")
            
            # המלצה
            explanation_parts.append("**💡 המלצה:**")
            if max_pension > 20000:
                explanation_parts.append(f"   הקצבה המקסימלית ({max_pension:,.0f} ₪) גבוהה - אפשר לשקול להשאיר חלק כהון.")
            elif max_pension < 10000:
                explanation_parts.append(f"   הקצבה המקסימלית ({max_pension:,.0f} ₪) נמוכה יחסית - שקול לדחות את הפרישה.")
            else:
                explanation_parts.append(f"   התרחישים מציגים טווח סביר. בחר לפי הצרכים האישיים שלך.")
            
            explanation = "\n".join(explanation_parts)

            return {
                "success": True,
                "tool_name": "RUN_RETIREMENT_SCENARIOS",
                "result": {
                    "retirement_age": retirement_age,
                    "scenarios": summary,
                    "max_pension": max_pension,
                    "max_capital": max_capital,
                    "max_npv": max_npv,
                },
                "explanation": explanation,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error running scenarios: {e}", exc_info=True)
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_SCENARIOS",
                "result": {},
                "explanation": f"שגיאה בהפקת התרחישים: {str(e)}",
            }

    def find_optimal_scenario_for_target(
        self,
        target_monthly_pension: float,
        min_retirement_age: Optional[int] = None,
        max_retirement_age: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        מחפש את התרחיש האופטימלי להשגת יעד קצבה מסוים.
        מריץ תרחישים לכמה גילי פרישה ובוחר את הטוב ביותר.
        """
        client = self.client
        if not client or not client.birth_date:
            return {
                "success": False,
                "tool_name": "FIND_OPTIMAL_SCENARIO",
                "result": {},
                "explanation": "חסרים נתוני לקוח (תאריך לידה) לחישוב.",
            }

        current_age = client.get_age()
        if current_age is None:
            return {
                "success": False,
                "tool_name": "FIND_OPTIMAL_SCENARIO",
                "result": {},
                "explanation": "לא ניתן לחשב את גיל הלקוח.",
            }

        # הגדרת טווח גילי פרישה לבדיקה
        min_age = max(min_retirement_age or current_age, current_age, 50)
        max_age = min(max_retirement_age or 75, 80)

        if min_age > max_age:
            return {
                "success": False,
                "tool_name": "FIND_OPTIMAL_SCENARIO",
                "result": {},
                "explanation": f"טווח גילים לא תקין: {min_age}-{max_age}.",
            }

        # נבחר כמה נקודות בטווח (לא להריץ כל גיל)
        ages_to_check = []
        if max_age - min_age <= 5:
            ages_to_check = list(range(min_age, max_age + 1))
        else:
            # בודקים כל 2-3 שנים
            step = max(1, (max_age - min_age) // 5)
            ages_to_check = list(range(min_age, max_age + 1, step))
            if max_age not in ages_to_check:
                ages_to_check.append(max_age)

        target = float(target_monthly_pension)
        all_results = []
        best_achieving = None
        best_overall = None

        for age in ages_to_check:
            result = self.run_retirement_scenarios(age)
            if not result["success"]:
                continue

            for scenario in result["result"].get("scenarios", []):
                scenario["retirement_age"] = age
                all_results.append(scenario)

                pension = scenario.get("total_pension_monthly", 0)
                npv = scenario.get("estimated_npv", 0)

                if pension >= target:
                    if best_achieving is None or npv > best_achieving.get("estimated_npv", 0):
                        best_achieving = scenario

                if best_overall is None or pension > best_overall.get("total_pension_monthly", 0):
                    best_overall = scenario

        if not all_results:
            return {
                "success": False,
                "tool_name": "FIND_OPTIMAL_SCENARIO",
                "result": {},
                "explanation": "לא הצלחתי להריץ תרחישים לאף גיל פרישה.",
            }

        # ניתוח רגישות - איך הקצבה משתנה לפי גיל פרישה
        sensitivity_analysis: list[dict] = []
        results_by_age: dict[int, dict] = {}
        for res in all_results:
            age = res.get("retirement_age")
            pension = res.get("total_pension_monthly", 0)
            if age not in results_by_age or pension > results_by_age[age].get("total_pension_monthly", 0):
                results_by_age[age] = res
        
        sorted_ages = sorted(results_by_age.keys())
        for i, age in enumerate(sorted_ages):
            res = results_by_age[age]
            pension = res.get("total_pension_monthly", 0)
            capital = res.get("total_capital", 0)
            
            # חישוב שינוי מהגיל הקודם
            change_from_prev = 0
            if i > 0:
                prev_age = sorted_ages[i-1]
                prev_pension = results_by_age[prev_age].get("total_pension_monthly", 0)
                change_from_prev = pension - prev_pension
            
            sensitivity_analysis.append({
                "age": age,
                "pension": pension,
                "capital": capital,
                "change_from_prev": change_from_prev,
                "meets_target": pension >= target,
            })

        # בניית הסבר מפורט
        explanation_parts: list[str] = []
        
        if best_achieving:
            explanation_parts.append(
                f"✅ **נמצא תרחיש שמגיע ליעד של {target:,.0f} ₪/חודש!**"
            )
            explanation_parts.append("")
            explanation_parts.append(f"**🎯 התרחיש המומלץ:**")
            explanation_parts.append(
                f"  • גיל פרישה: {best_achieving['retirement_age']}"
            )
            explanation_parts.append(
                f"  • תרחיש: {best_achieving['scenario_name']}"
            )
            explanation_parts.append(
                f"  • קצבה: {best_achieving['total_pension_monthly']:,.0f} ₪/חודש"
            )
            explanation_parts.append(
                f"  • הון: {best_achieving.get('total_capital', 0):,.0f} ₪"
            )
            explanation_parts.append(
                f"  • NPV: {best_achieving['estimated_npv']:,.0f} ₪"
            )
        else:
            gap = target - best_overall.get("total_pension_monthly", 0)
            explanation_parts.append(
                f"❌ **לא נמצא תרחיש שמגיע ליעד של {target:,.0f} ₪/חודש**"
            )
            explanation_parts.append("")
            explanation_parts.append(f"**📊 התרחיש הטוב ביותר:**")
            explanation_parts.append(
                f"  • גיל פרישה: {best_overall['retirement_age']}"
            )
            explanation_parts.append(
                f"  • קצבה: {best_overall['total_pension_monthly']:,.0f} ₪/חודש"
            )
            explanation_parts.append(
                f"  • פער מהיעד: {gap:,.0f} ₪/חודש ({(gap/target*100):.0f}%)"
            )
        
        # ניתוח רגישות
        explanation_parts.append("")
        explanation_parts.append("**📈 ניתוח רגישות - קצבה לפי גיל פרישה:**")
        for item in sensitivity_analysis:
            marker = "✓" if item["meets_target"] else "✗"
            change_text = ""
            if item["change_from_prev"] != 0:
                sign = "+" if item["change_from_prev"] > 0 else ""
                change_text = f" ({sign}{item['change_from_prev']:,.0f})"
            explanation_parts.append(
                f"  {marker} גיל {item['age']}: {item['pension']:,.0f} ₪{change_text}"
            )
        
        # המלצות
        explanation_parts.append("")
        explanation_parts.append("**💡 המלצות:**")
        
        if best_achieving:
            # בדוק אם יש גיל מוקדם יותר שגם מגיע ליעד
            earliest_achieving = None
            for item in sensitivity_analysis:
                if item["meets_target"]:
                    if earliest_achieving is None or item["age"] < earliest_achieving["age"]:
                        earliest_achieving = item
            
            if earliest_achieving and earliest_achieving["age"] < best_achieving["retirement_age"]:
                explanation_parts.append(
                    f"  • אפשר לפרוש כבר בגיל {earliest_achieving['age']} ולהגיע ליעד ({earliest_achieving['pension']:,.0f} ₪)"
                )
            
            # בדוק אם דחייה נותנת יותר
            if len(sensitivity_analysis) > 1:
                last_item = sensitivity_analysis[-1]
                if last_item["pension"] > best_achieving["total_pension_monthly"]:
                    explanation_parts.append(
                        f"  • דחייה לגיל {last_item['age']} תיתן קצבה גבוהה יותר ({last_item['pension']:,.0f} ₪)"
                    )
        else:
            # לא מגיעים ליעד - תן המלצות
            explanation_parts.append(
                f"  • שקול להוריד את היעד ל-{best_overall['total_pension_monthly']:,.0f} ₪/חודש"
            )
            if len(sensitivity_analysis) > 0:
                last_item = sensitivity_analysis[-1]
                if last_item["age"] < 75:
                    explanation_parts.append(
                        f"  • דחיית פרישה מעבר לגיל {last_item['age']} עשויה לשפר את הקצבה"
                    )
            explanation_parts.append(
                f"  • הגדלת ההפקדות השוטפות תקטין את הפער"
            )
        
        explanation = "\n".join(explanation_parts)
        
        result_data = {
            "target_monthly_pension": target,
            "selected_scenario": best_achieving or best_overall,
            "target_achieved": best_achieving is not None,
            "ages_checked": ages_to_check,
            "total_scenarios_evaluated": len(all_results),
            "sensitivity_analysis": sensitivity_analysis,
        }
        
        if not best_achieving:
            result_data["gap_to_target"] = target - best_overall.get("total_pension_monthly", 0)
        
        return {
            "success": True,
            "tool_name": "FIND_OPTIMAL_SCENARIO",
            "result": result_data,
            "explanation": explanation,
        }

    def _get_pension_sources_from_portfolio(
        self,
        pension_portfolio: List[Dict[str, Any]],
        client: Client,
        retirement_age: int,
        retirement_date: date,
        retirement_year: int,
    ) -> List[Dict[str, Any]]:
        pension_sources: List[Dict[str, Any]] = []

        termination_confirmed = False
        try:
            current_employer = (
                self.db.query(CurrentEmployer)
                .filter(CurrentEmployer.client_id == self.client_id)
                .order_by(CurrentEmployer.id.desc())
                .first()
            )
            if current_employer is not None:
                other_grants = current_employer.other_grants or {}
                if isinstance(other_grants, dict):
                    termination_confirmed = bool(other_grants.get("termination_confirmed"))
        except Exception:
            termination_confirmed = False

        def _as_dict(raw: Any) -> Dict[str, Any]:
            if raw is None:
                return {}
            if isinstance(raw, dict):
                return raw
            if hasattr(raw, "model_dump"):
                try:
                    dumped = raw.model_dump()
                    return dumped if isinstance(dumped, dict) else {}
                except Exception:
                    return {}
            try:
                return vars(raw)
            except Exception:
                return {}

        def _safe_float(value: Any) -> float:
            try:
                if value is None:
                    return 0.0
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    cleaned = value.replace(",", "").replace("₪", "").strip()
                    if not cleaned:
                        return 0.0
                    return float(cleaned)
                return float(value)
            except Exception:
                return 0.0

        components: list[dict[str, Any]] = [
            {
                "field": "פיצויים_מעסיק_נוכחי",
                "label": "פיצויים מעסיק נוכחי",
                "tax_treatment": "taxable",
                "priority_bucket": 2,
                "action_needed": "requires_termination",
            },
            {
                "field": "פיצויים_לאחר_התחשבנות",
                "label": "פיצויים לאחר התחשבנות",
                "tax_treatment": "exempt",
                "priority_bucket": 1,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
                "label": "פיצויים (מעסיקים קודמים - רצף קצבה)",
                "tax_treatment": "taxable",
                "priority_bucket": 1,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "תגמולי_עובד_עד_2000",
                "label": "תגמולי עובד עד 2000",
                "tax_treatment": "taxable",
                "priority_bucket": 3,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "תגמולי_מעביד_עד_2000",
                "label": "תגמולי מעביד עד 2000",
                "tax_treatment": "taxable",
                "priority_bucket": 3,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "תגמולי_עובד_אחרי_2000",
                "label": "תגמולי עובד אחרי 2000",
                "tax_treatment": "taxable",
                "priority_bucket": 4,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "תגמולי_מעביד_אחרי_2000",
                "label": "תגמולי מעביד אחרי 2000",
                "tax_treatment": "taxable",
                "priority_bucket": 4,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "תגמולי_עובד_אחרי_2008_לא_משלמת",
                "label": "תגמולי עובד אחרי 2008 (לא משלמת)",
                "tax_treatment": "taxable",
                "priority_bucket": 4,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "תגמולי_מעביד_אחרי_2008_לא_משלמת",
                "label": "תגמולי מעביד אחרי 2008 (לא משלמת)",
                "tax_treatment": "taxable",
                "priority_bucket": 4,
                "action_needed": "convert_to_pension",
            },
            {
                "field": "קרן_השתלמות",
                "label": "קרן השתלמות",
                "tax_treatment": "exempt",
                "priority_bucket": 5,
                "action_needed": "convert_to_pension",
            },
        ]

        for account in pension_portfolio:
            acc = _as_dict(account)

            product_type = acc.get("סוג_מוצר") or ""
            plan_name = acc.get("שם_תכנית", "תכנית ללא שם")
            account_number = acc.get("מספר_חשבון") or None

            start_date_raw = acc.get("תאריך_התחלה")

            annuity_factor = float(PENSION_COEFFICIENT)
            try:
                start_date_obj: Optional[date] = None
                if isinstance(start_date_raw, str) and start_date_raw:
                    try:
                        start_date_obj = parse_date_flexible(start_date_raw)
                    except Exception:
                        start_date_obj = None

                coeff = get_annuity_coefficient(
                    product_type=product_type,
                    start_date=start_date_obj or date(retirement_year, 1, 1),
                    gender=getattr(client, "gender", None) or "זכר",
                    retirement_age=(
                        int(retirement_age)
                        if retirement_age is not None
                        else int(get_retirement_age_simple(client.birth_date, client.gender or ""))
                    ),
                    company_name=acc.get("חברה_מנהלת"),
                    option_name=None,
                    survivors_option="תקנוני",
                    spouse_age_diff=0,
                    target_year=retirement_year,
                    birth_date=getattr(client, "birth_date", None),
                    pension_start_date=retirement_date or None,
                )
                annuity_factor = float(coeff.get("factor_value") or annuity_factor)
            except Exception:
                annuity_factor = float(PENSION_COEFFICIENT)

            if annuity_factor <= 0:
                annuity_factor = float(PENSION_COEFFICIENT)

            if "השתלמות" in str(product_type) or "השתלמות" in str(plan_name):
                balance = _safe_float(acc.get("יתרה", 0))
                if balance <= 0:
                    continue
                potential_pension = balance / annuity_factor
                pension_sources.append(
                    {
                        "source_type": "pension_fund_from_portfolio",
                        "source_id": account_number,
                        "account_number": account_number,
                        "component_field": "קרן_השתלמות",
                        "source_name": f"{plan_name} (קרן השתלמות)",
                        "fund_type": product_type or "unknown",
                        "start_date": start_date_raw,
                        "balance": balance,
                        "annuity_factor": annuity_factor,
                        "monthly_pension": potential_pension,
                        "tax_treatment": "exempt",
                        "priority_bucket": 5,
                        "action_needed": "convert_to_pension",
                        "action_description": f"המרת קרן השתלמות בסך {balance:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                    }
                )
                continue

            component_added = False
            skipped_requires_termination = False
            for comp in components:
                field = str(comp.get("field") or "")
                if not field:
                    continue
                amount = _safe_float(acc.get(field, 0))
                if amount <= 0:
                    continue

                action_needed = comp.get("action_needed") or "convert_to_pension"
                if action_needed == "requires_termination" and termination_confirmed:
                    skipped_requires_termination = True
                    continue
                component_added = True
                potential_pension = amount / annuity_factor
                tax_treatment = comp.get("tax_treatment") or (
                    "exempt" if ("השתלמות" in str(product_type)) else "taxable"
                )
                priority_bucket = int(comp.get("priority_bucket") or 9)
                label = str(comp.get("label") or field)

                if action_needed == "requires_termination":
                    action_description = (
                        f"נדרש לבצע עזיבת עבודה כדי להמיר {label} בסך {amount:,.0f} ₪ לקצבה"
                    )
                else:
                    action_description = (
                        f"המרת {label} בסך {amount:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש"
                    )

                pension_sources.append(
                    {
                        "source_type": "pension_fund_from_portfolio",
                        "source_id": account_number,
                        "account_number": account_number,
                        "component_field": field,
                        "source_name": f"{plan_name} ({label})",
                        "fund_type": product_type or "unknown",
                        "start_date": start_date_raw,
                        "balance": amount,
                        "annuity_factor": annuity_factor,
                        "monthly_pension": potential_pension,
                        "tax_treatment": tax_treatment,
                        "priority_bucket": priority_bucket,
                        "action_needed": action_needed,
                        "action_description": action_description,
                    }
                )

            if component_added:
                continue

            if skipped_requires_termination:
                continue

            # Fallback: אם אין רכיבים מפורטים, נשתמש ביתרה כללית בלבד
            balance = _safe_float(acc.get("יתרה", 0))
            if balance <= 0:
                continue
            potential_pension = balance / annuity_factor
            tax_treatment = "exempt" if ("השתלמות" in str(product_type)) else "taxable"
            priority_bucket = 5 if ("השתלמות" in str(product_type) or "השתלמות" in str(plan_name)) else 4
            pension_sources.append(
                {
                    "source_type": "pension_fund_from_portfolio",
                    "source_id": account_number,
                    "account_number": account_number,
                    "source_name": plan_name,
                    "fund_type": product_type or "unknown",
                    "start_date": start_date_raw,
                    "balance": balance,
                    "annuity_factor": annuity_factor,
                    "monthly_pension": potential_pension,
                    "tax_treatment": tax_treatment,
                    "priority_bucket": priority_bucket,
                    "action_needed": "convert_to_pension",
                    "action_description": f"המרת יתרה של {balance:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                }
            )

        return pension_sources

    def _build_sources_from_pension_portfolio(
        self,
        pension_portfolio: List[Dict[str, Any]],
        client: Client,
        retirement_age: int,
        retirement_date: date,
        retirement_year: int,
    ) -> List[Dict[str, Any]]:
        return self._get_pension_sources_from_portfolio(
            pension_portfolio=pension_portfolio,
            client=client,
            retirement_age=retirement_age,
            retirement_date=retirement_date,
            retirement_year=retirement_year,
        )

    def build_target_pension_plan(
        self,
        target_monthly_pension: float,
        retirement_age: Optional[int] = None,
        target_is_net: bool = True,
    ) -> Dict[str, Any]:
        """
        בונה תכנית להשגת קצבת יעד בצורה אופטימלית.
        
        האלגוריתם:
        1. אוסף את כל מקורות הקצבה הפוטנציאליים (קרנות פנסיה, נכסי הון)
        2. מדרג אותם לפי "איכות" (מקדם קצבה - הנמוך יותר = טוב יותר)
        3. ממיר בסדר מהטוב לפחות טוב עד להגעה ליעד
        4. מחזיר תכנית מפורטת עם יתרונות/חסרונות
        """
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "BUILD_TARGET_PENSION_PLAN",
                "result": {},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        if not client.birth_date:
            return {
                "success": False,
                "tool_name": "BUILD_TARGET_PENSION_PLAN",
                "result": {},
                "explanation": "חסר תאריך לידה ללקוח - לא ניתן לחשב מקדמי קצבה.",
            }

        # קביעת גיל/תאריך תחילת קצבה (ברירת מחדל: max(גיל נוכחי, גיל פרישה חוקי לפי הגדרות))
        from app.services.retirement_age_service import (
            DEFAULT_MALE_RETIREMENT_AGE,
            get_retirement_age_simple,
            get_retirement_date,
        )

        current_age = client.get_age()
        legal_retirement_age = int(DEFAULT_MALE_RETIREMENT_AGE)
        legal_retirement_date = None
        try:
            legal_retirement_age = int(
                get_retirement_age_simple(client.birth_date, client.gender or "")
            )
        except Exception:
            legal_retirement_age = int(DEFAULT_MALE_RETIREMENT_AGE)
        try:
            legal_retirement_date = get_retirement_date(client.birth_date, client.gender or "")
        except Exception:
            legal_retirement_date = None

        inferred_default_retirement_date = False
        if retirement_age is None:
            if current_age is not None:
                retirement_age = max(int(current_age), int(legal_retirement_age))
            else:
                retirement_age = int(legal_retirement_age)
            inferred_default_retirement_date = True
        
        if retirement_age < current_age:
            return {
                "success": False,
                "tool_name": "BUILD_TARGET_PENSION_PLAN",
                "result": {},
                "explanation": f"גיל הפרישה ({retirement_age}) לא יכול להיות נמוך מהגיל הנוכחי ({current_age}).",
            }

        # חישוב תאריך תחילת קצבה
        if inferred_default_retirement_date:
            # אם כבר עבר גיל פרישה (או שווה לו) – מתחילים היום; אחרת לפי תאריך הפרישה החוקי
            if current_age is not None and current_age >= legal_retirement_age:
                retirement_date = date.today()
            else:
                retirement_date = legal_retirement_date
            if retirement_date is None:
                retirement_date = date.today()
        else:
            try:
                retirement_date = date(
                    client.birth_date.year + retirement_age,
                    client.birth_date.month,
                    client.birth_date.day,
                )
            except ValueError:
                retirement_date = client.birth_date.replace(
                    year=client.birth_date.year + retirement_age,
                    day=min(client.birth_date.day, 28),
                )
            # אם המשתמש ביקש גיל נוכחי, אל תאפשר תאריך בעבר
            if current_age is not None and retirement_age == current_age and retirement_date < date.today():
                retirement_date = date.today()
        retirement_year = retirement_date.year

        target = float(target_monthly_pension)

        # שלב 1: איסוף כל מקורות הקצבה הפוטנציאליים
        pension_sources = []

        # קרנות פנסיה עם יתרות
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()

        for pf in pension_funds:
            balance = float(pf.balance or 0)
            existing_pension = float(pf.pension_amount or 0)
            
            # אם יש כבר קצבה מוגדרת - זה מקור קיים
            if existing_pension > 0:
                pension_sources.append({
                    "source_type": "existing_pension",
                    "source_id": pf.id,
                    "account_number": pf.deduction_file,
                    "source_name": pf.fund_name,
                    "fund_type": pf.fund_type,
                    "balance": 0,
                    "annuity_factor": pf.annuity_factor or PENSION_COEFFICIENT,
                    "monthly_pension": existing_pension,
                    "tax_treatment": pf.tax_treatment or "taxable",
                    "action_needed": "none",
                    "action_description": "קצבה קיימת - ללא פעולה נדרשת",
                })
                continue

            # אם יש יתרה - ניתן להמיר לקצבה
            if balance > 0:
                # חישוב מקדם קצבה דינמי
                annuity_factor = float(pf.annuity_factor or 0)
                if annuity_factor <= 0:
                    try:
                        coeff_result = get_annuity_coefficient(
                            product_type=pf.fund_type or "קרן פנסיה",
                            start_date=retirement_date,
                            gender=client.gender or "זכר",
                            retirement_age=retirement_age,
                            birth_date=client.birth_date,
                            pension_start_date=retirement_date,
                        )
                        annuity_factor = float(coeff_result.get("factor_value") or PENSION_COEFFICIENT)
                    except Exception:
                        annuity_factor = PENSION_COEFFICIENT

                potential_pension = balance / annuity_factor

                pension_sources.append({
                    "source_type": "pension_fund",
                    "source_id": pf.id,
                    "account_number": pf.deduction_file,
                    "source_name": pf.fund_name,
                    "fund_type": pf.fund_type,
                    "balance": balance,
                    "annuity_factor": annuity_factor,
                    "monthly_pension": potential_pension,
                    "tax_treatment": pf.tax_treatment or "taxable",
                    "action_needed": "convert_to_pension",
                    "action_description": f"המרת יתרה של {balance:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                })

        # נכסי הון שניתן להמיר לקצבה
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()

        for ca in capital_assets:
            value = float(ca.current_value or 0)
            if value <= 0:
                value = float(ca.monthly_income or 0)
            
            if value > 0:
                # נכסי הון ממירים במקדם כללי
                potential_pension = value / PENSION_COEFFICIENT

                pension_sources.append({
                    "source_type": "capital_asset",
                    "source_id": ca.id,
                    "account_number": None,
                    "source_name": ca.asset_name,
                    "fund_type": ca.asset_type,
                    "balance": value,
                    "annuity_factor": PENSION_COEFFICIENT,
                    "monthly_pension": potential_pension,
                    "tax_treatment": ca.tax_treatment or "taxable",
                    "action_needed": "convert_to_pension",
                    "action_description": f"המרת הון של {value:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                })

        portfolio_sources_total = 0
        portfolio_sources_added = 0
        portfolio_sources_skipped_duplicates = 0
        portfolio_sources_unique_accounts = 0
        portfolio_sources_total_balance = 0.0

        pension_portfolio_data: Any = None
        if isinstance(getattr(self, "pension_portfolio_data", None), list) and getattr(self, "pension_portfolio_data"):
            pension_portfolio_data = getattr(self, "pension_portfolio_data")
        else:
            try:
                all_scenarios = (
                    self.db.query(Scenario)
                    .filter(Scenario.client_id == self.client_id)
                    .order_by(Scenario.created_at.desc())
                    .limit(20)
                    .all()
                )
                for scenario in all_scenarios:
                    if not scenario.parameters:
                        continue
                    try:
                        params = json.loads(scenario.parameters)
                        portfolio = params.get("pension_portfolio")
                        if isinstance(portfolio, list) and portfolio:
                            pension_portfolio_data = portfolio
                            break
                    except Exception:
                        continue
            except Exception:
                pension_portfolio_data = None

        if isinstance(pension_portfolio_data, list) and pension_portfolio_data:
            portfolio_sources = self._build_sources_from_pension_portfolio(
                pension_portfolio=pension_portfolio_data,
                client=client,
                retirement_age=retirement_age,
                retirement_date=retirement_date,
                retirement_year=retirement_year,
            )
            portfolio_sources_total = len(portfolio_sources)
            try:
                portfolio_sources_total_balance = float(
                    sum(float(s.get("balance") or 0) for s in portfolio_sources if isinstance(s, dict))
                )
            except Exception:
                portfolio_sources_total_balance = 0.0

            existing_account_numbers: set[str] = set()
            for src in pension_sources:
                if not isinstance(src, dict):
                    continue
                acc = src.get("account_number")
                if isinstance(acc, str) and acc.strip():
                    existing_account_numbers.add(acc.strip())

            seen_portfolio_account_numbers: set[str] = set()
            seen_portfolio_source_keys: set[str] = set()
            filtered_portfolio_sources: list[dict] = []
            for src in portfolio_sources:
                if not isinstance(src, dict):
                    continue
                acc = src.get("account_number")
                acc_norm = acc.strip() if isinstance(acc, str) else ""
                try:
                    src_name_norm = str(src.get("source_name") or "").strip()
                except Exception:
                    src_name_norm = ""
                source_key = f"{acc_norm}::{src_name_norm}" if acc_norm else src_name_norm
                if source_key:
                    if source_key in seen_portfolio_source_keys:
                        continue
                    seen_portfolio_source_keys.add(source_key)
                if acc_norm:
                    if acc_norm in seen_portfolio_account_numbers:
                        # We still allow multiple component sources per account.
                        pass
                    seen_portfolio_account_numbers.add(acc_norm)
                    if acc_norm in existing_account_numbers:
                        portfolio_sources_skipped_duplicates += 1
                        continue
                filtered_portfolio_sources.append(src)

            portfolio_sources_unique_accounts = len(seen_portfolio_account_numbers)
            portfolio_sources_added = len(filtered_portfolio_sources)
            pension_sources.extend(filtered_portfolio_sources)

        if not pension_sources:
            return {
                "success": False,
                "tool_name": "BUILD_TARGET_PENSION_PLAN",
                "result": {},
                "explanation": (
                    "לא נמצאו מקורות קצבה (קרנות פנסיה או נכסי הון) ללקוח. "
                    "ייתכן שטרם הורץ תרחיש פרישה עם תיק פנסיוני, או שהתיק הפנסיוני לא נשמר כראוי. "
                    "אנא וודא שהעלית תיק פנסיוני והרצת תרחישי פרישה דרך המסך המיועד לכך."
                ),
            }

        def _infer_priority_bucket(source: dict[str, Any]) -> int:
            try:
                explicit = source.get("priority_bucket")
                if isinstance(explicit, (int, float)):
                    return int(explicit)
            except Exception:
                pass
            src_type = str(source.get("source_type") or "")
            fund_type = str(source.get("fund_type") or "")
            name = str(source.get("source_name") or "")
            return (
                0
                if source.get("action_needed") == "none"
                else 1
                if ("pension_fund" in src_type or "from_portfolio" in src_type)
                else 4
                if "השתלמות" in fund_type or "השתלמות" in name
                else 3
                if "גמל" in fund_type or "קופת" in fund_type or "גמל" in name
                else 2
                if "capital_asset" in src_type
                else 9
            )

        def _is_pension_only_source(source: dict[str, Any]) -> bool:
            if not isinstance(source, dict):
                return False

            src_type = str(source.get("source_type") or "")
            if src_type in {"existing_pension", "pension_fund"}:
                return True
            if src_type == "capital_asset":
                return False

            if src_type != "pension_fund_from_portfolio":
                return False

            field = str(source.get("component_field") or "").strip()
            product_type = str(source.get("fund_type") or "")
            if not field:
                return False

            if "השתלמות" in product_type or "השתלמות" in str(source.get("source_name") or ""):
                return False

            if field == "תגמולים":
                rule = rule_for_tagmulim_by_product_type(product_type=product_type)
                try:
                    can_pension = bool(rule.get("pension"))
                except Exception:
                    can_pension = True
                try:
                    can_capital = bool(rule.get("capital") or rule.get("capital_asset"))
                except Exception:
                    can_capital = False
                return can_pension and (not can_capital)

            rule = COMPONENT_RULES.get(field)
            if not isinstance(rule, dict):
                return False
            try:
                can_pension = bool(rule.get("pension"))
            except Exception:
                can_pension = True
            try:
                can_capital = bool(rule.get("capital") or rule.get("capital_asset"))
            except Exception:
                can_capital = False
            return can_pension and (not can_capital)

        def _is_hishtalmut_source(source: dict[str, Any]) -> bool:
            if not isinstance(source, dict):
                return False
            src_type = str(source.get("source_type") or "")
            if src_type != "pension_fund_from_portfolio":
                return False
            fund_type = str(source.get("fund_type") or "")
            if "השתלמות" in fund_type:
                return True
            source_name = str(source.get("source_name") or "")
            if "השתלמות" in source_name:
                return True
            component_field = str(source.get("component_field") or "")
            if component_field == "קרן_השתלמות":
                return True
            return False

        def _phase_rank(source: dict[str, Any]) -> int:
            if not isinstance(source, dict):
                return 99
            if source.get("action_needed") == "none":
                return 0
            if _is_pension_only_source(source):
                return 1
            if str(source.get("source_type") or "") == "capital_asset":
                return 3
            return 2

        # שלב 2: מיון לפי מתודולוגיה דטרמיניסטית + איכות (מקדם נמוך = טוב יותר)
        pension_sources.sort(
            key=lambda x: (
                _phase_rank(x),
                _infer_priority_bucket(x),
                float(x.get("annuity_factor") or PENSION_COEFFICIENT),
            )
        )

        # שלב 3: בניית התכנית - צבירת קצבה עד היעד
        plan_steps = []
        accumulated_pension = 0.0
        remaining_capital = 0.0
        blocked_for_execution_capital = 0.0
        sources_used = []
        sources_not_used = []

        # יעד להשגה בברוטו/נטו
        required_gross_for_target = target
        required_gross_tax_projection = None
        if target_is_net:
            def _gross_for_net_target(target_net: float) -> tuple[Optional[float], Optional[dict]]:
                try:
                    target_net_val = float(target_net or 0)
                except Exception:
                    target_net_val = 0.0
                if target_net_val <= 0:
                    return None, None

                def _net_from_gross(gross: float) -> tuple[Optional[float], Optional[dict]]:
                    try:
                        proj = self.get_tax_projection(monthly_pension=float(gross))
                        if not (isinstance(proj, dict) and isinstance(proj.get("result"), dict)):
                            return None, None
                        res = proj.get("result")
                        monthly_tax = res.get("monthly_tax")
                        try:
                            tax_val = float(monthly_tax or 0)
                        except Exception:
                            tax_val = 0.0
                        return float(gross) - tax_val, res
                    except Exception:
                        return None, None

                low = max(1000.0, target_net_val)
                low_net, low_res = _net_from_gross(low)
                if low_net is None:
                    return None, None
                if low_net >= target_net_val:
                    return low, low_res

                high = low
                high_net = low_net
                high_res: Optional[dict] = low_res
                for _ in range(16):
                    high = min(high * 1.5, 500_000.0)
                    high_net, high_res = _net_from_gross(high)
                    if high_net is not None and high_net >= target_net_val:
                        break
                if high_net is None or high_net < target_net_val:
                    return None, None

                best_gross = high
                best_res = high_res
                for _ in range(30):
                    mid = (low + high) / 2.0
                    mid_net, mid_res = _net_from_gross(mid)
                    if mid_net is None:
                        low = mid
                        continue
                    if mid_net >= target_net_val:
                        best_gross = mid
                        best_res = mid_res
                        high = mid
                    else:
                        low = mid
                    if abs(high - low) < 1.0:
                        break

                try:
                    best_gross = float(round(best_gross, 2))
                except Exception:
                    pass
                return best_gross, best_res

            computed_gross, tax_result = _gross_for_net_target(target)
            if computed_gross is not None:
                required_gross_for_target = float(computed_gross)
                required_gross_tax_projection = tax_result

        existing_sources: list[dict[str, Any]] = []
        pension_only_sources: list[dict[str, Any]] = []
        other_sources: list[dict[str, Any]] = []
        for src in pension_sources:
            if not isinstance(src, dict):
                continue
            if src.get("action_needed") == "none":
                existing_sources.append(src)
                continue
            if _is_pension_only_source(src):
                pension_only_sources.append(src)
            else:
                other_sources.append(src)

        existing_sources.sort(
            key=lambda x: (
                _infer_priority_bucket(x),
                float(x.get("annuity_factor") or PENSION_COEFFICIENT),
            )
        )
        pension_only_sources.sort(
            key=lambda x: (
                _infer_priority_bucket(x),
                float(x.get("annuity_factor") or PENSION_COEFFICIENT),
            )
        )
        other_sources.sort(
            key=lambda x: (
                _phase_rank(x),
                _infer_priority_bucket(x),
                float(x.get("annuity_factor") or PENSION_COEFFICIENT),
            )
        )

        hishtalmut_sources: list[dict[str, Any]] = []
        non_hishtalmut_other_sources: list[dict[str, Any]] = []
        for src in other_sources:
            if _is_hishtalmut_source(src):
                hishtalmut_sources.append(src)
            else:
                non_hishtalmut_other_sources.append(src)

        pension_sources = [
            *existing_sources,
            *pension_only_sources,
            *non_hishtalmut_other_sources,
            *hishtalmut_sources,
        ]

        for source in pension_sources:
            if source.get("action_needed") == "requires_termination":
                sources_not_used.append(source)
                blocked_for_execution_capital += float(source.get("balance") or 0)
                continue
            if accumulated_pension >= required_gross_for_target:
                # כבר הגענו ליעד - השאר נשאר כהון
                sources_not_used.append(source)
                remaining_capital += source["balance"]
                continue

            pension_from_source = source["monthly_pension"]
            needed = required_gross_for_target - accumulated_pension

            if pension_from_source <= needed:
                # משתמשים בכל המקור
                accumulated_pension += pension_from_source
                sources_used.append({
                    **source,
                    "pension_used": pension_from_source,
                    "balance_used": source["balance"],
                    "partial": False,
                })
                plan_steps.append({
                    "step_number": len(plan_steps) + 1,
                    "action": source["action_description"],
                    "pension_added": pension_from_source,
                    "accumulated_pension": accumulated_pension,
                    "source_name": source["source_name"],
                    "annuity_factor": source["annuity_factor"],
                })
            else:
                # משתמשים רק בחלק מהמקור
                partial_balance = needed * source["annuity_factor"]
                accumulated_pension += needed
                remaining_from_source = source["balance"] - partial_balance
                remaining_capital += remaining_from_source

                sources_used.append({
                    **source,
                    "pension_used": needed,
                    "balance_used": partial_balance,
                    "partial": True,
                    "remaining_balance": remaining_from_source,
                })
                plan_steps.append({
                    "step_number": len(plan_steps) + 1,
                    "action": f"המרה חלקית: {partial_balance:,.0f} ₪ מתוך {source['balance']:,.0f} ₪ לקצבה של {needed:,.0f} ₪/חודש",
                    "pension_added": needed,
                    "accumulated_pension": accumulated_pension,
                    "source_name": source["source_name"],
                    "annuity_factor": source["annuity_factor"],
                    "remaining_as_capital": remaining_from_source,
                })

        # חישוב סיכום
        target_achieved_gross = accumulated_pension >= required_gross_for_target
        gap = max(0, required_gross_for_target - accumulated_pension)

        # בניית יתרונות וחסרונות
        advantages = []
        disadvantages = []

        if target_achieved_gross:
            if target_is_net:
                advantages.append(f"הושג יעד ברוטו שמוערך כמספיק ל-{target:,.0f} ₪ נטו")
            else:
                advantages.append(f"היעד של {target:,.0f} ₪ לחודש הושג")
        
        if remaining_capital > 0:
            advantages.append(f"נותר הון נזיל של {remaining_capital:,.0f} ₪")

        # בדיקת איכות המקורות שנבחרו
        avg_factor = sum(s["annuity_factor"] for s in sources_used) / len(sources_used) if sources_used else 0
        if avg_factor < 180:
            advantages.append(f"מקדם קצבה ממוצע טוב ({avg_factor:.0f})")
        elif avg_factor > 200:
            disadvantages.append(f"מקדם קצבה ממוצע גבוה ({avg_factor:.0f}) - פחות יעיל")

        # בדיקת מס
        taxable_pension = sum(s["pension_used"] for s in sources_used if s["tax_treatment"] == "taxable")
        exempt_pension = sum(s["pension_used"] for s in sources_used if s["tax_treatment"] == "exempt")
        
        if exempt_pension > 0:
            advantages.append(f"{exempt_pension:,.0f} ₪ מהקצבה פטורים ממס")
        if taxable_pension > accumulated_pension * 0.7:
            disadvantages.append(f"רוב הקצבה ({taxable_pension:,.0f} ₪) חייבת במס")

        if not target_achieved_gross:
            if target_is_net:
                disadvantages.append(f"לא ניתן להגיע ליעד נטו - חסרים {gap:,.0f} ₪ ברוטו לחודש לפי ההמרה הנוכחית")
            else:
                disadvantages.append(f"לא ניתן להגיע ליעד - חסרים {gap:,.0f} ₪ לחודש")

        estimated_tax = None
        estimated_net = None
        tax_projection_result = None
        try:
            tax_proj = self.get_tax_projection(monthly_pension=accumulated_pension)
            if isinstance(tax_proj, dict) and isinstance(tax_proj.get("result"), dict):
                tax_projection_result = tax_proj.get("result")
                estimated_tax = tax_projection_result.get("monthly_tax")
                if estimated_tax is not None:
                    try:
                        estimated_net = float(accumulated_pension) - float(estimated_tax)
                    except Exception:
                        estimated_net = None
        except Exception:
            tax_projection_result = None

        # יעד נטו בפועל לפי הערכת מס - בדיקה סופית
        target_achieved_net = None
        if target_is_net and estimated_net is not None:
            try:
                target_achieved_net = float(estimated_net) >= float(target)
            except Exception:
                target_achieved_net = None

        # בניית הסבר מפורט לסוכן
        explanation_parts: list[str] = []
        
        if target_achieved_gross:
            explanation_parts.append(
                (
                    f"✅ **התכנית הושלמה בהצלחה** - ניתן להגיע לקצבה של {target:,.0f} ₪ נטו (משוער) בגיל {retirement_age}."
                    if target_is_net
                    else f"✅ **התכנית הושלמה בהצלחה** - ניתן להגיע לקצבה של {target:,.0f} ₪/חודש בגיל {retirement_age}."
                )
            )
            explanation_parts.append("")
            explanation_parts.append("**📋 צעדי התכנית:**")
            for step in plan_steps:
                explanation_parts.append(
                    f"  {step['step_number']}. {step['source_name']} (מקדם {step['annuity_factor']:.0f}): "
                    f"+{step['pension_added']:,.0f} ₪/חודש → סה\"כ {step['accumulated_pension']:,.0f} ₪"
                )
            
            if remaining_capital > 0:
                explanation_parts.append("")
                explanation_parts.append(f"💰 **הון שנותר**: {remaining_capital:,.0f} ₪ (לא הומר לקצבה)")
            
            if advantages:
                explanation_parts.append("")
                explanation_parts.append("**✅ יתרונות:**")
                for adv in advantages:
                    explanation_parts.append(f"  • {adv}")
            
            if disadvantages:
                explanation_parts.append("")
                explanation_parts.append("**⚠️ חסרונות:**")
                for dis in disadvantages:
                    explanation_parts.append(f"  • {dis}")

            if blocked_for_execution_capital > 0:
                explanation_parts.append("")
                explanation_parts.append("**🧩 מקורות שדורשים עזיבת עבודה כדי לכלול בפועל:**")
                explanation_parts.append(f"  • הון חסום לביצוע (סה\"כ): {blocked_for_execution_capital:,.0f} ₪")
            
            # המלצות נוספות
            explanation_parts.append("")
            explanation_parts.append("**💡 המלצות:**")
            if remaining_capital > 100000:
                explanation_parts.append(f"  • ההון שנותר ({remaining_capital:,.0f} ₪) יכול לשמש כרזרבה לחירום או להעברה לדור הבא.")
            if exempt_pension > 0:
                explanation_parts.append(f"  • {exempt_pension:,.0f} ₪ מהקצבה פטורים ממס - יתרון משמעותי.")
            if avg_factor > 190:
                explanation_parts.append("  • שקול לדחות את הפרישה בשנה-שנתיים לשיפור המקדם.")
        else:
            explanation_parts.append(
                (
                    f"❌ **לא ניתן להגיע ליעד** של {target:,.0f} ₪ נטו (משוער) עם המקורות הקיימים."
                    if target_is_net
                    else f"❌ **לא ניתן להגיע ליעד** של {target:,.0f} ₪/חודש עם המקורות הקיימים."
                )
            )
            explanation_parts.append("")
            explanation_parts.append(f"📊 **המצב הנוכחי:**")
            explanation_parts.append(f"  • קצבה ברוטו שנבנתה מהמקורות: {accumulated_pension:,.0f} ₪/חודש")
            if target_is_net and estimated_net is not None:
                explanation_parts.append(f"  • קצבה נטו משוערת (מס הכנסה בלבד): {float(estimated_net):,.0f} ₪/חודש")
            explanation_parts.append(f"  • פער מהיעד: {gap:,.0f} ₪/חודש")
            base = required_gross_for_target if required_gross_for_target > 0 else 1
            explanation_parts.append(f"  • אחוז מהיעד: {(accumulated_pension/base*100):.0f}%")
            
            explanation_parts.append("")
            explanation_parts.append("**💡 אפשרויות לגישור הפער:**")
            explanation_parts.append(f"  1. **דחיית פרישה**: כל שנה נוספת משפרת את המקדם ומגדילה את הצבירה.")
            explanation_parts.append(f"  2. **הגדלת חיסכון**: הפקדות נוספות עד הפרישה.")
            explanation_parts.append(f"  3. **הורדת יעד**: יעד ריאלי יותר הוא {accumulated_pension:,.0f} ₪/חודש.")
            if remaining_capital > 0:
                monthly_from_capital = remaining_capital / 240  # 20 שנות פרישה
                explanation_parts.append(
                    f"  4. **משיכה מההון**: {remaining_capital:,.0f} ₪ יכולים לתת ~{monthly_from_capital:,.0f} ₪/חודש ל-20 שנה."
                )
        
        explanation = "\n".join(explanation_parts)

        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_monthly_pension": target,
                "target_is_net": target_is_net,
                "retirement_age": retirement_age,
                "target_achieved": (target_achieved_net if target_is_net else target_achieved_gross),
                "target_achieved_gross": target_achieved_gross,
                "target_achieved_net": target_achieved_net,
                "required_gross_for_target": required_gross_for_target,
                "required_gross_tax_projection": required_gross_tax_projection,
                "accumulated_pension": accumulated_pension,
                "taxable_pension": taxable_pension,
                "exempt_pension": exempt_pension,
                "estimated_monthly_tax": estimated_tax,
                "estimated_monthly_net": estimated_net,
                "tax_projection": tax_projection_result,
                "portfolio_sources_total": portfolio_sources_total,
                "portfolio_sources_added": portfolio_sources_added,
                "portfolio_sources_skipped_duplicates": portfolio_sources_skipped_duplicates,
                "portfolio_sources_unique_accounts": portfolio_sources_unique_accounts,
                "portfolio_sources_total_balance": portfolio_sources_total_balance,
                "gap_to_target": gap,
                "remaining_capital": remaining_capital,
                "blocked_for_execution_capital": blocked_for_execution_capital,
                "plan_steps": plan_steps,
                "sources_used": sources_used,
                "sources_not_used": sources_not_used,
                "advantages": advantages,
                "disadvantages": disadvantages,
                "total_sources_available": len(pension_sources),
                "sources_used_count": len(sources_used),
            },
            "explanation": explanation,
        }

    def get_tax_projection(
        self,
        monthly_pension: Optional[float] = None,
        additional_income: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        מחשב הערכת מס על הכנסה בפרישה.
        אם לא מסופקים פרמטרים, משתמש בנתונים מהתרחישים הקיימים.
        """
        from app.services.tax_data.tax_brackets import TaxBracketsService
        from app.models.fixation_result import FixationResult
        
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "GET_TAX_PROJECTION",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }
        
        # אם לא סופקה קצבה, נסה לקחת מהתרחישים
        if monthly_pension is None:
            scenarios = self.db.query(Scenario).filter(
                Scenario.client_id == self.client_id
            ).order_by(Scenario.created_at.desc()).first()
            
            if scenarios and scenarios.summary_results:
                try:
                    summary = json.loads(scenarios.summary_results)
                    monthly_pension = summary.get("total_pension_monthly", 0)
                except Exception:
                    monthly_pension = 0
            else:
                monthly_pension = 0
        
        if additional_income is None:
            additional_income = 0

        # בדיקת סף עבור קצבה חודשית ברוטו – משמשת גם לבדיקות עמידות (Run 13)
        gross_monthly_pension = float(monthly_pension or 0)
        if gross_monthly_pension < 1000:
            raise ValueError("TAX_TOOL_ERROR: הקצבה החודשית נמוכה מ-1,000 ₪, לא ניתן לבצע הערכת מס אמינה.")
        
        # חישוב הכנסה שנתית
        annual_pension = float(monthly_pension) * 12
        annual_additional = float(additional_income) * 12
        total_annual_income = annual_pension + annual_additional
        
        if total_annual_income <= 0:
            return {
                "success": True,
                "tool_name": "GET_TAX_PROJECTION",
                "result": {"annual_tax": 0, "monthly_tax": 0},
                "explanation": "אין הכנסה לחישוב מס.",
            }
        
        # קבלת מדרגות מס
        current_year = date.today().year
        tax_brackets = TaxBracketsService.get_tax_brackets(current_year)
        
        # חישוב מס לפי מדרגות
        annual_tax = 0.0
        remaining_income = total_annual_income
        tax_breakdown: list[dict] = []
        
        for bracket in tax_brackets:
            if remaining_income <= 0:
                break
            
            bracket_min = bracket["min_income"]
            bracket_max = bracket["max_income"]
            rate = bracket["rate"]
            
            taxable_in_bracket = min(remaining_income, bracket_max - bracket_min + 1)
            if taxable_in_bracket > 0:
                tax_in_bracket = taxable_in_bracket * rate
                annual_tax += tax_in_bracket
                tax_breakdown.append({
                    "bracket": f"{bracket_min:,}-{bracket_max:,}",
                    "rate": f"{int(rate*100)}%",
                    "taxable_amount": taxable_in_bracket,
                    "tax": tax_in_bracket,
                })
                remaining_income -= taxable_in_bracket
        
        # התחשבות בפטור קצבה (אם יש קיבוע)
        fixation = self.db.query(FixationResult).filter(
            FixationResult.client_id == self.client_id
        ).order_by(FixationResult.created_at.desc()).first()
        
        exempt_pension_pct = 0.0
        if fixation and fixation.raw_result:
            try:
                fixation_data = fixation.raw_result if isinstance(fixation.raw_result, dict) else json.loads(fixation.raw_result)
                exempt_pension_pct = fixation_data.get("exemption_summary", {}).get("exempt_pension_percentage", 0)
            except Exception:
                pass
        
        # הפחתת מס בגין פטור
        if exempt_pension_pct > 0 and annual_pension > 0:
            exempt_amount = annual_pension * exempt_pension_pct
            # הערכה פשוטה - הפחתת מס יחסית
            tax_reduction = exempt_amount * 0.3  # הערכה של מס שולי ממוצע
            annual_tax = max(0, annual_tax - tax_reduction)
        
        monthly_tax = annual_tax / 12
        effective_rate = (annual_tax / total_annual_income * 100) if total_annual_income > 0 else 0
        
        # בניית הסבר
        tax_explanation_parts: list[str] = []
        tax_explanation_parts.append("💵 **הערכת מס בפרישה**")
        tax_explanation_parts.append("")
        tax_explanation_parts.append("**📊 הכנסות:**")
        tax_explanation_parts.append(f"  • קצבה חודשית: {monthly_pension:,.0f} ₪")
        if additional_income > 0:
            tax_explanation_parts.append(f"  • הכנסות נוספות: {additional_income:,.0f} ₪/חודש")
        tax_explanation_parts.append(f"  • סה\"כ שנתי: {total_annual_income:,.0f} ₪")
        
        tax_explanation_parts.append("")
        tax_explanation_parts.append("**💰 מס משוער:**")
        tax_explanation_parts.append(f"  • מס שנתי: {annual_tax:,.0f} ₪")
        tax_explanation_parts.append(f"  • מס חודשי: {monthly_tax:,.0f} ₪")
        tax_explanation_parts.append(f"  • שיעור מס אפקטיבי: {effective_rate:.1f}%")
        
        if exempt_pension_pct > 0:
            tax_explanation_parts.append("")
            tax_explanation_parts.append(f"✅ **פטור קצבה**: {exempt_pension_pct*100:.1f}% מהקצבה פטורים ממס (מקיבוע זכויות)")
        
        tax_explanation_parts.append("")
        tax_explanation_parts.append("**💡 שים לב:**")
        tax_explanation_parts.append("  • זו הערכה בלבד - המס בפועל תלוי בנקודות זיכוי ובניכויים נוספים")
        tax_explanation_parts.append("  • מומלץ להתייעץ עם יועץ מס לחישוב מדויק")
        
        return {
            "success": True,
            "tool_name": "GET_TAX_PROJECTION",
            "result": {
                "monthly_pension": monthly_pension,
                "additional_income": additional_income,
                "total_annual_income": total_annual_income,
                "annual_tax": annual_tax,
                "monthly_tax": monthly_tax,
                "effective_rate": effective_rate,
                "exempt_pension_percentage": exempt_pension_pct,
                "tax_breakdown": tax_breakdown,
            },
            "explanation": "\n".join(tax_explanation_parts),
        }

    def calculate_required_gross_withdrawal(
        self,
        desired_net_income: float,
        guaranteed_pension: float,
        retirement_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        מחשב את סכום הברוטו החודשי שצריך למשוך מההון כך שלאחר מס,
        ההכנסה החודשית נטו (קצבה מובטחת + משיכה) תגיע ליעד המבוקש.

        משתמש באותן מדרגות מס ופטור קצבה כמו GET_TAX_PROJECTION.
        """
        from app.services.tax_data.tax_brackets import TaxBracketsService
        from app.models.fixation_result import FixationResult
        from datetime import datetime

        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }

        # קביעת שנת המס לפי תאריך הפרישה אם סופק, אחרת השנה הנוכחית
        if retirement_date:
            try:
                tax_year = parse_date_flexible(retirement_date).year
            except Exception:
                tax_year = date.today().year
        else:
            tax_year = date.today().year

        tax_brackets = TaxBracketsService.get_tax_brackets(tax_year)

        # שליפת נתוני קיבוע (אם קיימים) כדי לחשב אחוז קצבה פטורה
        fixation = self.db.query(FixationResult).filter(
            FixationResult.client_id == self.client_id
        ).order_by(FixationResult.created_at.desc()).first()

        exempt_pension_pct = 0.0
        exemption_source = "None"
        
        if fixation and fixation.raw_result:
            try:
                fixation_data = fixation.raw_result if isinstance(fixation.raw_result, dict) else json.loads(fixation.raw_result)
                exempt_pension_pct = fixation_data.get("exemption_summary", {}).get("exempt_pension_percentage", 0)
                exemption_source = "FixationResult"
            except Exception:
                pass
        
        # אם אין נתוני קיבוע, נשתמש בהנחת ברירת מחדל אופטימית ל-2025+ (67% מהתקרה המזכה)
        # זהו התיקון שהתבקש כדי לשקף מצב ריאלי ב-2028
        if exempt_pension_pct == 0:
             # ערכים משוערים ל-2028
             ESTIMATED_QUALIFYING_CAP_2028 = 9924.0
             ESTIMATED_EXEMPTION_RATE_2028 = 0.67
             
             max_exempt_amount = ESTIMATED_QUALIFYING_CAP_2028 * ESTIMATED_EXEMPTION_RATE_2028
             exemption_source = "Default 2028 Estimation (67%)"
        else:
             # אם יש אחוז פטור ידוע, נניח שהוא חל על הקצבה המזכה
             # נשתמש בתקרה הנוכחית לחישוב הסכום
             ESTIMATED_QUALIFYING_CAP_2028 = 9924.0
             max_exempt_amount = ESTIMATED_QUALIFYING_CAP_2028 * exempt_pension_pct


        def _compute_net_for_withdrawal(withdrawal: float) -> tuple[float, float, float]:
            """מחזיר (נטו חודשי, מס חודשי, פטור שנוצל) עבור סכום משיכה חודשי נתון."""
            annual_pension = float(guaranteed_pension) * 12
            annual_withdrawal = float(withdrawal) * 12
            # הנחה: המשיכה נחשבת כהכנסה חייבת רגילה (קצבה או שכר), ולכן יכולה ליהנות מפטור קצבה אם נשאר
            # אם המשיכה היא הונית, היא לא נהנית מפטור קצבה מזכה, אבל בחישוב זה אנו מניחים מיסוי פירותי שולי.
            
            total_annual_income = annual_pension + annual_withdrawal

            if total_annual_income <= 0:
                return 0.0, 0.0, 0.0

            annual_tax = 0.0
            remaining_income = total_annual_income

            for bracket in tax_brackets:
                if remaining_income <= 0:
                    break

                bracket_min = bracket["min_income"]
                bracket_max = bracket["max_income"]
                rate = bracket["rate"]

                taxable_in_bracket = min(remaining_income, bracket_max - bracket_min + 1)
                if taxable_in_bracket > 0:
                    tax_in_bracket = taxable_in_bracket * rate
                    annual_tax += tax_in_bracket
                    remaining_income -= taxable_in_bracket

            # חישוב הפטור:
            # הפטור הוא שנתי = max_exempt_amount * 12
            # הוא חל על ההכנסה הפנסיונית (קצבה + משיכה פירותית)
            # אנו מניחים שכל ההכנסה כאן היא פנסיונית לצורך הפטור
            
            annual_max_exempt = max_exempt_amount * 12
            actual_exempt_amount = min(total_annual_income, annual_max_exempt)
            
            # חישוב הפחתת המס בגין הפטור (זיכוי מס)
            # שיטה מדויקת יותר: הפחתת ההכנסה החייבת לפני חישוב המס.
            # אבל המבנה הנוכחי של TaxBrackets מחשב על ברוטו מלא.
            # נבצע קירוב: המס שנחסך הוא המס השולי על החלק הפטור? 
            # או פשוט נוריד את המס על החלק הפטור כאילו הוא המס הראשון?
            # בישראל הפטור הוא "פטור ממס", כלומר ההכנסה החייבת קטנה.
            
            # נחשב מחדש את המס על (הכנסה ברוטו - הכנסה פטורה)
            taxable_income_after_exemption = max(0, total_annual_income - actual_exempt_amount)
            
            final_annual_tax = 0.0
            remaining_taxable = taxable_income_after_exemption
            
            for bracket in tax_brackets:
                if remaining_taxable <= 0:
                    break
                    
                bracket_min = bracket["min_income"]
                bracket_max = bracket["max_income"]
                rate = bracket["rate"]
                
                # כאן יש ניואנס: מדרגות המס חלות על ההכנסה החייבת.
                # הפטור מוריד את ההכנסה החייבת "מלמטה" או "מלמעלה"?
                # בישראל: הפטור מקטין את ההכנסה החייבת. המדרגות חלות על היתרה.
                
                span = bracket_max - bracket_min + 1
                taxable_in_bracket = min(remaining_taxable, span)
                
                if taxable_in_bracket > 0:
                    final_annual_tax += taxable_in_bracket * rate
                    remaining_taxable -= taxable_in_bracket

            monthly_tax = final_annual_tax / 12
            total_gross = float(guaranteed_pension) + float(withdrawal)
            net_income = total_gross - monthly_tax
            
            return net_income, monthly_tax, (actual_exempt_amount / 12)

        # בדיקה האם הקצבה המובטחת לבדה כבר מספיקה
        base_net, base_tax, base_exempt = _compute_net_for_withdrawal(0.0)
        if base_net >= desired_net_income:
            return {
                "success": True,
                "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
                "result": {
                    "required_gross_withdrawal": 0.0,
                    "total_gross_income": round(float(guaranteed_pension), 2),
                    "final_net_income": round(base_net, 2),
                    "tax_amount": round(base_tax, 2),
                    "is_net_goal_achieved": True,
                    "tax_exemption_applied": round(base_exempt, 2),
                    "exemption_source": exemption_source
                },
                "explanation": "הקצבה המובטחת לבדה כבר גבוהה או שווה ליעד הנטו.",
            }

        # חיפוש גס לגבול עליון
        low = 0.0
        high = max(desired_net_income - base_net, 0) * 3 or 10000.0
        target = float(desired_net_income)

        net_high, tax_high, _ = _compute_net_for_withdrawal(high)
        iterations = 0
        while net_high < target and high < 1_000_000 and iterations < 20:
            high *= 2
            net_high, tax_high, _ = _compute_net_for_withdrawal(high)
            iterations += 1

        # חיפוש בינארי
        best_withdrawal = high
        best_net = net_high
        best_tax = tax_high
        best_exempt = 0.0

        for _ in range(40):
            mid = (low + high) / 2
            net_mid, tax_mid, exempt_mid = _compute_net_for_withdrawal(mid)
            if net_mid >= target:
                best_withdrawal = mid
                best_net = net_mid
                best_tax = tax_mid
                best_exempt = exempt_mid
                high = mid
            else:
                low = mid

        total_gross_income = float(guaranteed_pension) + float(best_withdrawal)
        is_achieved = best_net >= target * 0.995  # מרווח קטן לדיוק מספרי

        return {
            "success": True,
            "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
            "result": {
                "required_gross_withdrawal": round(best_withdrawal, 2),
                "total_gross_income": round(total_gross_income, 2),
                "final_net_income": round(best_net, 2),
                "tax_amount": round(best_tax, 2),
                "is_net_goal_achieved": is_achieved,
                "tax_exemption_applied": round(best_exempt, 2),
                "exemption_source": exemption_source
            },
            "explanation": f"בוצע חישוב הפוך למציאת משיכת ברוטו נדרשת להשגת נטו חודשי יעד (כולל פטור {exemption_source}).",
        }

    def get_pension_products(self) -> Dict[str, Any]:
        """
        מחזיר את כל המוצרים הפנסיוניים וההוניים של הלקוח בצורה מרוכזת.
        """
        client = self.client
        if not client:
            logger.warning("GET_PENSION_PRODUCTS: client %s not found", self.client_id)
            return {
                "success": False,
                "tool_name": "GET_PENSION_PRODUCTS",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }

        logger.info("GET_PENSION_PRODUCTS: client %s loaded", self.client_id)

        products: list[dict[str, Any]] = []
        pension_products: list[dict[str, Any]] = []
        capital_products: list[dict[str, Any]] = []

        # 1. קרנות פנסיה וקופות גמל
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()

        # 2. נכסים הוניים (ביטוח מנהלים, גמל להשקעה)
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()

        logger.info(
            "GET_PENSION_PRODUCTS: client %s has %d pension funds and %d capital assets",
            self.client_id,
            len(pension_funds),
            len(capital_assets),
        )

        for pf in pension_funds:
            pf_created_at = getattr(pf, "created_at", None)
            pf_updated_at = getattr(pf, "updated_at", None)
            item = {
                "category": "pension",
                "id": pf.id,
                "fund_name": pf.fund_name,
                "fund_type": pf.fund_type,
                "input_mode": pf.input_mode,
                "balance": float(pf.balance or 0),
                "annuity_factor": float(pf.annuity_factor) if pf.annuity_factor else None,
                "pension_amount": float(pf.pension_amount) if pf.pension_amount else None,
                "pension_start_date": pf.pension_start_date.isoformat() if pf.pension_start_date else None,
                "tax_treatment": pf.tax_treatment,
                "deduction_file": pf.deduction_file,
                "conversion_source": pf.conversion_source,
                "remarks": pf.remarks,
                "created_at": pf_created_at.isoformat() if pf_created_at else None,
                "updated_at": pf_updated_at.isoformat() if pf_updated_at else None,
            }
            pension_products.append(item)
            products.append(item)

        for ca in capital_assets:
            ca_created_at = getattr(ca, "created_at", None)
            ca_updated_at = getattr(ca, "updated_at", None)
            item = {
                "category": "capital",
                "id": ca.id,
                "asset_name": ca.asset_name,
                "asset_type": ca.asset_type,
                "current_value": float(ca.current_value or 0),
                "monthly_income": float(ca.monthly_income) if ca.monthly_income else None,
                "start_date": ca.start_date.isoformat() if ca.start_date else None,
                "end_date": ca.end_date.isoformat() if ca.end_date else None,
                "tax_treatment": ca.tax_treatment,
                "conversion_source": ca.conversion_source,
                "remarks": ca.remarks,
                "description": ca.description,
                "created_at": ca_created_at.isoformat() if ca_created_at else None,
                "updated_at": ca_updated_at.isoformat() if ca_updated_at else None,
            }
            capital_products.append(item)
            products.append(item)

        # מיון לפי יתרה יורדת
        products.sort(
            key=lambda x: float(x.get("balance") or x.get("current_value") or 0),
            reverse=True,
        )

        total_balance = sum(
            float(p.get("balance") or p.get("current_value") or 0) for p in products
        )

        logger.info(
            "GET_PENSION_PRODUCTS: returning %d products (total_balance=%s) for client %s",
            len(products),
            total_balance,
            self.client_id,
        )

        # יצירת הסבר טקסטואלי קצר לשימוש המודל
        explanation = (
            f"נמצאו {len(products)} מוצרים בתיק.\n"
            f"סה\"כ צבירה: {total_balance:,.0f} ₪."
        )

        return {
            "success": True,
            "tool_name": "GET_PENSION_PRODUCTS",
            "result": {
                "products": products,
                "pension_funds": pension_products,
                "capital_assets": capital_products,
                "total_balance": total_balance,
                "count": len(products),
            },
            "explanation": explanation,
        }

    def calculate_tax_exempt_pension(self, current_tax_exempt_grant_amount: float) -> Dict[str, Any]:
        """
        מבצע סימולציה של חישוב קיבוע זכויות (Tax Relief) והשפעת משיכת מענק פטור.
        מחשב את הקצבה הפטורה לפני ואחרי קיזוז המענק המבוקש.
        """
        from app.models.fixation_result import FixationResult
        
        # קבועים לחישוב (נכון ל-2025)
        QUALIFYING_PENSION_CAP = 9924  # תקרת קצבה מזכה משוערת ל-2025
        EXEMPTION_RATE = 0.52          # שיעור הפטור (52%)
        OFFSET_FACTOR = 1.35           # מקדם קיזוז למענקים (נוסחת הקיזוז)
        CAPITALIZATION_FACTOR = 180    # מקדם המרה להון (180 משכורות)
        
        # 1. שליפת נתונים קיימים או חישוב ברירת מחדל
        fixation = self.db.query(FixationResult).filter(
            FixationResult.client_id == self.client_id
        ).first()

        if fixation and fixation.exempt_capital_remaining > 0:
            total_exempt_capital = fixation.exempt_capital_remaining
            source = "FixationResult (DB)"
        else:
            # חישוב ברירת מחדל אם אין קיבוע היסטורי
            monthly_exemption = QUALIFYING_PENSION_CAP * EXEMPTION_RATE
            total_exempt_capital = monthly_exemption * CAPITALIZATION_FACTOR
            source = "Default (2025 Estimation)"

        # 2. חישוב קצבה פטורה התחלתית (ללא משיכת המענק הנוכחי)
        # אם יש מענקים קודמים, הם כבר מגולמים ב-exempt_capital_remaining
        initial_exempt_pension = total_exempt_capital / CAPITALIZATION_FACTOR

        # 3. סימולציה: קיזוז המענק הנוכחי
        # כל שקל מענק מקזז 1.35 שקל מההון הפטור
        grant_offset_value = current_tax_exempt_grant_amount * OFFSET_FACTOR
        remaining_capital_after_grant = max(0, total_exempt_capital - grant_offset_value)
        
        final_exempt_pension = remaining_capital_after_grant / CAPITALIZATION_FACTOR

        # 4. הכנת תוצאה
        monthly_loss = initial_exempt_pension - final_exempt_pension
        
        # פורמט טקסטואלי לתשובה
        scenario_a = (
            f"תרחיש A (שמירת הפטור לקצבה):\n"
            f"• סה\"כ הון פטור זמין: {total_exempt_capital:,.0f} ₪\n"
            f"• קצבה פטורה חודשית: {initial_exempt_pension:,.0f} ₪"
        )
        
        scenario_b = (
            f"תרחיש B (משיכת מענק פטור בסך {current_tax_exempt_grant_amount:,.0f} ₪):\n"
            f"• עלות הקיזוז בהון: {grant_offset_value:,.0f} ₪ (לפי מקדם 1.35)\n"
            f"• הון פטור נותר: {remaining_capital_after_grant:,.0f} ₪\n"
            f"• קצבה פטורה חודשית: {final_exempt_pension:,.0f} ₪"
        )
        
        explanation = (
            f"בוצעה סימולציית קיבוע זכויות ({source}).\n"
            f"משיכת מענק של {current_tax_exempt_grant_amount:,.0f} ₪ תקטין את הקצבה הפטורה ב-{monthly_loss:,.0f} ₪ לכל החיים."
        )

        return {
            "success": True,
            "tool_name": "CALCULATE_TAX_EXEMPT_PENSION",
            "result": {
                "initial_exempt_pension": round(initial_exempt_pension, 2),
                "final_exempt_pension": round(final_exempt_pension, 2),
                "exempt_grant_used": current_tax_exempt_grant_amount,
                "monthly_pension_loss": round(monthly_loss, 2),
                "total_capital_offset": round(grant_offset_value, 2),
                "remaining_exempt_capital": round(remaining_capital_after_grant, 2),
                "scenarios_text": {
                    "scenario_a": scenario_a,
                    "scenario_b": scenario_b,
                }
            },
            "explanation": explanation
        }

    def run_retirement_cashflow_analysis(
        self,
        retirement_date: str,
        desired_monthly_income: Optional[float] = None,
        apply_max_exemption: bool = False
    ) -> Dict[str, Any]:
        """
        מבצע ניתוח תזרים מזומנים בפרישה:
        1. חישוב קצבה פנסיונית צפויה
        2. חישוב ביטוח לאומי (אזרח ותיק)
        3. בדיקת גירעון מול היעד
        4. חישוב משך הזמן שההון יספיק לכיסוי הגירעון
        """
        from datetime import datetime, date
        from dateutil.relativedelta import relativedelta
        
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }

        # 1. Parsing & Defaults
        try:
            target_date = parse_date_flexible(retirement_date)
        except ValueError:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": f"תאריך לא תקין: {retirement_date}. יש להשתמש בפורמט YYYY-MM-DD.",
            }

        if desired_monthly_income is None:
            # ברירת מחדל: 70% מהשכר האחרון או 15,000 ש"ח
            if client.annual_salary:
                desired_monthly_income = (client.annual_salary / 12) * 0.7
            else:
                desired_monthly_income = 15000.0

        # 2. חישוב גיל הפרישה המתוכנן
        # שימוש בלוגיקה קיימת של המודל אם אפשר, או חישוב פשוט
        birth_date = client.birth_date or date(1970, 1, 1)
        age_at_retirement = relativedelta(target_date, birth_date).years
        
        # Refresh client to ensure relationships are loaded
        self.db.refresh(client)

        # 3. חישוב קצבה פנסיונית צפויה (Projected Pension)
        
        total_pension_balance = 0.0
        # סכום קצבאות שכבר נקובות (למשל פנסיה תקציבית או ותיקה)
        existing_pension_sum = 0.0
        
        pension_funds = []
        capital_assets = []
        
        # בדיקה האם יש נכסים בבסיס הנתונים (לאחר המרה)
        # אם יש - נעדיף אותם על פני נתונים מוזרקים כדי למנוע כפילויות
        db_pension_count = self.db.query(PensionFund).filter(PensionFund.client_id == self.client_id).count()
        db_capital_count = self.db.query(CapitalAsset).filter(CapitalAsset.client_id == self.client_id).count()
        has_db_assets = (db_pension_count + db_capital_count) > 0
        
        if has_db_assets:
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %d pension funds and %d capital assets in DB for client %s - using DB records",
                db_pension_count, db_capital_count, self.client_id
            )
        
        # אם יש נכסים ב-DB, נשתמש בהם. אחרת, נשתמש בנתונים המוזרקים
        if has_db_assets:
            # שימוש בנכסים מבסיס הנתונים (לאחר TRANSFORM_FUNDS_TO_ASSETS)
            pension_funds = list(self.db.query(PensionFund).filter(PensionFund.client_id == self.client_id).all())
            capital_assets = list(self.db.query(CapitalAsset).filter(CapitalAsset.client_id == self.client_id).all())
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Loaded %d pension funds and %d capital assets from DB",
                len(pension_funds), len(capital_assets)
            )
        elif self.pension_portfolio_data and len(self.pension_portfolio_data) > 0:
            # שלב 1: שימוש בנתונים המוזרקים מה-Request (Pydantic models)
            # המרה לאובייקטי מודל כדי שהלוגיקה בהמשך תעבוד
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Using injected pension_portfolio_data with %s accounts for client %s",
                len(self.pension_portfolio_data),
                getattr(self, "client_id", None),
            )
            for acc in self.pension_portfolio_data:
                balance = float(acc.יתרה or 0)
                product_type_raw = acc.סוג_מוצר or ""
                name = acc.שם_תכנית or "ללא שם"

                if balance <= 0:
                    continue

                # סייגי מוצר בעדיפות עליונה
                is_study_fund = "קרן השתלמות" in product_type_raw
                is_investment_gemel = "גמל להשקעה" in product_type_raw
                is_gemel_fund = ("קופת גמל" in product_type_raw) and not is_investment_gemel

                classification: str | None = None  # "pension", "capital", "unspecified"

                if is_study_fund or is_investment_gemel:
                    classification = "capital"
                else:
                    # קריאת טורי פיצויים ותגמולים אם קיימים
                    pitz_current = float(getattr(acc, "פיצויים_מעסיק_נוכחי", 0) or 0)
                    pitz_after_settlement = float(getattr(acc, "פיצויים_לאחר_התחשבנות", 0) or 0)
                    pitz_not_settled = float(getattr(acc, "פיצויים_שלא_עברו_התחשבנות", 0) or 0)
                    pitz_prev_rights = float(getattr(acc, "פיצויים_ממעסיקים_קודמים_רצף_זכויות", 0) or 0)
                    pitz_prev_pension = float(getattr(acc, "פיצויים_ממעסיקים_קודמים_רצף_קצבה", 0) or 0)

                    emp_before_2000 = float(getattr(acc, "תגמולי_עובד_עד_2000", 0) or 0)
                    emp_after_2000 = float(getattr(acc, "תגמולי_עובד_אחרי_2000", 0) or 0)
                    emp_after_2008_np = float(getattr(acc, "תגמולי_עובד_אחרי_2008_לא_משלמת", 0) or 0)
                    empr_before_2000 = float(getattr(acc, "תגמולי_מעביד_עד_2000", 0) or 0)
                    empr_after_2000 = float(getattr(acc, "תגמולי_מעביד_אחרי_2000", 0) or 0)
                    empr_after_2008_np = float(getattr(acc, "תגמולי_מעביד_אחרי_2008_לא_משלמת", 0) or 0)

                    capital_sum = 0.0
                    pension_sum = 0.0
                    unspecified_sum = 0.0

                    # טורי "ללא סיווג": פיצויים שלא עברו התחשבנות + רצף זכויות
                    unspecified_sum += pitz_not_settled + pitz_prev_rights

                    # פיצויים לאחר התחשבנות – הון
                    capital_sum += pitz_after_settlement

                    # פיצויים מעסיק נוכחי – גמיש, ברירת מחדל הון
                    capital_sum += pitz_current

                    # פיצויים ממעסיקים קודמים ברצף קצבה – קצבה
                    pension_sum += pitz_prev_pension

                    # תגמולי עובד/מעביד אחרי 2000 – קצבה, למעט קופת גמל = הון
                    if emp_after_2000 > 0:
                        if is_gemel_fund:
                            capital_sum += emp_after_2000
                        else:
                            pension_sum += emp_after_2000
                    if empr_after_2000 > 0:
                        if is_gemel_fund:
                            capital_sum += empr_after_2000
                        else:
                            pension_sum += empr_after_2000

                    # תגמולי עובד/מעביד אחרי 2008 (לא משלמת) – קצבה
                    pension_sum += emp_after_2008_np + empr_after_2008_np

                    # תגמולי עובד/מעביד עד 2000 – גמיש, ברירת מחדל הון
                    capital_sum += emp_before_2000 + empr_before_2000

                    total_cols = capital_sum + pension_sum + unspecified_sum

                    if total_cols > 0:
                        if capital_sum == 0 and pension_sum == 0:
                            classification = "unspecified"
                        elif pension_sum >= capital_sum:
                            classification = "pension"
                        else:
                            classification = "capital"

                if classification is None:
                    # fallback: קופת גמל כהון, אחרת קצבה
                    if is_gemel_fund or is_study_fund or is_investment_gemel:
                        classification = "capital"
                    else:
                        classification = "pension"

                logger.info(
                    "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Injected account classified as %s - name=%s, type=%s, balance=%.2f",
                    classification,
                    name,
                    product_type_raw,
                    balance,
                )

                if classification == "unspecified":
                    # לא נכנס לחישוב הון/קצבה, דורש החלטה נפרדת
                    continue

                if classification == "capital":
                    ca = CapitalAsset(
                        client_id=self.client_id,
                        asset_name=name,
                        asset_type=acc.סוג_מוצר,
                        current_value=balance,
                        annual_return_rate=0,
                        payment_frequency='monthly',
                        start_date=date.today(),
                    )
                    capital_assets.append(ca)
                else:
                    pf = PensionFund(
                        client_id=self.client_id,
                        fund_name=name,
                        fund_type=acc.סוג_מוצר,
                        balance=balance,
                        pension_amount=0,
                        input_mode="manual",
                    )
                    pension_funds.append(pf)

            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %s pension funds (via raw data injection) and %s capital assets",
                len(pension_funds),
                len(capital_assets),
            )
            
        else:
            # Fallback למקרה שהנתונים לא הוזרקו כלל - נסיון אחרון דרך ה-Client
            logger.info("RUN_RETIREMENT_CASHFLOW_ANALYSIS: No injected pension portfolio data, falling back to client relationships.")
            pension_funds_raw = self.client.pension_funds if self.client else []
            capital_assets_raw = self.client.capital_assets if self.client else []
            
            pension_funds = [acc for acc in pension_funds_raw if isinstance(acc, PensionFund)]
            capital_assets = [acc for acc in capital_assets_raw if isinstance(acc, CapitalAsset)]
            
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %s pension funds (via client relationship fallback) for client %s",
                len(pension_funds), getattr(self, "client_id", None),
            )
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %s capital assets (via client relationship fallback) for client %s",
                len(capital_assets), getattr(self, "client_id", None),
            )

        # לוג מפורט על כל קרן פנסיה לפני החישוב
        if pension_funds:
            logger.info("RUN_RETIREMENT_CASHFLOW_ANALYSIS: Pension fund details for client %s:", getattr(self, "client_id", None))
            for pf in pension_funds:
                logger.info(
                    "  Fund id=%s, name=%s, type=%s, balance=%.2f, pension_amount=%.2f, input_mode=%s, start_date=%s",
                    getattr(pf, "id", None),
                    getattr(pf, "fund_name", None),
                    getattr(pf, "fund_type", None),
                    (pf.balance or 0.0),
                    (pf.pension_amount or 0.0),
                    getattr(pf, "input_mode", None),
                    getattr(pf, "pension_start_date", None),
                )

        # לוג מפורט על כל נכס הון לפני החישוב (כדי לאתר הון שמופיע רק כ-capital_asset)
        if capital_assets:
            logger.info("RUN_RETIREMENT_CASHFLOW_ANALYSIS: Capital asset details for client %s:", getattr(self, "client_id", None))
            for ca in capital_assets:
                logger.info(
                    "  CapitalAsset id=%s, name=%s, type=%s, current_value=%.2f, monthly_income=%.2f, start_date=%s",
                    getattr(ca, "id", None),
                    getattr(ca, "asset_name", None),
                    getattr(ca, "asset_type", None),
                    float(ca.current_value or 0),
                    float(ca.monthly_income or 0),
                    getattr(ca, "start_date", None),
                )

        for pf in pension_funds:
            total_pension_balance += (pf.balance or 0)
            existing_pension_sum += (pf.pension_amount or 0)

        logger.info(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Total pension balance after aggregation = %.2f, existing monthly pension sum = %.2f",
            total_pension_balance,
            existing_pension_sum,
        )

        # קבלת מקדם המרה דינמי לפי גיל ותאריך תחילת קצבה
        annuity_factor = float(PENSION_COEFFICIENT)
        logger.info(
            "🔍 [RUN 16 DEBUG] Starting annuity coefficient retrieval for age %s, date %s",
            age_at_retirement, target_date
        )
        try:
            coeff_result = get_annuity_coefficient(
                product_type="קרן פנסיה",  # שימוש בזיהוי קרן פנסיה כמו בשאר המערכת
                start_date=target_date,
                gender=client.gender or "זכר",
                retirement_age=age_at_retirement,
                target_year=target_date.year,
                birth_date=birth_date,
                pension_start_date=target_date,
            )
            logger.info(
                "✅ [RUN 16 DEBUG] Coefficient result: %s",
                coeff_result
            )
            annuity_factor = float(coeff_result.get("factor_value") or annuity_factor)
            logger.info(
                "📊 [RUN 16 DEBUG] Using annuity_factor: %.2f (source: %s)",
                annuity_factor,
                coeff_result.get("source_table", "unknown")
            )
        except Exception as e:  # הגנה: אם השירות נכשל, נשתמש במקדם ברירת מחדל
            logger.warning(
                "❌ [RUN 16 DEBUG] Failed to get annuity coefficient, "
                "falling back to default %s: %s",
                annuity_factor,
                e,
            )

        if annuity_factor <= 0:
            logger.warning("⚠️ [RUN 16 DEBUG] Factor was <= 0, resetting to default: %s", PENSION_COEFFICIENT)
            annuity_factor = float(PENSION_COEFFICIENT)

        logger.info(
            "🧮 [RUN 16 DEBUG] Calculating projected pension: balance=%.2f / factor=%.2f",
            total_pension_balance, annuity_factor
        )
        projected_new_pension = total_pension_balance / annuity_factor if total_pension_balance > 0 else 0.0
        logger.info(
            "💰 [RUN 16 DEBUG] Projected NEW pension from balance: %.2f ₪/month",
            projected_new_pension
        )
        total_pension_income = existing_pension_sum + projected_new_pension
        logger.info(
            "💵 [RUN 16 DEBUG] TOTAL pension income: existing=%.2f + new=%.2f = %.2f ₪/month",
            existing_pension_sum, projected_new_pension, total_pension_income
        )

        # 4. חישוב קצבת אזרח ותיק (ביטוח לאומי)
        # הערכה בסיסית: בסיס + תוספת ותק
        # בסיס ליחיד (2025 משוער): ~1730 ש"ח
        # תוספת ותק מקסימלית (50%): ~865 ש"ח
        # סה"כ מקסימלי ליחיד: ~2600 ש"ח
        # (נניח תרחיש סביר של 2400 ש"ח אם לא ידוע אחרת)
        # לצורך דיבאג ננטרל את ברירת המחדל וניצור לוג מפורט על הערך בפועל
        social_security_amount = 0.0
        
        # התאמה לפי גיל הזכאות (נשים 62-65, גברים 67)
        # אם פורש לפני הזמן - 0
        legal_retirement_age = 67 if (client.gender == "male" or not client.gender) else 65
        if age_at_retirement < legal_retirement_age:
            social_security_amount = 0.0

        logger.info(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Social security amount used = %.2f (age_at_retirement=%s, legal_retirement_age=%s)",
            social_security_amount,
            age_at_retirement,
            legal_retirement_age,
        )

        total_guaranteed_income_gross = total_pension_income + social_security_amount

        # ===== חישוב מס על הקצבה (Tax Analysis) =====
        # יצירת פרטים אישיים לחישוב מס
        tax_personal_details = PersonalDetails(
            birth_date=birth_date,
            marital_status="single",  # ברירת מחדל - ניתן לשפר בהמשך
            is_veteran=False,
            is_disabled=False,
        )

        # חישוב מס על הקצבה השנתית
        annual_pension_gross = total_pension_income * 12
        tax_year = target_date.year

        # ===== חישוב פטור קיבוע זכויות (Run 25) =====
        # אם apply_max_exemption=True, נחשב את הפטור המקסימלי לפי שנת הפרישה
        # ונשמור את תוצאות הקיבוע ל-DB כדי שיהיו זמינות לדוחות ולממשק
        exempt_pension_monthly = 0.0
        exemption_percentage = 0.0
        monthly_cap = 0.0
        fixation_saved = False

        if apply_max_exemption:
            # חישוב פטור מקסימלי לפי שנת הזכאות
            # פטור חודשי = תקרת פיצויים × אחוז פטור
            monthly_cap = get_monthly_cap(tax_year)
            exemption_percentage = get_exemption_percentage(tax_year)
            exempt_pension_monthly = monthly_cap * exemption_percentage

            # הפטור לא יכול לעלות על הקצבה בפועל
            exempt_pension_monthly = min(exempt_pension_monthly, total_pension_income)

            logger.info(
                "EXEMPTION ANALYSIS (Run 25): Year=%d, Monthly Cap=%.2f, Exemption %%=%.1f%%, Max Exempt=%.2f",
                tax_year, monthly_cap, exemption_percentage * 100, exempt_pension_monthly
            )

            # שמירת קיבוע זכויות ל-DB כדי שיהיה זמין לדוחות ולממשק
            try:
                from app.routers.rights_fixation import (
                    calculate_and_save_fixation_for_client,
                    update_fixation_exempt_pension_fields,
                )
                fixation_result = calculate_and_save_fixation_for_client(self.db, self.client_id)
                if fixation_result:
                    try:
                        update_fixation_exempt_pension_fields(fixation_result)
                    except Exception as update_err:
                        logger.warning(
                            "RIGHTS FIXATION: Failed updating exempt pension fields: %s",
                            update_err,
                        )

                    self.db.commit()
                    self.db.refresh(fixation_result)
                    fixation_saved = True
                    logger.info(
                        "RIGHTS FIXATION: Auto-saved fixation for client %s (exempt_capital_remaining=%.2f)",
                        self.client_id, fixation_result.exempt_capital_remaining or 0
                    )
                else:
                    logger.warning("RIGHTS FIXATION: Failed to auto-save fixation for client %s", self.client_id)
            except Exception as fix_err:
                self.db.rollback()
                logger.warning("RIGHTS FIXATION: Error auto-saving fixation: %s", fix_err)

        try:
            tax_calculator = TaxCalculator(tax_year=tax_year)
            
            # יצירת קלט לחישוב מס - עם פטור קיבוע זכויות אם מופעל
            tax_input = TaxCalculationInput(
                tax_year=tax_year,
                personal_details=tax_personal_details,
                pension_income=annual_pension_gross,
                exempt_pension_amount=exempt_pension_monthly,  # פטור חודשי מקיבוע זכויות
                pension_months_in_year=12,
            )

            tax_result = tax_calculator.calculate_comprehensive_tax(tax_input)

            # חישוב נטו חודשי - המרה מפורשת ל-float למניעת שגיאת Decimal serialization
            annual_net_income = float(tax_result.net_income)
            monthly_net_pension = annual_net_income / 12
            monthly_tax_deduction = float(tax_result.net_tax) / 12
            monthly_health_tax = float(tax_result.health_tax) / 12
            monthly_income_tax = float(tax_result.income_tax) / 12

            logger.info(
                "TAX ANALYSIS: Gross annual pension=%.2f, Net annual=%.2f, Tax=%.2f, Health=%.2f",
                annual_pension_gross, annual_net_income, float(tax_result.income_tax), float(tax_result.health_tax)
            )
            logger.info(
                "TAX ANALYSIS: Monthly gross=%.2f, Monthly net=%.2f, Monthly tax deduction=%.2f, Exempt=%.2f",
                total_pension_income, monthly_net_pension, monthly_tax_deduction, exempt_pension_monthly
            )

        except Exception as e:
            logger.error(
                "TAX ANALYSIS: Failed to calculate tax for retirement_date=%s (tax_year=%s). Refusing to return fallback tax=0: %s",
                retirement_date,
                tax_year,
                e,
                exc_info=True,
            )
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": (
                    "שגיאה בחישוב מס הכנסה לקצבה. "
                    "כדי למנוע הצגת נתונים שגויים, המערכת לא מחזירה תוצאת מס משוערת במקרה זה. "
                    f"פרטים טכניים: {str(e)}"
                ),
            }

        # הכנסה מובטחת נטו (כולל ביטוח לאומי שהוא פטור ממס)
        total_guaranteed_income_net = monthly_net_pension + social_security_amount
        total_guaranteed_income = total_guaranteed_income_gross  # לשמירה על תאימות לאחור

        # 5. ניתוח גירעון (Gap Analysis) - מבוסס על נטו
        gap = desired_monthly_income - total_guaranteed_income_net
        
        # 6. חישוב הון זמין
        # שימוש ברשימה המסוננת שכבר יצרנו
        # capital_assets כבר חושב למעלה
        # המרה ל-float כדי למנוע שגיאת Decimal serialization
        total_capital_available = 0.0
        for ca in capital_assets:
            try:
                val = float(getattr(ca, "current_value", 0) or 0)
            except Exception:
                val = 0.0
            if val <= 0:
                try:
                    val = float(getattr(ca, "monthly_income", 0) or 0)
                except Exception:
                    val = 0.0
            total_capital_available += val
        # נניח שגם קרנות השתלמות נזילות בפרישה
        
        # 7. חישוב משך כיסוי (Sufficiency)
        sufficiency_years = 999.0 # אינסוף
        is_sustainable = True
        required_capital_withdrawal = 0.0

        logger.info(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Final calculations - Projected Pension: %s, Total Liquid Capital: %s, Gap: %s",
            total_pension_income, total_capital_available, gap
        )

        if gap > 0:
            is_sustainable = False
            required_capital_withdrawal = gap
            if total_capital_available > 0:
                months_covered = total_capital_available / gap
                sufficiency_years = months_covered / 12
                if sufficiency_years > (120 - age_at_retirement): # הנחת תוחלת חיים
                     is_sustainable = True
            else:
                sufficiency_years = 0.0
        else:
            # עודף תזרימי
            sufficiency_years = 999.0
            
        # 8. בניית התשובה
        
        # יצירת הסבר
        deficit_status = "עודף" if gap <= 0 else "גירעון"
        gap_abs = abs(gap)
        
        # בניית הסבר עם/בלי פטור קיבוע זכויות
        exemption_info = ""
        if apply_max_exemption and exempt_pension_monthly > 0:
            exemption_info = f"\n🎁 **פטור קיבוע זכויות (מקסימלי):**\n   אחוז פטור: {exemption_percentage * 100:.1f}%\n   קצבה פטורה: {exempt_pension_monthly:,.0f} ₪/חודש\n"

        explanation_lines = [
            f"**דוח תזרים לפרישה בתאריך {target_date.strftime('%d/%m/%Y')} (גיל {age_at_retirement})**",
            f"",
            f"💰 **הכנסה ברוטו חודשית:** {total_guaranteed_income_gross:,.0f} ₪",
            f"   (פנסיה ברוטו: {total_pension_income:,.0f} ₪ + ביטוח לאומי: {social_security_amount:,.0f} ₪)",
        ]

        if exemption_info:
            explanation_lines.append(exemption_info)

        explanation_lines.extend([
            f"",
            f"📊 **ניתוח מס הכנסה:**",
            f"   מס הכנסה חודשי על הקצבה: {monthly_income_tax:,.0f} ₪",
            f"",
            f"✅ **הכנסה נטו חודשית:** {total_guaranteed_income_net:,.0f} ₪",
            f"   (פנסיה נטו: {monthly_net_pension:,.0f} ₪ + ביטוח לאומי: {social_security_amount:,.0f} ₪)",
            f"",
            f"🎯 **יעד הכנסה:** {desired_monthly_income:,.0f} ₪",
            f"📉 **{deficit_status} חודשי (ברוטו):** {gap_abs:,.0f} ₪",
        ])
        
        if gap > 0:
            explanation_lines.append(f"")
            explanation_lines.append(f"🏦 **שימוש בהון פנוי:**")
            explanation_lines.append(f"   סך הון זמין: {total_capital_available:,.0f} ₪")
            if total_capital_available > 0:
                explanation_lines.append(f"   ההון יספיק לכיסוי הגירעון למשך **{sufficiency_years:.1f} שנים** (עד גיל {age_at_retirement + sufficiency_years:.1f}).")
            else:
                explanation_lines.append(f"   ⚠️ אין הון פנוי לכיסוי הגירעון!")

        return {
            "success": True,
            "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            "result": {
                "retirement_date": retirement_date,
                "retirement_age": age_at_retirement,
                # ברוטו
                "projected_pension": round(total_pension_income, 2),
                "social_security": social_security_amount,
                "total_guaranteed_income": round(total_guaranteed_income_gross, 2),
                # פטור קיבוע זכויות
                "apply_max_exemption": apply_max_exemption,
                "exemption_percentage": round(exemption_percentage * 100, 1),
                "exempt_pension_monthly": round(exempt_pension_monthly, 2),
                # ניתוח מס
                "monthly_income_tax": round(monthly_income_tax, 2),
                "monthly_health_tax": round(monthly_health_tax, 2),
                "monthly_tax_deduction": round(monthly_tax_deduction, 2),
                # נטו
                "projected_pension_net": round(monthly_net_pension, 2),
                "total_guaranteed_income_net": round(total_guaranteed_income_net, 2),
                # יעד וגירעון
                "desired_monthly_income": desired_monthly_income,
                "monthly_deficit_or_surplus": round(-gap, 2),  # שלילי = גירעון
                "required_capital_withdrawal": round(required_capital_withdrawal, 2),
                "total_liquid_capital": round(total_capital_available, 2),
                "capital_sufficiency_years": round(sufficiency_years, 1),
                "is_sustainable": is_sustainable
            },
            "explanation": "\n".join(explanation_lines)
        }

    def calculate_pension_commutation(
        self,
        target_monthly_pension_reduction: float,
        retirement_date: str,
    ) -> Dict[str, Any]:
        """
        מחשב היוון קצבה - המרת חלק מהקצבה החודשית לסכום חד-פעמי.
        
        Args:
            target_monthly_pension_reduction: הסכום החודשי שהלקוח מוכן להפחית מהקצבה (ברוטו)
            retirement_date: תאריך הפרישה (YYYY-MM-DD)
            
        Returns:
            Dict עם סכום ההיוון ברוטו, מס, ונטו
        """
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        if not client.birth_date:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": "חסר תאריך לידה ללקוח - לא ניתן לחשב מקדמי קצבה.",
            }

        # פרסור תאריך פרישה
        try:
            ret_date = parse_date_flexible(retirement_date)
        except Exception:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": f"תאריך פרישה לא תקין: {retirement_date}. יש להזין בפורמט YYYY-MM-DD.",
            }

        # חישוב גיל פרישה
        age_at_retirement = ret_date.year - client.birth_date.year
        if (ret_date.month, ret_date.day) < (client.birth_date.month, client.birth_date.day):
            age_at_retirement -= 1

        current_age = client.get_age() if hasattr(client, 'get_age') else None
        if current_age and age_at_retirement < current_age:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": f"גיל הפרישה ({age_at_retirement}) לא יכול להיות נמוך מהגיל הנוכחי ({current_age}).",
            }

        # קבלת מקדם קצבה ממוצע
        gender = client.gender or 'זכר'
        try:
            coeff_result = get_annuity_coefficient(
                product_type='קרן פנסיה',
                start_date=date.today(),
                gender=gender,
                retirement_age=age_at_retirement,
                survivors_option='תקנוני',
                birth_date=client.birth_date,
                pension_start_date=ret_date,
            )
            annuity_factor = float(coeff_result.get('factor_value', 200))
        except Exception:
            annuity_factor = 200.0

        # חישוב הכנסה שנתית אחרת (אם יש)
        other_annual_income = 0.0
        if client.annual_salary:
            other_annual_income = float(client.annual_salary)

        # ביצוע חישוב ההיוון
        commutation_service = CommutationService(self.db, self.client_id)
        result = commutation_service.calculate(
            monthly_pension_reduction=target_monthly_pension_reduction,
            annuity_factor=annuity_factor,
            client_age=current_age or age_at_retirement,
            retirement_age=age_at_retirement,
            gender=gender,
            other_annual_income=other_annual_income,
        )

        if not result.get('success'):
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": result.get('error', 'שגיאה בחישוב ההיוון'),
            }

        # בניית הסבר מפורט
        explanation_lines = [
            f"💰 **חישוב היוון קצבה**",
            f"",
            f"**פרטי ההיוון:**",
            f"  • הפחתה חודשית מהקצבה: {result['monthly_pension_reduction']:,.0f} ₪",
            f"  • מקדם קצבה: {result['annuity_factor']:.1f}",
            f"  • גיל פרישה: {age_at_retirement}",
            f"",
            f"**סכום ההיוון:**",
            f"  • סכום ברוטו: {result['lump_sum_gross']:,.0f} ₪",
            f"  • מס הכנסה על ההיוון: {result['tax_on_lump_sum']:,.0f} ₪ ({result['effective_tax_rate']:.1f}%)",
            f"  • **סכום נטו: {result['lump_sum_net']:,.0f} ₪**",
            f"",
            f"**השוואה כלכלית:**",
            f"  • קצבה שנתית שתאבד: {result['annual_pension_lost']:,.0f} ₪",
            f"  • סה\"כ קצבה שתאבד ב-30 שנה: {result['total_pension_lost_30_years']:,.0f} ₪",
            f"  • ערך נוכחי (NPV) של הקצבה שתאבד: {result['npv_pension_lost']:,.0f} ₪",
            f"",
        ]

        comparison = result.get('comparison', {})
        if comparison.get('recommendation') == 'lump_sum':
            explanation_lines.append(f"✅ **המלצה:** ההיוון משתלם כלכלית (הפרש: {comparison['difference']:,.0f} ₪ לטובתך)")
        else:
            explanation_lines.append(f"⚠️ **המלצה:** הקצבה משתלמת יותר כלכלית (הפרש: {abs(comparison['difference']):,.0f} ₪)")

        explanation_lines.extend([
            f"",
            f"**💡 שים לב:**",
            f"  • ההיוון מתאים למי שצריך סכום גדול מיידי (למשל לפירעון משכנתא)",
            f"  • הקצבה מתאימה למי שמעדיף הכנסה קבועה לכל החיים",
        ])

        return {
            "success": True,
            "tool_name": "CALCULATE_PENSION_COMMUTATION",
            "result": {
                "retirement_date": retirement_date,
                "retirement_age": age_at_retirement,
                "monthly_pension_reduction": result['monthly_pension_reduction'],
                "annuity_factor": result['annuity_factor'],
                "lump_sum_gross": result['lump_sum_gross'],
                "tax_on_lump_sum": result['tax_on_lump_sum'],
                "lump_sum_net": result['lump_sum_net'],
                "effective_tax_rate": result['effective_tax_rate'],
                "annual_pension_lost": result['annual_pension_lost'],
                "npv_pension_lost": result['npv_pension_lost'],
                "recommendation": comparison.get('recommendation', 'unknown'),
            },
            "explanation": "\n".join(explanation_lines),
        }

    def calculate_capital_withdrawal_tax(
        self,
        withdrawal_amount_gross: float,
        withdrawal_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        מחשב מס על משיכת כספי הון (קופת גמל, קרן השתלמות, תגמולים נזילים).
        
        Args:
            withdrawal_amount_gross: סכום המשיכה ברוטו
            withdrawal_year: שנת המשיכה המתוכננת
            
        Returns:
            Dict עם סכום המס, הסכום נטו, ושיעור המס האפקטיבי
        """
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
                "result": {},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        # הכנסה שנתית אחרת (אם יש)
        other_annual_income = 0.0
        if client.annual_salary:
            other_annual_income = float(client.annual_salary)

        if withdrawal_year is None:
            withdrawal_year = date.today().year

        # ביצוע חישוב המס
        withdrawal_service = CapitalWithdrawalService(self.db, self.client_id)
        result = withdrawal_service.calculate(
            withdrawal_amount_gross=withdrawal_amount_gross,
            withdrawal_year=withdrawal_year,
            other_annual_income=other_annual_income,
        )

        # בניית הסבר מפורט
        explanation_lines = [
            f"💰 **חישוב מס על משיכת כספי הון**",
            f"",
            f"**פרטי המשיכה:**",
            f"  • סכום המשיכה ברוטו: {result['withdrawal_amount_gross']:,.0f} ₪",
            f"  • שנת המשיכה: {result['withdrawal_year']}",
        ]

        if other_annual_income > 0:
            explanation_lines.append(f"  • הכנסה שנתית אחרת: {other_annual_income:,.0f} ₪")

        explanation_lines.extend([
            f"",
            f"**חישוב המס:**",
            f"  • מס הכנסה: {result['tax_amount']:,.0f} ₪",
            f"  • שיעור מס אפקטיבי: {result['effective_tax_rate']:.1f}%",
            f"  • מדרגת מס שולית: {result['marginal_tax_rate']:.0f}%",
            f"",
            f"**סכום נטו:**",
            f"  • **תקבל לידיים: {result['net_amount']:,.0f} ₪**",
            f"",
            f"**💡 שים לב:**",
            f"  • החישוב מתייחס למס הכנסה בלבד (ללא ביטוח לאומי/בריאות)",
            f"  • המס מחושב לפי מדרגות המס לשנת {result['withdrawal_year']}",
        ])

        if other_annual_income > 0:
            explanation_lines.append(f"  • המס מחושב בהתחשב בהכנסה השנתית הנוספת שלך")

        return {
            "success": True,
            "tool_name": "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
            "result": {
                "withdrawal_amount_gross": result['withdrawal_amount_gross'],
                "withdrawal_year": result['withdrawal_year'],
                "tax_amount": result['tax_amount'],
                "net_amount": result['net_amount'],
                "effective_tax_rate": result['effective_tax_rate'],
                "marginal_tax_rate": result['marginal_tax_rate'],
            },
            "explanation": "\n".join(explanation_lines),
        }

    def calculate_tax_spread_benefit(
        self,
        gross_amount: float,
        spread_years: int,
    ) -> Dict[str, Any]:
        """
        מחשב את הטבת המס בפריסה על מספר שנים.
        משווה בין משיכה מיידית (מס מלא) לבין פריסת מס על מספר שנים.
        
        Args:
            gross_amount: סכום ברוטו חייב במס
            spread_years: מספר שנות פריסה (1-6)
            
        Returns:
            Dict עם השוואת מס מיידי מול פריסה והטבת המס
        """
        from decimal import Decimal
        from app.services.capital_asset.tax_calculator import TaxCalculator
        
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CALCULATE_TAX_SPREAD_BENEFIT",
                "result": {},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        # וידוא שנות פריסה תקינות
        if spread_years < 1 or spread_years > 6:
            return {
                "success": False,
                "tool_name": "CALCULATE_TAX_SPREAD_BENEFIT",
                "result": {},
                "explanation": f"מספר שנות פריסה לא תקין ({spread_years}). יש לבחור בין 1 ל-6 שנים.",
            }

        # יצירת מחשבון מס
        tax_calculator = TaxCalculator()
        
        # חישוב מס מיידי (ללא פריסה)
        from app.models.capital_asset import TaxTreatment
        immediate_result = tax_calculator.calculate(
            gross_amount=Decimal(str(gross_amount)),
            tax_treatment=TaxTreatment.TAXABLE,
        )
        
        # חישוב מס עם פריסה
        spread_result = tax_calculator.calculate(
            gross_amount=Decimal(str(gross_amount)),
            tax_treatment=TaxTreatment.TAX_SPREAD,
            spread_years=spread_years,
        )
        
        # חישוב מס מיידי לפי מדרגות (כי TAXABLE מחזיר 0)
        from app.services.tax_data.tax_brackets import TaxBracketsService
        current_year = date.today().year
        tax_brackets = TaxBracketsService.get_tax_brackets(current_year)
        
        # חישוב מס מיידי לפי מדרגות
        immediate_tax = 0.0
        remaining = float(gross_amount)
        for bracket in tax_brackets:
            if remaining <= 0:
                break
            bracket_min = bracket["min_income"]
            bracket_max = bracket["max_income"]
            rate = bracket["rate"]
            taxable_in_bracket = min(remaining, bracket_max - bracket_min + 1)
            if taxable_in_bracket > 0:
                immediate_tax += taxable_in_bracket * rate
                remaining -= taxable_in_bracket
        
        # חישוב מס עם פריסה לפי מדרגות
        annual_portion = float(gross_amount) / spread_years
        annual_tax = 0.0
        remaining = annual_portion
        for bracket in tax_brackets:
            if remaining <= 0:
                break
            bracket_min = bracket["min_income"]
            bracket_max = bracket["max_income"]
            rate = bracket["rate"]
            taxable_in_bracket = min(remaining, bracket_max - bracket_min + 1)
            if taxable_in_bracket > 0:
                annual_tax += taxable_in_bracket * rate
                remaining -= taxable_in_bracket
        
        spread_total_tax = annual_tax * spread_years
        
        # חישוב הטבת המס
        tax_benefit = immediate_tax - spread_total_tax
        benefit_percentage = (tax_benefit / immediate_tax * 100) if immediate_tax > 0 else 0
        
        # חישוב שיעורי מס אפקטיביים
        immediate_effective_rate = (immediate_tax / float(gross_amount) * 100) if gross_amount > 0 else 0
        spread_effective_rate = (spread_total_tax / float(gross_amount) * 100) if gross_amount > 0 else 0
        
        # בניית הסבר מפורט
        explanation_lines = [
            f"📊 **ניתוח פריסת מס**",
            f"",
            f"**פרטי הסכום:**",
            f"  • סכום ברוטו חייב במס: {gross_amount:,.0f} ₪",
            f"  • שנות פריסה: {spread_years}",
            f"  • חלק שנתי: {annual_portion:,.0f} ₪",
            f"",
            f"**השוואת מס:**",
            f"",
            f"| אופציה | מס כולל | שיעור אפקטיבי | נטו |",
            f"|--------|---------|---------------|-----|",
            f"| משיכה מיידית | {immediate_tax:,.0f} ₪ | {immediate_effective_rate:.1f}% | {gross_amount - immediate_tax:,.0f} ₪ |",
            f"| פריסה ל-{spread_years} שנים | {spread_total_tax:,.0f} ₪ | {spread_effective_rate:.1f}% | {gross_amount - spread_total_tax:,.0f} ₪ |",
            f"",
            f"**💰 הטבת המס בפריסה:**",
            f"  • חיסכון במס: **{tax_benefit:,.0f} ₪** ({benefit_percentage:.1f}%)",
            f"  • תוספת נטו: **{tax_benefit:,.0f} ₪**",
            f"",
        ]
        
        if tax_benefit > 0:
            explanation_lines.append(f"**💡 המלצה:** פריסה ל-{spread_years} שנים חוסכת {tax_benefit:,.0f} ₪ במס.")
        else:
            explanation_lines.append(f"**💡 הערה:** אין הטבה משמעותית בפריסה במקרה זה.")
        
        return {
            "success": True,
            "tool_name": "CALCULATE_TAX_SPREAD_BENEFIT",
            "result": {
                "gross_amount": gross_amount,
                "spread_years": spread_years,
                "annual_portion": annual_portion,
                "immediate_tax": immediate_tax,
                "immediate_net": gross_amount - immediate_tax,
                "immediate_effective_rate": immediate_effective_rate,
                "spread_total_tax": spread_total_tax,
                "spread_net": gross_amount - spread_total_tax,
                "spread_effective_rate": spread_effective_rate,
                "annual_tax": annual_tax,
                "tax_benefit": tax_benefit,
                "benefit_percentage": benefit_percentage,
            },
            "explanation": "\n".join(explanation_lines),
        }
