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
from app.services.retirement import RetirementScenariosBuilder
from app.services.retirement.constants import PENSION_COEFFICIENT, MINIMUM_PENSION
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.tax_calculator import TaxCalculator
from app.schemas.tax_schemas import TaxCalculationInput, PersonalDetails
from app.services.rights_fixation.exemption_caps import get_monthly_cap, get_exemption_percentage
from datetime import date

logger = logging.getLogger("app.llm_agent_tools")


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
            builder = RetirementScenariosBuilder(
                self.db,
                self.client_id,
                retirement_age,
                pension_portfolio,
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
                        "pension_portfolio": pension_portfolio,
                        "include_current_employer_termination": include_current_employer_termination,
                    }),
                    summary_results=json.dumps(scenario_data),
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

    def _build_sources_from_pension_portfolio(
        self,
        pension_portfolio: List[Dict[str, Any]],
        client: Client,
        retirement_age: int,
        retirement_date: date,
        retirement_year: int,
    ) -> List[Dict[str, Any]]:
        pension_sources: List[Dict[str, Any]] = []

        component_fields = [
            "פיצויים_מעסיק_נוכחי",
            "פיצויים_לאחר_התחשבנות",
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
            "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
            "תגמולי_עובד_עד_2000",
            "תגמולי_עובד_אחרי_2000",
            "תגמולי_עובד_אחרי_2008_לא_משלמת",
            "תגמולי_מעביד_עד_2000",
            "תגמולי_מעביד_אחרי_2000",
            "תגמולי_מעביד_אחרי_2008_לא_משלמת",
        ]

        for account in pension_portfolio:
            try:
                balance = sum(float(account.get(field, 0) or 0) for field in component_fields)
            except Exception:
                balance = 0.0

            # Fallback לשדה יתרה כללי אם אין רכיבים מפורטים
            if balance <= 0:
                try:
                    balance = float(account.get("יתרה", 0) or 0)
                except Exception:
                    balance = 0.0

            if balance <= 0:
                continue

            product_type = account.get("סוג_מוצר") or ""
            tax_treatment = "exempt" if "השתלמות" in product_type else "taxable"

            annuity_factor = float(PENSION_COEFFICIENT)
            try:
                start_date_raw = account.get("תאריך_התחלה")
                start_date_obj: Optional[date] = None
                if isinstance(start_date_raw, str) and start_date_raw:
                    try:
                        start_date_obj = date.fromisoformat(start_date_raw)
                    except ValueError:
                        start_date_obj = None

                coeff = get_annuity_coefficient(
                    product_type=product_type,
                    start_date=start_date_obj or date(retirement_year, 1, 1),
                    gender=getattr(client, "gender", None) or "זכר",
                    retirement_age=retirement_age or 67,
                    company_name=account.get("חברה_מנהלת"),
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

            potential_pension = balance / annuity_factor

            pension_sources.append(
                {
                    "source_type": "pension_fund_from_portfolio",
                    "source_id": account.get("מספר_חשבון") or None,
                    "source_name": account.get("שם_תכנית", "תכנית ללא שם"),
                    "fund_type": product_type or "unknown",
                    "balance": balance,
                    "annuity_factor": annuity_factor,
                    "monthly_pension": potential_pension,
                    "tax_treatment": tax_treatment,
                    "action_needed": "convert_to_pension",
                    "action_description": f"המרת יתרה של {balance:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                }
            )

        return pension_sources

    def build_target_pension_plan(
        self,
        target_monthly_pension: float,
        retirement_age: Optional[int] = None,
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

        # קביעת גיל פרישה
        current_age = client.get_age()
        if retirement_age is None:
            retirement_age = max(current_age + 1, 67) if current_age else 67
        
        if retirement_age < current_age:
            return {
                "success": False,
                "tool_name": "BUILD_TARGET_PENSION_PLAN",
                "result": {},
                "explanation": f"גיל הפרישה ({retirement_age}) לא יכול להיות נמוך מהגיל הנוכחי ({current_age}).",
            }

        # חישוב תאריך פרישה
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
                    "source_name": ca.asset_name,
                    "fund_type": ca.asset_type,
                    "balance": value,
                    "annuity_factor": PENSION_COEFFICIENT,
                    "monthly_pension": potential_pension,
                    "tax_treatment": ca.tax_treatment or "taxable",
                    "action_needed": "convert_to_pension",
                    "action_description": f"המרת הון של {value:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
                })

        # Fallback: אם אין עדיין מקורות קצבה בטבלאות, ננסה להשתמש בתיק הפנסיוני
        # מחפשים תרחיש שיש בו pension_portfolio תקין (לא רק את האחרון, כי הסוכן עלול לדרוס עם None)
        if not pension_sources:
            logger.info(
                "BUILD_TARGET_PENSION_PLAN: No PensionFund/CapitalAsset records found for client %s, "
                "trying fallback to saved scenarios...",
                self.client_id,
            )
            try:
                all_scenarios = (
                    self.db.query(Scenario)
                    .filter(Scenario.client_id == self.client_id)
                    .order_by(Scenario.created_at.desc())
                    .limit(20)
                    .all()
                )
                logger.info(
                    "BUILD_TARGET_PENSION_PLAN: Found %d scenarios for client %s",
                    len(all_scenarios),
                    self.client_id,
                )

                pension_portfolio_data: Any = None
                for scenario in all_scenarios:
                    if not scenario.parameters:
                        logger.debug("Scenario %s has no parameters", scenario.id)
                        continue
                    try:
                        params = json.loads(scenario.parameters)
                        portfolio = params.get("pension_portfolio")
                        if isinstance(portfolio, list) and portfolio:
                            pension_portfolio_data = portfolio
                            logger.info(
                                "BUILD_TARGET_PENSION_PLAN: Found pension_portfolio in scenario %s with %d accounts",
                                scenario.id,
                                len(portfolio),
                            )
                            break
                        else:
                            logger.debug(
                                "Scenario %s has pension_portfolio=%s (type=%s)",
                                scenario.id,
                                "None" if portfolio is None else f"list with {len(portfolio) if isinstance(portfolio, list) else 'N/A'} items",
                                type(portfolio).__name__,
                            )
                    except Exception as parse_err:
                        logger.debug(
                            "Failed to parse parameters from scenario %s: %s",
                            scenario.id,
                            parse_err,
                        )

                if isinstance(pension_portfolio_data, list) and pension_portfolio_data:
                    portfolio_sources = self._build_sources_from_pension_portfolio(
                        pension_portfolio=pension_portfolio_data,
                        client=client,
                        retirement_age=retirement_age,
                        retirement_date=retirement_date,
                        retirement_year=retirement_year,
                    )
                    logger.info(
                        "BUILD_TARGET_PENSION_PLAN: Built %d pension sources from portfolio",
                        len(portfolio_sources),
                    )
                    pension_sources.extend(portfolio_sources)
                else:
                    logger.warning(
                        "BUILD_TARGET_PENSION_PLAN: No valid pension_portfolio found in any scenario for client %s",
                        self.client_id,
                    )
            except Exception as portfolio_err:
                logger.warning(
                    "Failed to build pension sources from saved pension portfolio: %s",
                    portfolio_err,
                )

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

        # שלב 2: מיון לפי איכות (מקדם נמוך = טוב יותר)
        # קצבאות קיימות קודם, אחר כך לפי מקדם
        pension_sources.sort(key=lambda x: (
            0 if x["action_needed"] == "none" else 1,  # קצבאות קיימות קודם
            x["annuity_factor"],  # מקדם נמוך = טוב יותר
        ))

        # שלב 3: בניית התכנית - צבירת קצבה עד היעד
        plan_steps = []
        accumulated_pension = 0.0
        remaining_capital = 0.0
        sources_used = []
        sources_not_used = []

        for source in pension_sources:
            if accumulated_pension >= target:
                # כבר הגענו ליעד - השאר נשאר כהון
                sources_not_used.append(source)
                remaining_capital += source["balance"]
                continue

            pension_from_source = source["monthly_pension"]
            needed = target - accumulated_pension

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
        target_achieved = accumulated_pension >= target
        gap = max(0, target - accumulated_pension)

        # בניית יתרונות וחסרונות
        advantages = []
        disadvantages = []

        if target_achieved:
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

        if not target_achieved:
            disadvantages.append(f"לא ניתן להגיע ליעד - חסרים {gap:,.0f} ₪ לחודש")

        # בניית הסבר מפורט לסוכן
        explanation_parts: list[str] = []
        
        if target_achieved:
            explanation_parts.append(
                f"✅ **התכנית הושלמה בהצלחה** - ניתן להגיע לקצבה של {target:,.0f} ₪/חודש בגיל {retirement_age}."
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
                f"❌ **לא ניתן להגיע ליעד** של {target:,.0f} ₪/חודש עם המקורות הקיימים."
            )
            explanation_parts.append("")
            explanation_parts.append(f"📊 **המצב הנוכחי:**")
            explanation_parts.append(f"  • קצבה מקסימלית אפשרית: {accumulated_pension:,.0f} ₪/חודש")
            explanation_parts.append(f"  • פער מהיעד: {gap:,.0f} ₪/חודש")
            explanation_parts.append(f"  • אחוז מהיעד: {(accumulated_pension/target*100):.0f}%")
            
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
                "retirement_age": retirement_age,
                "target_achieved": target_achieved,
                "accumulated_pension": accumulated_pension,
                "gap_to_target": gap,
                "remaining_capital": remaining_capital,
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
        try:
            tax_year = datetime.strptime(retirement_date, "%Y-%m-%d").year if retirement_date else date.today().year
        except ValueError:
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
            products.append({
                "Product Name": pf.fund_name,
                "Managing Company": pf.managing_company or "לא ידוע",
                "Type": f"פנסיוני ({pf.fund_type or 'כללי'})",
                "Accumulated Balance": pf.balance or 0,
                "Monthly Deposit": pf.monthly_deposit or 0,
                "Management Fee": f"{pf.management_fee_accumulation or 0}% מצבירה",
                "Status": "פעיל" if pf.is_active else "לא פעיל",
            })

        for ca in capital_assets:
            products.append({
                "Product Name": ca.asset_name,
                "Managing Company": ca.managing_company or "לא ידוע",
                "Type": f"הוני ({ca.asset_type or 'כללי'})",
                "Accumulated Balance": ca.current_balance or 0,
                "Monthly Deposit": ca.monthly_deposit or 0,
                "Management Fee": f"{ca.management_fee_accumulation or 0}% מצבירה",
                "Status": "פעיל" if ca.is_active else "לא פעיל",
            })

        # מיון לפי יתרה יורדת
        products.sort(key=lambda x: x["Accumulated Balance"], reverse=True)

        total_balance = sum(p["Accumulated Balance"] for p in products)
        total_deposit = sum(p["Monthly Deposit"] for p in products)

        logger.info(
            "GET_PENSION_PRODUCTS: returning %d products (total_balance=%s, total_monthly_deposit=%s) for client %s",
            len(products),
            total_balance,
            total_deposit,
            self.client_id,
        )

        # יצירת הסבר טקסטואלי קצר לשימוש המודל
        explanation = (
            f"נמצאו {len(products)} מוצרים בתיק.\n"
            f"סה\"כ צבירה: {total_balance:,.0f} ₪.\n"
            f"סה\"כ הפקדה חודשית: {total_deposit:,.0f} ₪."
        )

        return {
            "success": True,
            "tool_name": "GET_PENSION_PRODUCTS",
            "result": {
                "products": products,
                "total_balance": total_balance,
                "total_monthly_deposit": total_deposit,
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
            target_date = datetime.strptime(retirement_date, "%Y-%m-%d").date()
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
        
        # אם הוזרקו נתוני תיק פנסיוני מה-UI, נשתמש בהם בלבד
        if self.pension_portfolio_data and len(self.pension_portfolio_data) > 0:
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
                product_type_lower = product_type_raw.lower()
                name = acc.שם_תכנית or "ללא שם"

                # ===== לוגיקת סיווג משופרת (Run 22) =====
                # מוצרים שהם תמיד הוניים (לא קצבתיים):
                is_pure_capital = (
                    "קרן השתלמות" in product_type_lower
                    or "גמל להשקעה" in product_type_lower
                    or "חיסכון פיננסי" in product_type_lower
                )

                # מוצרים שהם תמיד קצבתיים (גם אם מכילים 'חיסכון' או 'ביטוח'):
                is_pension_or_annuity = (
                    product_type_raw == "פוליסת ביטוח חיים משולב חיסכון"  # המוצר הספציפי עם 6M
                    or "קצבה" in product_type_lower
                    or "ביטוח מנהלים" in product_type_lower
                    or "קרן פנסיה" in product_type_lower
                    or "פנסיה" in product_type_lower
                    or "ביטוח חיים" in product_type_lower  # פוליסות ביטוח חיים הן קצבתיות
                )

                # לוגיקת הסיווג הסופית:
                # אם זה מוצר קצבתי מובהק - תמיד pension_fund
                # אם זה מוצר הוני טהור ולא קצבתי - capital_asset
                # אחרת (ברירת מחדל) - pension_fund
                if is_pension_or_annuity:
                    is_capital = False
                elif is_pure_capital:
                    is_capital = True
                else:
                    # ברירת מחדל: מוצר פנסיוני (לא הוני)
                    is_capital = False

                classification = "capital_asset" if is_capital else "pension_fund"
                logger.info(
                    "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Injected account classified as %s - name=%s, type=%s, balance=%.2f",
                    classification,
                    name,
                    product_type_raw,
                    balance,
                )

                if is_capital:
                    ca = CapitalAsset(
                        client_id=self.client_id,
                        asset_name=name,
                        asset_type=acc.סוג_מוצר,
                        current_value=balance,  # Fixed: current_balance -> current_value
                        # Required fields defaults
                        annual_return_rate=0,
                        payment_frequency='monthly',
                        start_date=date.today(),
                        # Removed managing_company as it is not in the model
                    )
                    capital_assets.append(ca)
                else:
                    pf = PensionFund(
                        client_id=self.client_id,
                        fund_name=name,
                        fund_type=acc.סוג_מוצר,
                        balance=balance,
                        pension_amount=0,  # הנחה: בנתוני מסלקה גולמיים אין שדה קצבה חודשית מפורש לרוב
                        input_mode="manual",  # Required field
                        # Removed managing_company as it is not in the model
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
                    (ca.current_value or 0.0),
                    (ca.monthly_income or 0.0),
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
        exempt_pension_monthly = 0.0
        exemption_percentage = 0.0
        monthly_cap = 0.0

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

            # חישוב נטו חודשי
            annual_net_income = tax_result.net_income
            monthly_net_pension = annual_net_income / 12
            monthly_tax_deduction = (tax_result.net_tax / 12)
            monthly_health_tax = (tax_result.health_tax / 12)
            monthly_income_tax = (tax_result.income_tax / 12)

            logger.info(
                "TAX ANALYSIS: Gross annual pension=%.2f, Net annual=%.2f, Tax=%.2f, Health=%.2f",
                annual_pension_gross, annual_net_income, tax_result.income_tax, tax_result.health_tax
            )
            logger.info(
                "TAX ANALYSIS: Monthly gross=%.2f, Monthly net=%.2f, Monthly tax deduction=%.2f, Exempt=%.2f",
                total_pension_income, monthly_net_pension, monthly_tax_deduction, exempt_pension_monthly
            )

        except Exception as e:
            logger.warning("TAX ANALYSIS: Failed to calculate tax, using gross as net: %s", e)
            monthly_net_pension = total_pension_income
            monthly_tax_deduction = 0.0
            monthly_health_tax = 0.0
            monthly_income_tax = 0.0

        # הכנסה מובטחת נטו (כולל ביטוח לאומי שהוא פטור ממס)
        total_guaranteed_income_net = monthly_net_pension + social_security_amount
        total_guaranteed_income = total_guaranteed_income_gross  # לשמירה על תאימות לאחור

        # 5. ניתוח גירעון (Gap Analysis) - מבוסס על נטו
        gap = desired_monthly_income - total_guaranteed_income
        
        # 6. חישוב הון זמין
        # שימוש ברשימה המסוננת שכבר יצרנו
        # capital_assets כבר חושב למעלה
        total_capital_available = sum((ca.current_value or 0) for ca in capital_assets)
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
            f"📊 **ניתוח מס:**",
            f"   מס הכנסה: {monthly_income_tax:,.0f} ₪/חודש",
            f"   מס בריאות: {monthly_health_tax:,.0f} ₪/חודש",
            f"   סה\"כ ניכויי מס: {monthly_tax_deduction:,.0f} ₪/חודש",
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
