import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("app.llm_agent_tools")


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
            prev_age = sorted_ages[i - 1]
            prev_pension = results_by_age[prev_age].get("total_pension_monthly", 0)
            change_from_prev = pension - prev_pension

        sensitivity_analysis.append(
            {
                "age": age,
                "pension": pension,
                "capital": capital,
                "change_from_prev": change_from_prev,
                "meets_target": pension >= target,
            }
        )

    # בניית הסבר מפורט
    explanation_parts: list[str] = []

    if best_achieving:
        explanation_parts.append(f"✅ **נמצא תרחיש שמגיע ליעד של {target:,.0f} ₪/חודש!**")
        explanation_parts.append("")
        explanation_parts.append(f"**🎯 התרחיש המומלץ:**")
        explanation_parts.append(f"  • גיל פרישה: {best_achieving['retirement_age']}")
        explanation_parts.append(f"  • תרחיש: {best_achieving['scenario_name']}")
        explanation_parts.append(
            f"  • קצבה: {best_achieving['total_pension_monthly']:,.0f} ₪/חודש"
        )
        explanation_parts.append(f"  • הון: {best_achieving.get('total_capital', 0):,.0f} ₪")
        explanation_parts.append(f"  • NPV: {best_achieving['estimated_npv']:,.0f} ₪")
    else:
        gap = target - best_overall.get("total_pension_monthly", 0)
        explanation_parts.append(f"❌ **לא נמצא תרחיש שמגיע ליעד של {target:,.0f} ₪/חודש**")
        explanation_parts.append("")
        explanation_parts.append(f"**📊 התרחיש הטוב ביותר:**")
        explanation_parts.append(f"  • גיל פרישה: {best_overall['retirement_age']}")
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
        explanation_parts.append(f"  {marker} גיל {item['age']}: {item['pension']:,.0f} ₪{change_text}")

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
                explanation_parts.append(f"  • דחיית פרישה מעבר לגיל {last_item['age']} עשויה לשפר את הקצבה")
        explanation_parts.append(f"  • הגדלת ההפקדות השוטפות תקטין את הפער")

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
