import logging
from typing import Any, Dict, List, Optional
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.current_employment import CurrentEmployer, EmployerGrant, GrantType
from app.models.grant import Grant
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.schemas.current_employer import TerminationDecisionCreate

logger = logging.getLogger("app.current_employer.termination")


def _delete_existing_severance_grants(self, employer_id: int):
    """מחיקת EmployerGrants קיימים"""
    existing_grants = (
        self.db.query(EmployerGrant)
        .filter(
            EmployerGrant.employer_id == employer_id,
            EmployerGrant.grant_type == GrantType.severance,
        )
        .all()
    )

    if existing_grants:
        logger.debug("Deleting %s existing EmployerGrants", len(existing_grants))
        for grant in existing_grants:
            self.db.delete(grant)
        self.db.flush()


def _create_employer_grants(
    self,
    employer: CurrentEmployer,
    decision: TerminationDecisionCreate,
    plan_details_list: List[Dict],
):
    """יצירת EmployerGrant לכל תכנית"""
    if plan_details_list:
        for plan_detail in plan_details_list:
            amount_raw = plan_detail.get("amount", 0)
            try:
                amount = float(amount_raw or 0)
            except Exception:
                amount = 0.0
            if amount > 0:
                employer_grant = EmployerGrant(
                    employer_id=employer.id,
                    grant_type=GrantType.severance,
                    grant_amount=amount,
                    grant_date=decision.termination_date,
                    plan_name=plan_detail.get("plan_name"),
                    plan_start_date=self._parse_date(
                        plan_detail.get("plan_start_date")
                    ),
                    product_type=plan_detail.get("product_type", "קופת גמל"),
                )
                self.db.add(employer_grant)
        self.db.flush()
    else:
        # Fallback: יצירת מענק יחיד
        total_amount = float(decision.exempt_amount or 0) + float(
            decision.taxable_amount or 0
        )
        if total_amount > 0:
            employer_grant = EmployerGrant(
                employer_id=employer.id,
                grant_type=GrantType.severance,
                grant_amount=total_amount,
                grant_date=decision.termination_date,
                plan_name="ללא תכנית",
                plan_start_date=employer.start_date,
            )
            self.db.add(employer_grant)
            self.db.flush()


def _delete_grants(self, client_id: int, employer_name: str) -> int:
    """מחיקת מענקים"""
    grants = (
        self.db.query(Grant)
        .filter(
            Grant.client_id == client_id, Grant.employer_name.like(f"%{employer_name}%")
        )
        .all()
    )
    for grant in grants:
        self.db.delete(grant)
    return len(grants)


def _delete_capital_assets(self, client_id: int, employer_name: str) -> int:
    """מחיקת נכסי הון"""
    assets = (
        self.db.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client_id,
            CapitalAsset.asset_name.like(f"%{employer_name}%"),
        )
        .all()
    )
    for asset in assets:
        self.db.delete(asset)
    return len(assets)


def _delete_pension_funds(self, client_id: int, employer_name: str) -> int:
    """מחיקת קצבאות"""
    pensions = (
        self.db.query(PensionFund)
        .filter(
            PensionFund.client_id == client_id,
            PensionFund.fund_name.like(f"%{employer_name}%"),
        )
        .all()
    )
    for pension in pensions:
        self.db.delete(pension)
    return len(pensions)


class TerminationRepositoryMixin:
    def _process_exempt_amount(
        self,
        client: Client,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate,
        source_suffix: str,
        result: Dict,
    ):
        """עיבוד סכום פטור - מענק/קצבה/נכס הון"""
        logger.debug("Processing exempt amount: %s", decision.exempt_amount)

        if decision.exempt_choice == "redeem_with_exemption":
            # יצירת מענק + נכס הון פטור
            grant_prefix = f"מענק פיצויים פטור - {employer.employer_name}"
            matching_grants = (
                self.db.query(Grant)
                .filter(
                    Grant.client_id == client.id,
                    Grant.grant_date == decision.termination_date,
                    Grant.employer_name.like(f"{grant_prefix}%"),
                )
                .order_by(Grant.id.desc())
                .all()
            )
            existing_grant = matching_grants[0] if matching_grants else None
            if len(matching_grants) > 1:
                for extra in matching_grants[1:]:
                    self.db.delete(extra)

            if existing_grant is not None:
                existing_grant.employer_name = f"{grant_prefix}{source_suffix}"
                existing_grant.work_start_date = employer.start_date
                existing_grant.work_end_date = decision.termination_date
                existing_grant.grant_amount = decision.exempt_amount
                existing_grant.grant_date = decision.termination_date
                existing_grant.grant_indexed_amount = decision.exempt_amount
                existing_grant.limited_indexed_amount = decision.exempt_amount
                self.db.flush()
                result["created_grant_id"] = existing_grant.id
            else:
                grant = Grant(
                    client_id=client.id,
                    employer_name=f"{grant_prefix}{source_suffix}",
                    work_start_date=employer.start_date,
                    work_end_date=decision.termination_date,
                    grant_amount=decision.exempt_amount,
                    grant_date=decision.termination_date,
                    grant_indexed_amount=decision.exempt_amount,
                    limited_indexed_amount=decision.exempt_amount,
                )
                self.db.add(grant)
                self.db.flush()
                result["created_grant_id"] = grant.id

            asset_prefix = f"מענק פיצויים פטור ({employer.employer_name})"
            matching_assets = (
                self.db.query(CapitalAsset)
                .filter(
                    CapitalAsset.client_id == client.id,
                    CapitalAsset.start_date == decision.termination_date,
                    CapitalAsset.asset_name.like(f"{asset_prefix}%"),
                    CapitalAsset.asset_type == "other",
                )
                .order_by(CapitalAsset.id.desc())
                .all()
            )
            existing_asset = matching_assets[0] if matching_assets else None
            if len(matching_assets) > 1:
                for extra in matching_assets[1:]:
                    self.db.delete(extra)

            if existing_asset is not None:
                existing_asset.asset_name = f"{asset_prefix}{source_suffix}"
                existing_asset.current_value = Decimal("0")
                existing_asset.monthly_income = Decimal(
                    str(decision.exempt_amount or 0)
                )
                existing_asset.annual_return_rate = 0.0
                existing_asset.payment_frequency = "annually"
                existing_asset.start_date = decision.termination_date
                existing_asset.indexation_method = "none"
                existing_asset.tax_treatment = "exempt"
                existing_asset.spread_years = None
                existing_asset.remarks = (
                    f"מענק פיצויים פטור ממס - {decision.exempt_amount:,.0f} ₪"
                )
                self.db.flush()
                result["created_capital_asset_id"] = existing_asset.id
            else:
                capital_asset = CapitalAsset(
                    client_id=client.id,
                    asset_name=f"{asset_prefix}{source_suffix}",
                    asset_type="other",
                    current_value=Decimal("0"),
                    monthly_income=Decimal(str(decision.exempt_amount or 0)),
                    annual_return_rate=0.0,
                    payment_frequency="annually",
                    start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment="exempt",
                    remarks=f"מענק פיצויים פטור ממס - {decision.exempt_amount:,.0f} ₪",
                )
                self.db.add(capital_asset)
                self.db.flush()
                result["created_capital_asset_id"] = capital_asset.id

        elif decision.exempt_choice == "redeem_no_exemption":
            # נכס הון עם פריסת מס
            spread_years = decision.max_spread_years or 1
            asset_prefix = f"מענק פיצויים פטור ({employer.employer_name})"
            matching_assets = (
                self.db.query(CapitalAsset)
                .filter(
                    CapitalAsset.client_id == client.id,
                    CapitalAsset.start_date == decision.termination_date,
                    CapitalAsset.asset_name.like(f"{asset_prefix}%"),
                    CapitalAsset.asset_type == "other",
                )
                .order_by(CapitalAsset.id.desc())
                .all()
            )
            existing_asset = matching_assets[0] if matching_assets else None
            if len(matching_assets) > 1:
                for extra in matching_assets[1:]:
                    self.db.delete(extra)

            if existing_asset is not None:
                existing_asset.asset_name = f"{asset_prefix}{source_suffix}"
                existing_asset.current_value = Decimal("0")
                existing_asset.monthly_income = Decimal(
                    str(decision.exempt_amount or 0)
                )
                existing_asset.annual_return_rate = 0.0
                existing_asset.payment_frequency = "annually"
                existing_asset.start_date = decision.termination_date
                existing_asset.indexation_method = "none"
                existing_asset.tax_treatment = "tax_spread"
                existing_asset.spread_years = spread_years
                existing_asset.remarks = (
                    f"מענק פיצויים פטור ממס עם פריסת מס ל-{spread_years} שנים"
                )
                self.db.flush()
                result["created_capital_asset_id"] = existing_asset.id
            else:
                capital_asset = CapitalAsset(
                    client_id=client.id,
                    asset_name=f"{asset_prefix}{source_suffix}",
                    asset_type="other",
                    current_value=Decimal("0"),
                    monthly_income=Decimal(str(decision.exempt_amount or 0)),
                    annual_return_rate=0.0,
                    payment_frequency="annually",
                    start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment="tax_spread",
                    spread_years=spread_years,
                    remarks=f"מענק פיצויים פטור ממס עם פריסת מס ל-{spread_years} שנים",
                )
                self.db.add(capital_asset)
                self.db.flush()
                result["created_capital_asset_id"] = capital_asset.id

        elif decision.exempt_choice == "annuity":
            # יצירת קצבאות
            self._create_pension_funds_from_amount(
                client, employer, decision, decision.exempt_amount, "exempt", result
            )

    def _process_taxable_amount(
        self,
        client: Client,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate,
        source_suffix: str,
        result: Dict,
        max_spread_years: int = 6,
    ):
        """עיבוד סכום חייב - קצבה/נכס הון עם פריסת מס"""
        logger.debug("Processing taxable amount: %s", decision.taxable_amount)

        # D4.4: אכיפת שנות פריסה מקסימליות לטובת הלקוח
        requested_spread = decision.tax_spread_years
        if (
            requested_spread is None
            or requested_spread < 1
            or requested_spread > max_spread_years
        ):
            effective_spread_years = max_spread_years
            logger.debug(
                "Enforcing max spread years (requested=%s, using=%s)",
                requested_spread,
                effective_spread_years,
            )
        else:
            effective_spread_years = requested_spread
            logger.debug("Using requested spread years: %s", effective_spread_years)

        # D4.4: שמירת הפריסה בפועל ב-result
        result["effective_spread_years"] = effective_spread_years
        result["requested_spread_years"] = requested_spread

        # D4.1: בדיקה אם יש פיצול של הסכום החייב
        taxable_annuity = getattr(decision, "taxable_annuity_amount", None)
        taxable_capital = getattr(decision, "taxable_capital_amount", None)

        if decision.taxable_choice == "split" or (
            taxable_annuity is not None or taxable_capital is not None
        ):
            # D4.1: פיצול הסכום החייב - חלק לקצבה וחלק למענק
            annuity_amount = float(taxable_annuity or 0)
            capital_amount = float(taxable_capital or 0)

            logger.debug(
                "Split taxable amount (annuity=%s, capital=%s)",
                annuity_amount,
                capital_amount,
            )

            # יצירת קצבה מהחלק שהוקצה לרצף קצבה
            if annuity_amount > 0:
                logger.debug("Creating pension from annuity amount: %s", annuity_amount)
                self._create_pension_funds_from_amount(
                    client, employer, decision, annuity_amount, "taxable", result
                )

            # יצירת נכס הון מהחלק שהוקצה למענק
            if capital_amount > 0:
                logger.debug(
                    "Creating capital asset from capital amount: %s", capital_amount
                )
                spread_years = effective_spread_years  # D4.4: שימוש בפריסה המאוכפת
                asset_prefix = f"מענק פיצויים חייב במס ({employer.employer_name})"
                matching_assets = (
                    self.db.query(CapitalAsset)
                    .filter(
                        CapitalAsset.client_id == client.id,
                        CapitalAsset.start_date == decision.termination_date,
                        CapitalAsset.asset_name.like(f"{asset_prefix}%"),
                        CapitalAsset.asset_type == "other",
                    )
                    .order_by(CapitalAsset.id.desc())
                    .all()
                )
                existing_asset = matching_assets[0] if matching_assets else None
                if len(matching_assets) > 1:
                    for extra in matching_assets[1:]:
                        self.db.delete(extra)

                if existing_asset is not None:
                    existing_asset.asset_name = f"{asset_prefix}{source_suffix}"
                    existing_asset.current_value = Decimal("0")
                    existing_asset.monthly_income = Decimal(str(capital_amount or 0))
                    existing_asset.annual_return_rate = 0.0
                    existing_asset.payment_frequency = "annually"
                    existing_asset.start_date = decision.termination_date
                    existing_asset.indexation_method = "none"
                    existing_asset.tax_treatment = "tax_spread"
                    existing_asset.spread_years = spread_years
                    existing_asset.remarks = f"מענק פיצויים חייב במס עם פריסת מס ל-{spread_years} שנים (D4.1 split)"
                    self.db.flush()
                    if not result.get("created_capital_asset_id"):
                        result["created_capital_asset_id"] = existing_asset.id
                else:
                    capital_asset = CapitalAsset(
                        client_id=client.id,
                        asset_name=f"{asset_prefix}{source_suffix}",
                        asset_type="other",
                        current_value=Decimal("0"),
                        monthly_income=Decimal(str(capital_amount or 0)),
                        annual_return_rate=0.0,
                        payment_frequency="annually",
                        start_date=decision.termination_date,
                        indexation_method="none",
                        tax_treatment="tax_spread",
                        spread_years=spread_years,
                        remarks=f"מענק פיצויים חייב במס עם פריסת מס ל-{spread_years} שנים (D4.1 split)",
                    )
                    self.db.add(capital_asset)
                    self.db.flush()
                    if not result.get("created_capital_asset_id"):
                        result["created_capital_asset_id"] = capital_asset.id

                # D4.2: חישוב המס על המענק ההוני
                tax_info = self._calculate_capital_tax(capital_amount, spread_years)
                result["capital_tax_info"] = tax_info
                logger.debug("Capital tax calculated: %s", tax_info)

        elif decision.taxable_choice == "redeem_no_exemption":
            # נכס הון עם פריסת מס - כל הסכום החייב
            spread_years = effective_spread_years  # D4.4: שימוש בפריסה המאוכפת
            asset_prefix = f"מענק פיצויים חייב במס ({employer.employer_name})"
            matching_assets = (
                self.db.query(CapitalAsset)
                .filter(
                    CapitalAsset.client_id == client.id,
                    CapitalAsset.start_date == decision.termination_date,
                    CapitalAsset.asset_name.like(f"{asset_prefix}%"),
                    CapitalAsset.asset_type == "other",
                )
                .order_by(CapitalAsset.id.desc())
                .all()
            )
            existing_asset = matching_assets[0] if matching_assets else None
            if len(matching_assets) > 1:
                for extra in matching_assets[1:]:
                    self.db.delete(extra)

            if existing_asset is not None:
                existing_asset.asset_name = f"{asset_prefix}{source_suffix}"
                existing_asset.current_value = Decimal("0")
                existing_asset.monthly_income = Decimal(
                    str(decision.taxable_amount or 0)
                )
                existing_asset.annual_return_rate = 0.0
                existing_asset.payment_frequency = "annually"
                existing_asset.start_date = decision.termination_date
                existing_asset.indexation_method = "none"
                existing_asset.tax_treatment = "tax_spread"
                existing_asset.spread_years = spread_years
                existing_asset.remarks = (
                    f"מענק פיצויים חייב במס עם פריסת מס ל-{spread_years} שנים"
                )
                self.db.flush()
                if not result.get("created_capital_asset_id"):
                    result["created_capital_asset_id"] = existing_asset.id
            else:
                capital_asset = CapitalAsset(
                    client_id=client.id,
                    asset_name=f"{asset_prefix}{source_suffix}",
                    asset_type="other",
                    current_value=Decimal("0"),
                    monthly_income=Decimal(str(decision.taxable_amount or 0)),
                    annual_return_rate=0.0,
                    payment_frequency="annually",
                    start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment="tax_spread",
                    spread_years=spread_years,
                    remarks=f"מענק פיצויים חייב במס עם פריסת מס ל-{spread_years} שנים",
                )
                self.db.add(capital_asset)
                self.db.flush()
                if not result.get("created_capital_asset_id"):
                    result["created_capital_asset_id"] = capital_asset.id

            # D4.2: חישוב המס על המענק ההוני
            tax_info = self._calculate_capital_tax(
                float(decision.taxable_amount), spread_years
            )
            result["capital_tax_info"] = tax_info
            logger.debug("Capital tax calculated: %s", tax_info)

        elif decision.taxable_choice == "annuity":
            # יצירת קצבאות - כל הסכום החייב
            self._create_pension_funds_from_amount(
                client, employer, decision, decision.taxable_amount, "taxable", result
            )

    def _create_pension_funds_from_amount(
        self,
        client: Client,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate,
        amount: Decimal,
        tax_treatment: str,
        result: Dict,
    ):
        """יצירת קצבאות מסכום נתון"""
        from app.services.annuity_coefficient import get_annuity_coefficient

        try:
            amount_value = float(amount or 0)
        except Exception:
            amount_value = 0.0
        if amount_value <= 0:
            return

        grants = (
            self.db.query(EmployerGrant)
            .filter(
                EmployerGrant.employer_id == employer.id,
                EmployerGrant.grant_type == GrantType.severance,
            )
            .all()
        )

        grants_by_plan: dict[str, dict[str, object]] = {}
        total_grant_amount = sum(
            float(getattr(g, "grant_amount", 0) or 0) for g in grants
        )

        for grant in grants:
            plan_key = (grant.plan_name or "ללא תכנית").strip() or "ללא תכנית"
            if plan_key not in grants_by_plan:
                grants_by_plan[plan_key] = {
                    "grants": [],
                    "plan_start_date": getattr(grant, "plan_start_date", None),
                    "plan_name": getattr(grant, "plan_name", None),
                    "product_type": getattr(grant, "product_type", None) or "קופת גמל",
                }
            grants_by_plan[plan_key]["grants"].append(grant)

        if not grants_by_plan or total_grant_amount <= 0:
            plan_details_list = self._parse_plan_details(decision)
            inferred_total = 0.0
            inferred_by_plan: dict[str, dict[str, object]] = {}
            for plan_detail in plan_details_list or []:
                try:
                    p_amount = float(plan_detail.get("amount") or 0)
                except Exception:
                    p_amount = 0.0
                if p_amount <= 0:
                    continue
                plan_key = (
                    str(plan_detail.get("plan_name") or "ללא תכנית").strip()
                    or "ללא תכנית"
                )
                inferred_total += p_amount

                if plan_key not in inferred_by_plan:
                    inferred_by_plan[plan_key] = {
                        "grants": [],
                        "plan_start_date": self._parse_date(
                            plan_detail.get("plan_start_date")
                        )
                        or employer.start_date,
                        "plan_name": plan_detail.get("plan_name") or plan_key,
                        "product_type": plan_detail.get("product_type", "קופת גמל"),
                        "_synthetic_amount": 0.0,
                    }
                inferred_by_plan[plan_key]["_synthetic_amount"] = (
                    float(inferred_by_plan[plan_key].get("_synthetic_amount") or 0)
                    + p_amount
                )

            if inferred_by_plan and inferred_total > 0:
                grants_by_plan = inferred_by_plan
                total_grant_amount = inferred_total
            else:
                grants_by_plan = {
                    "ללא תכנית": {
                        "grants": [],
                        "plan_start_date": employer.start_date,
                        "plan_name": "ללא תכנית",
                        "product_type": "קופת גמל",
                        "_synthetic_amount": amount_value,
                    }
                }
                total_grant_amount = amount_value

        total_annuity_deposit = 0.0
        total_monthly_annuity = 0.0
        annuity_details: list[dict[str, object]] = []

        # יצירת קצבה לכל תכנית
        for plan_key, plan_data in grants_by_plan.items():
            plan_grants = plan_data["grants"]
            plan_grant_amount = sum(
                float(getattr(g, "grant_amount", 0) or 0) for g in plan_grants
            )
            if plan_grant_amount <= 0:
                try:
                    plan_grant_amount = float(plan_data.get("_synthetic_amount") or 0)
                except Exception:
                    plan_grant_amount = 0.0
            plan_amount = (
                (plan_grant_amount / total_grant_amount) * amount_value
                if total_grant_amount > 0
                else 0.0
            )
            if plan_amount <= 0:
                continue

            # D3.9: חישוב מקדם קצבה לפי סוג המוצר
            product_type = plan_data["product_type"]
            start_date = (
                plan_data["plan_start_date"]
                or employer.start_date
                or decision.termination_date
            )
            logger.debug(
                "Calculating annuity coefficient (plan=%s, product_type=%s, start_date=%s, amount=%s)",
                plan_key,
                product_type,
                start_date,
                plan_amount,
            )

            try:
                from app.services.retirement_age_service import (
                    DEFAULT_MALE_RETIREMENT_AGE,
                    get_retirement_age_simple,
                )

                computed_ret_age = None
                try:
                    if (
                        client
                        and getattr(client, "birth_date", None)
                        and getattr(client, "gender", None)
                    ):
                        computed_ret_age = int(
                            get_retirement_age_simple(client.birth_date, client.gender)
                        )
                except Exception:
                    computed_ret_age = None

                try:
                    current_age = (
                        client.get_age()
                        if client and hasattr(client, "get_age")
                        else None
                    )
                except Exception:
                    current_age = None

                fallback_ret_age = int(DEFAULT_MALE_RETIREMENT_AGE)

                retirement_age_for_coeff = (
                    max(int(computed_ret_age), int(current_age))
                    if (computed_ret_age is not None and current_age is not None)
                    else (
                        int(current_age)
                        if current_age is not None
                        else (
                            int(computed_ret_age)
                            if computed_ret_age is not None
                            else fallback_ret_age
                        )
                    )
                )

                coefficient_result = get_annuity_coefficient(
                    product_type=product_type,
                    start_date=start_date,
                    gender=client.gender or "זכר",
                    retirement_age=retirement_age_for_coeff,
                    survivors_option="תקנוני",
                    spouse_age_diff=0,
                    birth_date=client.birth_date,
                    pension_start_date=decision.termination_date,
                )
                annuity_factor_raw = coefficient_result["factor_value"]
                annuity_factor = float(annuity_factor_raw or 0)
                if annuity_factor <= 0:
                    annuity_factor = 200
                logger.debug(
                    "Got coefficient (factor=%s, source=%s)",
                    annuity_factor,
                    coefficient_result.get("source_table", "unknown"),
                )
            except Exception as e:
                logger.warning("Coefficient error (%s), using default 200", e)
                annuity_factor = 200

            monthly_amount = plan_amount / annuity_factor

            plan_name_for_display = plan_data.get("plan_name") or plan_key
            fund_name = f"קצבה ממענק פיצויים {tax_treatment} - {plan_name_for_display} ({employer.employer_name})"
            matching_pensions = (
                self.db.query(PensionFund)
                .filter(
                    PensionFund.client_id == client.id,
                    PensionFund.pension_start_date == decision.termination_date,
                    PensionFund.fund_name == fund_name,
                )
                .order_by(PensionFund.id.desc())
                .all()
            )
            existing_pension = matching_pensions[0] if matching_pensions else None
            if len(matching_pensions) > 1:
                for extra in matching_pensions[1:]:
                    self.db.delete(extra)

            if existing_pension is not None:
                existing_pension.fund_name = fund_name
                existing_pension.fund_type = "monthly_pension"
                existing_pension.input_mode = "manual"
                existing_pension.balance = plan_amount
                existing_pension.annuity_factor = annuity_factor
                existing_pension.pension_amount = monthly_amount
                existing_pension.pension_start_date = decision.termination_date
                existing_pension.indexation_method = "none"
                existing_pension.tax_treatment = tax_treatment
                existing_pension.remarks = (
                    f"מקדם קצבה: {annuity_factor:.2f}, תכנית: {plan_name_for_display}"
                )
                self.db.flush()

                if not result.get("created_pension_id"):
                    result["created_pension_id"] = existing_pension.id
            else:
                pension_fund = PensionFund(
                    client_id=client.id,
                    fund_name=fund_name,
                    fund_type="monthly_pension",
                    input_mode="manual",
                    balance=plan_amount,
                    annuity_factor=annuity_factor,
                    pension_amount=monthly_amount,
                    pension_start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment=tax_treatment,
                    remarks=f"מקדם קצבה: {annuity_factor:.2f}, תכנית: {plan_name_for_display}",
                )
                self.db.add(pension_fund)
                self.db.flush()

                if not result.get("created_pension_id"):
                    result["created_pension_id"] = pension_fund.id

            # D6.1: צבירת נתוני הקצבה
            total_annuity_deposit += float(plan_amount)
            total_monthly_annuity += float(monthly_amount)
            annuity_details.append(
                {
                    "plan_name": plan_data.get("plan_name") or plan_key,
                    "deposit": round(float(plan_amount), 2),
                    "coefficient": round(annuity_factor, 2),
                    "monthly_annuity": round(float(monthly_amount), 2),
                }
            )

        # D6.1: עדכון result עם נתוני הקצבה
        if total_annuity_deposit > 0:
            # אתחול אם לא קיים
            if "annuity_projection" not in result:
                result["annuity_projection"] = {
                    "total_annuity_deposit": 0.0,
                    "total_monthly_annuity": 0.0,
                    "details": [],
                }

            # הוספה לסכומים הקיימים (יכול להיות גם exempt וגם taxable)
            result["annuity_projection"]["total_annuity_deposit"] += round(
                total_annuity_deposit, 2
            )
            result["annuity_projection"]["total_monthly_annuity"] += round(
                total_monthly_annuity, 2
            )
            result["annuity_projection"]["details"].extend(annuity_details)

            logger.debug(
                "Annuity projection updated (deposit=%s, monthly=%s)",
                total_annuity_deposit,
                total_monthly_annuity,
            )
