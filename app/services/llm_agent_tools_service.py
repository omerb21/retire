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
from app.models.additional_income import AdditionalIncome
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
from app.services.llm_agent_tools.tax_tools import TaxToolsMixin
from app.services.llm_agent_tools.portfolio_tools import PortfolioToolsMixin
from app.services.llm_agent_tools.scenarios_tools import ScenariosToolsMixin
from app.services.llm_agent_tools.fixation_tools import FixationToolsMixin
from app.services.llm_agent_tools import RetirementCashflowToolsMixin
from app.services.llm_agent_tools import CommutationToolsMixin
from app.services.llm_agent_tools import DataCompletenessToolsMixin
from app.services.llm_agent_tools import TaxProjectionToolsMixin
from app.services.llm_agent_tools import GrossWithdrawalToolsMixin

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


class AgentToolsService(TaxToolsMixin, PortfolioToolsMixin, ScenariosToolsMixin, FixationToolsMixin, RetirementCashflowToolsMixin, CommutationToolsMixin, DataCompletenessToolsMixin, TaxProjectionToolsMixin, GrossWithdrawalToolsMixin):
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

            pension_sources.append({
                "source_type": "pension_fund_from_portfolio",
                "source_id": account_number,
                "account_number": account_number,
                "source_name": plan_name,
                "fund_type": product_type or "unknown",
                "start_date": start_date_raw,
                "balance": balance,
                "annuity_factor": annuity_factor,
                "monthly_pension": potential_pension,
                "tax_treatment": "exempt" if ("השתלמות" in str(product_type) or "השתלמות" in str(plan_name)) else "taxable",
                "priority_bucket": 5 if ("השתלמות" in str(product_type) or "השתלמות" in str(plan_name)) else 4,
                "action_needed": "convert_to_pension",
                "action_description": f"המרת יתרה של {balance:,.0f} ₪ לקצבה של {potential_pension:,.0f} ₪/חודש",
            })

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
            def _gross_for_net_target(target_net: float) -> tuple[Optional[float], Optional[dict], Optional[str]]:
                try:
                    target_net_val = float(target_net or 0)
                except Exception:
                    target_net_val = 0.0
                if target_net_val <= 0:
                    return None, None, "invalid_target_net"

                def _net_from_gross(gross: float) -> tuple[Optional[float], Optional[dict], Optional[str]]:
                    try:
                        proj = self.get_tax_projection(monthly_pension=float(gross))
                        if not (isinstance(proj, dict) and isinstance(proj.get("result"), dict)):
                            return None, None, "invalid_tax_projection_response"
                        res = proj.get("result")
                        monthly_tax = res.get("monthly_tax")
                        try:
                            tax_val = float(monthly_tax or 0)
                        except Exception:
                            tax_val = 0.0
                        return float(gross) - tax_val, res, None
                    except Exception as e:
                        return None, None, str(e) or "tax_projection_failed"

                low = max(1000.0, target_net_val)
                low_net, low_res, low_err = _net_from_gross(low)
                if low_net is None:
                    return None, None, low_err
                if low_net >= target_net_val:
                    return low, low_res, None

                high = low
                high_net = low_net
                high_res: Optional[dict] = low_res
                high_err: Optional[str] = None
                for _ in range(16):
                    high = min(high * 1.5, 500_000.0)
                    high_net, high_res, high_err = _net_from_gross(high)
                    if high_net is not None and high_net >= target_net_val:
                        break
                if high_net is None or high_net < target_net_val:
                    return None, None, high_err

                best_gross = high
                best_res = high_res
                for _ in range(30):
                    mid = (low + high) / 2.0
                    mid_net, mid_res, _ = _net_from_gross(mid)
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
                return best_gross, best_res, None

            computed_gross, tax_result, gross_err = _gross_for_net_target(target)
            if computed_gross is None:
                err = (gross_err or "לא ניתן לחשב ברוטו נדרש ליעד נטו (כשל בהערכת מס)").strip()
                return {
                    "success": False,
                    "tool_name": "BUILD_TARGET_PENSION_PLAN",
                    "result": {},
                    "explanation": (
                        "לא ניתן לתכנן יעד קצבה נטו ללא הערכת מס תקינה. "
                        "הערכת המס נכשלה ולכן לא ניתן להמיר יעד נטו לברוטו נדרש. "
                        f"פרטי שגיאה: {err}"
                    ),
                }

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
        if target_is_net and estimated_net is None:
            target_achieved_net = False

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
