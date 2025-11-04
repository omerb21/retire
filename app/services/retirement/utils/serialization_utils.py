"""
Serialization utilities for retirement scenarios
פונקציות סריאליזציה לתרחישי פרישה
"""
from typing import Dict
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.additional_income import AdditionalIncome
from app.models.termination_event import TerminationEvent


def serialize_pension_fund(pf: PensionFund) -> Dict:
    """ממיר PensionFund לדיקשנרי"""
    return {
        "client_id": pf.client_id,
        "fund_name": pf.fund_name,
        "fund_type": pf.fund_type,
        "input_mode": pf.input_mode,
        "balance": float(pf.balance) if pf.balance else None,
        "annuity_factor": float(pf.annuity_factor) if pf.annuity_factor else None,
        "pension_amount": float(pf.pension_amount) if pf.pension_amount else None,
        "pension_start_date": pf.pension_start_date,
        "indexation_method": pf.indexation_method,
        "fixed_index_rate": float(pf.fixed_index_rate) if pf.fixed_index_rate else None,
        "indexed_pension_amount": float(pf.indexed_pension_amount) if pf.indexed_pension_amount else None,
        "tax_treatment": pf.tax_treatment,
        "remarks": pf.remarks,
        "deduction_file": pf.deduction_file,
        "conversion_source": pf.conversion_source
    }


def serialize_capital_asset(ca: CapitalAsset) -> Dict:
    """ממיר CapitalAsset לדיקשנרי"""
    return {
        "client_id": ca.client_id,
        "asset_name": ca.asset_name,
        "asset_type": ca.asset_type,
        "description": ca.description,
        "current_value": float(ca.current_value),
        "monthly_income": float(ca.monthly_income) if ca.monthly_income else None,
        "annual_return_rate": float(ca.annual_return_rate),
        "payment_frequency": ca.payment_frequency,
        "start_date": ca.start_date,
        "end_date": ca.end_date,
        "indexation_method": ca.indexation_method,
        "fixed_rate": float(ca.fixed_rate) if ca.fixed_rate else None,
        "tax_treatment": ca.tax_treatment,
        "tax_rate": float(ca.tax_rate) if ca.tax_rate else None,
        "spread_years": ca.spread_years,
        "remarks": ca.remarks,
        "conversion_source": ca.conversion_source
    }


def serialize_additional_income(ai: AdditionalIncome) -> Dict:
    """ממיר AdditionalIncome לדיקשנרי"""
    return {
        "client_id": ai.client_id,
        "source_type": ai.source_type,
        "description": ai.description,
        "amount": float(ai.amount),
        "frequency": ai.frequency,
        "start_date": ai.start_date,
        "end_date": ai.end_date,
        "indexation_method": ai.indexation_method,
        "fixed_rate": float(ai.fixed_rate) if ai.fixed_rate else None,
        "tax_treatment": ai.tax_treatment,
        "tax_rate": float(ai.tax_rate) if ai.tax_rate else None,
        "remarks": ai.remarks
    }


def serialize_termination_event(te: TerminationEvent) -> Dict:
    """ממיר TerminationEvent לדיקשנרי"""
    return {
        "client_id": te.client_id,
        "employment_id": te.employment_id,
        "planned_termination_date": te.planned_termination_date,
        "actual_termination_date": te.actual_termination_date,
        "reason": te.reason,
        "severance_basis_nominal": float(te.severance_basis_nominal) if te.severance_basis_nominal else None,
        "package_paths": te.package_paths
    }
