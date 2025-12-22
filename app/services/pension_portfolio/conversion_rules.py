from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConversionType(str, Enum):
    pension = "pension"
    capital_asset = "capital_asset"


class PensionPortfolioComponentField(str, Enum):
    severance_current_employer = "פיצויים_מעסיק_נוכחי"
    severance_after_settlement = "פיצויים_לאחר_התחשבנות"
    severance_not_settled = "פיצויים_שלא_עברו_התחשבנות"
    severance_prev_rights = "פיצויים_ממעסיקים_קודמים_רצף_זכויות"
    severance_prev_pension = "פיצויים_ממעסיקים_קודמים_רצף_קצבה"

    tagmulim_employee_to_2000 = "תגמולי_עובד_עד_2000"
    tagmulim_employer_to_2000 = "תגמולי_מעביד_עד_2000"
    tagmulim_employee_after_2000 = "תגמולי_עובד_אחרי_2000"
    tagmulim_employer_after_2000 = "תגמולי_מעביד_אחרי_2000"
    tagmulim_employee_after_2008_non_paying = "תגמולי_עובד_אחרי_2008_לא_משלמת"
    tagmulim_employer_after_2008_non_paying = "תגמולי_מעביד_אחרי_2008_לא_משלמת"

    education_fund_column = "קרן_השתלמות"

    tagmulim_aggregate = "תגמולים"


TaxTreatment = str


@dataclass(frozen=True)
class ComponentRule:
    can_convert_to_pension: bool
    can_convert_to_capital: bool
    pension_tax: TaxTreatment | None
    capital_tax: TaxTreatment | None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "pension": self.can_convert_to_pension,
            "capital_asset": self.can_convert_to_capital,
            "capital": self.can_convert_to_capital,
            "pension_tax": self.pension_tax,
            "capital_tax": self.capital_tax,
            "error": self.error,
        }


FIELD_DISPLAY: dict[str, str] = {
    PensionPortfolioComponentField.severance_current_employer.value: "פיצויים מעסיק נוכחי",
    PensionPortfolioComponentField.severance_after_settlement.value: "פיצויים לאחר התחשבנות",
    PensionPortfolioComponentField.severance_not_settled.value: "פיצויים שלא עברו התחשבנות",
    PensionPortfolioComponentField.severance_prev_rights.value: "פיצויים מעסיקים קודמים (רצף זכויות)",
    PensionPortfolioComponentField.severance_prev_pension.value: "פיצויים מעסיקים קודמים (רצף קצבה)",
    PensionPortfolioComponentField.tagmulim_employee_to_2000.value: "תגמולי עובד עד 2000",
    PensionPortfolioComponentField.tagmulim_employer_to_2000.value: "תגמולי מעביד עד 2000",
    PensionPortfolioComponentField.tagmulim_employee_after_2000.value: "תגמולי עובד אחרי 2000",
    PensionPortfolioComponentField.tagmulim_employer_after_2000.value: "תגמולי מעביד אחרי 2000",
    PensionPortfolioComponentField.tagmulim_employee_after_2008_non_paying.value: "תגמולי עובד אחרי 2008 (לא משלמת)",
    PensionPortfolioComponentField.tagmulim_employer_after_2008_non_paying.value: "תגמולי מעביד אחרי 2008 (לא משלמת)",
    PensionPortfolioComponentField.education_fund_column.value: "קרן השתלמות (עמודה)",
    PensionPortfolioComponentField.tagmulim_aggregate.value: "תגמולים (עמודה כללית)",
}


_COMPONENT_RULES_OBJ: dict[str, ComponentRule] = {
    PensionPortfolioComponentField.severance_current_employer.value: ComponentRule(
        can_convert_to_pension=False,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר כספים ממעסיק נוכחי. נדרש PROCESS_TERMINATION במסך מעסיק נוכחי.",
    ),
    PensionPortfolioComponentField.severance_after_settlement.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=True,
        pension_tax="exempt",
        capital_tax="capital_gains",
    ),
    PensionPortfolioComponentField.severance_not_settled.value: ComponentRule(
        can_convert_to_pension=False,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר כספים שלא עברו התחשבנות.",
    ),
    PensionPortfolioComponentField.severance_prev_rights.value: ComponentRule(
        can_convert_to_pension=False,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר כספים ברצף זכויות. נדרש טיפול חיצוני/התחשבנות.",
    ),
    PensionPortfolioComponentField.severance_prev_pension.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר רכיב זה להון.",
    ),
    PensionPortfolioComponentField.tagmulim_employee_to_2000.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=True,
        pension_tax="exempt",
        capital_tax="exempt",
    ),
    PensionPortfolioComponentField.tagmulim_employer_to_2000.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=True,
        pension_tax="exempt",
        capital_tax="exempt",
    ),
    PensionPortfolioComponentField.tagmulim_employee_after_2000.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר רכיב זה להון.",
    ),
    PensionPortfolioComponentField.tagmulim_employer_after_2000.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר רכיב זה להון.",
    ),
    PensionPortfolioComponentField.tagmulim_employee_after_2008_non_paying.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר רכיב זה להון.",
    ),
    PensionPortfolioComponentField.tagmulim_employer_after_2008_non_paying.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר רכיב זה להון.",
    ),
    PensionPortfolioComponentField.education_fund_column.value: ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=True,
        pension_tax="exempt",
        capital_tax="exempt",
    ),
}


COMPONENT_RULES: dict[str, dict[str, object]] = {
    k: v.as_dict() for k, v in _COMPONENT_RULES_OBJ.items()
}


def is_education_fund(product_type: str) -> bool:
    lowered = (product_type or "").lower()
    return (
        ("השתלמות" in lowered)
        or ("education_fund" in lowered)
        or ("klal_stud" in lowered)
    )


def is_investment_provident_fund(product_type: str) -> bool:
    lowered = (product_type or "").lower()
    return ("גמל להשקעה" in lowered) or ("investment_provident_fund" in lowered)


def is_regular_provident_fund(product_type: str) -> bool:
    lowered = (product_type or "").lower()
    if "provident_fund" in lowered or "savings_policy" in lowered:
        return True
    return ("קופת גמל" in lowered) and ("להשקעה" not in lowered)


def is_pension_or_insurance(product_type: str) -> bool:
    lowered = (product_type or "").lower()
    if "pension_fund" in lowered or "insurance_policy" in lowered:
        return True
    return ("קרן פנסיה" in lowered) or ("פנסיה" in lowered) or ("ביטוח" in lowered)


def rule_for_tagmulim_by_product_type(*, product_type: str) -> dict[str, object]:
    pt = (product_type or "").lower()

    if ("גמל להשקעה" in pt) or ("investment_provident_fund" in pt):
        return ComponentRule(
            can_convert_to_pension=True,
            can_convert_to_capital=True,
            pension_tax="exempt",
            capital_tax="capital_gains",
        ).as_dict()

    if is_education_fund(product_type):
        return ComponentRule(
            can_convert_to_pension=True,
            can_convert_to_capital=True,
            pension_tax="exempt",
            capital_tax="exempt",
        ).as_dict()

    if is_regular_provident_fund(product_type):
        return ComponentRule(
            can_convert_to_pension=True,
            can_convert_to_capital=True,
            pension_tax="exempt",
            capital_tax="exempt",
        ).as_dict()

    if is_pension_or_insurance(product_type):
        return ComponentRule(
            can_convert_to_pension=True,
            can_convert_to_capital=False,
            pension_tax="taxable",
            capital_tax=None,
            error="לא ניתן להמיר רכיב תגמולים להון עבור קרן פנסיה/ביטוח מנהלים",
        ).as_dict()

    return ComponentRule(
        can_convert_to_pension=True,
        can_convert_to_capital=False,
        pension_tax="taxable",
        capital_tax=None,
        error="לא ניתן להמיר רכיב תגמולים להון עבור סוג מוצר לא מזוהה",
    ).as_dict()


def preferred_conversion_type_for_component(*, field: str, product_type: str) -> str:
    pt = (product_type or "").lower()
    is_education_code = any(token in pt for token in ("education_fund", "klal_stud"))
    if is_education_fund(product_type) or is_education_code:
        return ConversionType.capital_asset.value

    if field == PensionPortfolioComponentField.tagmulim_aggregate.value:
        rule = rule_for_tagmulim_by_product_type(product_type=product_type)
        if bool(rule.get("capital_asset")):
            return ConversionType.capital_asset.value
        return ConversionType.pension.value

    if field in {
        PensionPortfolioComponentField.tagmulim_employee_to_2000.value,
        PensionPortfolioComponentField.tagmulim_employer_to_2000.value,
        PensionPortfolioComponentField.education_fund_column.value,
        PensionPortfolioComponentField.severance_after_settlement.value,
    }:
        return ConversionType.capital_asset.value

    return ConversionType.pension.value


def validate_component_conversion(
    *,
    field: str,
    amount: float,
    conversion_type: str,
    product_type: str,
) -> tuple[bool, str | None, str | None]:
    if amount <= 0:
        return True, None, None

    pt = (product_type or "").lower()

    is_education_code = any(token in pt for token in ("education_fund", "klal_stud"))

    if ("גמל להשקעה" in pt) or ("investment_provident_fund" in pt):
        if conversion_type == ConversionType.capital_asset.value:
            return True, "capital_gains", None
        return True, "exempt", None

    if is_education_fund(product_type) or is_education_code:
        return True, "exempt", None

    if field == PensionPortfolioComponentField.tagmulim_aggregate.value:
        rule = rule_for_tagmulim_by_product_type(product_type=product_type)
    else:
        rule = COMPONENT_RULES.get(field)

    if not rule:
        return False, None, f"לא נמצאו חוקים עבור רכיב: {field}"

    allowed = bool(rule.get(conversion_type))
    if not allowed:
        return False, None, str(rule.get("error") or "לא ניתן להמיר")

    if conversion_type == ConversionType.pension.value:
        return True, str(rule.get("pension_tax") or "taxable"), None

    if conversion_type == ConversionType.capital_asset.value:
        cap_tax = rule.get("capital_tax")
        return True, str(cap_tax) if cap_tax is not None else "capital_gains", None

    return False, None, "סוג המרה לא נתמך"
