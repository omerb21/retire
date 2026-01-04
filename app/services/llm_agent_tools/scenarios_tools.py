import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.llm_agent_tools")


def _to_jsonable(value: Any) -> Any:
    from datetime import date, datetime
    from decimal import Decimal

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


class ScenariosToolsMixin:
    def get_saved_scenarios_summary(self, retirement_age: Optional[int] = None) -> Dict[str, Any]:
        """מחזיר סיכום של התרחישים השמורים"""
        from app.models.scenario import Scenario

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
        from app.models.scenario import Scenario
        from app.services.retirement import RetirementScenariosBuilder

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
