import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.pension_portfolio.conversion_rules import (
    COMPONENT_RULES,
    rule_for_tagmulim_by_product_type,
)
from app.services.retirement.constants import PENSION_COEFFICIENT
from app.services.retirement_age_service import get_retirement_age_simple
from app.utils.date_serializer import parse_date_flexible

logger = logging.getLogger("app.llm_agent_tools")


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
            "field": "פיצויים_שלא_עברו_התחשבנות",
            "label": "פיצויים שלא עברו התחשבנות",
            "tax_treatment": "taxable",
            "priority_bucket": 2,
            "action_needed": "requires_termination",
        },
        {
            "field": "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
            "label": "פיצויים (מעסיקים קודמים - רצף זכויות)",
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
        coeff_source_table: Optional[str] = None
        fallback_used = False
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
            try:
                coeff_source_table = (
                    str(coeff.get("source_table") or "").strip()
                    if isinstance(coeff, dict)
                    else None
                )
            except Exception:
                coeff_source_table = None
            annuity_factor = float(coeff.get("factor_value") or annuity_factor)
        except Exception:
            annuity_factor = float(PENSION_COEFFICIENT)
            fallback_used = True

        if annuity_factor <= 0:
            annuity_factor = float(PENSION_COEFFICIENT)

        if (not coeff_source_table) or (str(coeff_source_table).strip() == "default"):
            if annuity_factor == float(PENSION_COEFFICIENT):
                fallback_used = True

        if "השתלמות" in str(product_type) or "השתלמות" in str(plan_name):
            balance_candidates = [
                acc.get("קרן_השתלמות"),
                acc.get("education_fund"),
                acc.get("יתרה"),
                acc.get("balance"),
                acc.get("current_balance"),
            ]
            balance = 0.0
            for raw in balance_candidates:
                balance = _safe_float(raw)
                if balance > 0:
                    break
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
                    "coeff_source_table": coeff_source_table,
                    "fallback_used": bool(fallback_used),
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
                nested_components = acc.get("components")
                if isinstance(nested_components, dict):
                    amount = _safe_float(nested_components.get(field, 0))
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
                    "coeff_source_table": coeff_source_table,
                    "fallback_used": bool(fallback_used),
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
        balance_candidates = [
            acc.get("יתרה"),
            acc.get("balance"),
            acc.get("current_balance"),
        ]
        balance = 0.0
        for raw in balance_candidates:
            balance = _safe_float(raw)
            if balance > 0:
                break
        if balance <= 0:
            continue
        potential_pension = balance / annuity_factor

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
                "coeff_source_table": coeff_source_table,
                "fallback_used": bool(fallback_used),
                "monthly_pension": potential_pension,
                "tax_treatment": "exempt"
                if ("השתלמות" in str(product_type) or "השתלמות" in str(plan_name))
                else "taxable",
                "priority_bucket": 5
                if ("השתלמות" in str(product_type) or "השתלמות" in str(plan_name))
                else 4,
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
    return _get_pension_sources_from_portfolio(
        self,
        pension_portfolio=pension_portfolio,
        client=client,
        retirement_age=retirement_age,
        retirement_date=retirement_date,
        retirement_year=retirement_year,
    )
