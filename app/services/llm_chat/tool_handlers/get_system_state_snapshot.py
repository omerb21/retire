import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AdditionalIncome,
    CapitalAsset,
    Commutation,
    CurrentEmployer,
    EmployerGrant,
    FixationResult,
    Grant,
    Pension,
    PensionFund,
    Scenario,
    TerminationEvent,
)


def handle_get_system_state_snapshot(*, args: dict, client_id: int, db: Session) -> str:
    def _dt(v: Any) -> str | None:
        try:
            if v is None:
                return None
            return v.isoformat()
        except Exception:
            return None

    def _d(v: Any) -> str | None:
        try:
            if v is None:
                return None
            return v.isoformat()
        except Exception:
            return None

    def _f(v: Any) -> float | None:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    def _loads_maybe(text: Any) -> Any:
        if not isinstance(text, str):
            return text
        raw = text.strip()
        if not raw:
            return text
        try:
            return json.loads(raw)
        except Exception:
            return text

    pension_funds = (
        db.query(PensionFund)
        .filter(PensionFund.client_id == client_id)
        .order_by(PensionFund.id.asc())
        .all()
    )
    capital_assets = (
        db.query(CapitalAsset)
        .filter(CapitalAsset.client_id == client_id)
        .order_by(CapitalAsset.id.asc())
        .all()
    )
    additional_incomes = (
        db.query(AdditionalIncome)
        .filter(AdditionalIncome.client_id == client_id)
        .order_by(AdditionalIncome.id.asc())
        .all()
    )

    current_employers = (
        db.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.id.asc())
        .all()
    )

    employer_ids = [e.id for e in current_employers if getattr(e, "id", None) is not None]
    employer_grants = (
        db.query(EmployerGrant)
        .filter(EmployerGrant.employer_id.in_(employer_ids))
        .order_by(EmployerGrant.id.asc())
        .all()
        if employer_ids
        else []
    )

    legacy_grants = (
        db.query(Grant).filter(Grant.client_id == client_id).order_by(Grant.id.asc()).all()
    )

    termination_events = (
        db.query(TerminationEvent)
        .filter(TerminationEvent.client_id == client_id)
        .order_by(TerminationEvent.created_at.desc())
        .all()
    )

    fixation_results = (
        db.query(FixationResult)
        .filter(FixationResult.client_id == client_id)
        .order_by(FixationResult.created_at.desc())
        .all()
    )

    pensions = (
        db.query(Pension)
        .filter(Pension.client_id == client_id)
        .order_by(Pension.id.asc())
        .all()
    )

    pension_ids = [p.id for p in pensions if getattr(p, "id", None) is not None]
    commutations = (
        db.query(Commutation)
        .filter(Commutation.pension_id.in_(pension_ids))
        .order_by(Commutation.id.asc())
        .all()
        if pension_ids
        else []
    )

    scenarios = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .order_by(Scenario.created_at.desc())
        .all()
    )

    result = {
        "client_id": client_id,
        "generated_at": datetime.utcnow().isoformat(),
        "counts": {
            "pension_funds": len(pension_funds),
            "capital_assets": len(capital_assets),
            "additional_incomes": len(additional_incomes),
            "current_employers": len(current_employers),
            "employer_grants": len(employer_grants),
            "legacy_grants": len(legacy_grants),
            "termination_events": len(termination_events),
            "fixation_results": len(fixation_results),
            "pensions": len(pensions),
            "commutations": len(commutations),
            "scenarios": len(scenarios),
        },
        "entities": {
            "pension_funds": [
                {
                    "id": pf.id,
                    "client_id": pf.client_id,
                    "fund_name": pf.fund_name,
                    "fund_type": pf.fund_type,
                    "input_mode": pf.input_mode,
                    "balance": _f(pf.balance),
                    "annuity_factor": _f(pf.annuity_factor),
                    "pension_amount": _f(pf.pension_amount),
                    "pension_start_date": _d(pf.pension_start_date),
                    "indexation_method": pf.indexation_method,
                    "fixed_index_rate": _f(pf.fixed_index_rate),
                    "indexed_pension_amount": _f(pf.indexed_pension_amount),
                    "tax_treatment": pf.tax_treatment,
                    "remarks": pf.remarks,
                    "deduction_file": pf.deduction_file,
                    "conversion_source": pf.conversion_source,
                    "created_at": _dt(getattr(pf, "created_at", None)),
                    "updated_at": _dt(getattr(pf, "updated_at", None)),
                }
                for pf in pension_funds
            ],
            "capital_assets": [
                {
                    "id": ca.id,
                    "client_id": ca.client_id,
                    "asset_name": ca.asset_name,
                    "asset_type": ca.asset_type,
                    "description": ca.description,
                    "current_value": _f(ca.current_value),
                    "monthly_income": _f(ca.monthly_income),
                    "annual_return_rate": _f(ca.annual_return_rate),
                    "payment_frequency": ca.payment_frequency,
                    "start_date": _d(ca.start_date),
                    "end_date": _d(ca.end_date),
                    "indexation_method": ca.indexation_method,
                    "fixed_rate": _f(ca.fixed_rate),
                    "tax_treatment": ca.tax_treatment,
                    "tax_rate": _f(ca.tax_rate),
                    "spread_years": ca.spread_years,
                    "remarks": ca.remarks,
                    "conversion_source": ca.conversion_source,
                    "created_at": _dt(getattr(ca, "created_at", None)),
                    "updated_at": _dt(getattr(ca, "updated_at", None)),
                }
                for ca in capital_assets
            ],
            "additional_incomes": [
                {
                    "id": ai.id,
                    "client_id": ai.client_id,
                    "source_type": ai.source_type,
                    "description": ai.description,
                    "amount": _f(ai.amount),
                    "frequency": ai.frequency,
                    "start_date": _d(ai.start_date),
                    "end_date": _d(ai.end_date),
                    "indexation_method": ai.indexation_method,
                    "fixed_rate": _f(ai.fixed_rate),
                    "tax_treatment": ai.tax_treatment,
                    "tax_rate": _f(ai.tax_rate),
                    "remarks": ai.remarks,
                }
                for ai in additional_incomes
            ],
            "current_employers": [
                {
                    "id": ce.id,
                    "client_id": ce.client_id,
                    "employer_name": ce.employer_name,
                    "employer_id_number": getattr(ce, "employer_id_number", None),
                    "start_date": _d(ce.start_date),
                    "end_date": _d(ce.end_date),
                    "non_continuous_periods": ce.non_continuous_periods or [],
                    "last_salary": _f(ce.last_salary),
                    "average_salary": _f(getattr(ce, "average_salary", None)),
                    "severance_accrued": _f(getattr(ce, "severance_accrued", None)),
                    "other_grants": ce.other_grants or {},
                    "tax_withheld": _f(getattr(ce, "tax_withheld", None)),
                    "grant_installments": ce.grant_installments or [],
                    "active_continuity": ce.active_continuity.value if getattr(ce, "active_continuity", None) else None,
                    "continuity_years": _f(getattr(ce, "continuity_years", None)),
                    "pre_retirement_pension": _f(getattr(ce, "pre_retirement_pension", None)),
                    "existing_deductions": ce.existing_deductions or {},
                    "last_update": _d(getattr(ce, "last_update", None)),
                    "indexed_severance": _f(getattr(ce, "indexed_severance", None)),
                    "severance_exemption_cap": _f(getattr(ce, "severance_exemption_cap", None)),
                    "severance_exempt": _f(getattr(ce, "severance_exempt", None)),
                    "severance_taxable": _f(getattr(ce, "severance_taxable", None)),
                    "severance_tax_due": _f(getattr(ce, "severance_tax_due", None)),
                    "created_at": _dt(getattr(ce, "created_at", None)),
                    "updated_at": _dt(getattr(ce, "updated_at", None)),
                }
                for ce in current_employers
            ],
            "employer_grants": [
                {
                    "id": g.id,
                    "employer_id": g.employer_id,
                    "grant_type": g.grant_type.value if g.grant_type else None,
                    "grant_amount": _f(g.grant_amount),
                    "grant_date": _d(g.grant_date),
                    "plan_name": g.plan_name,
                    "plan_start_date": _d(g.plan_start_date),
                    "product_type": g.product_type,
                    "tax_withheld": _f(g.tax_withheld),
                    "grant_exempt": _f(g.grant_exempt),
                    "grant_taxable": _f(g.grant_taxable),
                    "tax_due": _f(g.tax_due),
                    "indexed_amount": _f(g.indexed_amount),
                    "created_at": _dt(getattr(g, "created_at", None)),
                    "updated_at": _dt(getattr(g, "updated_at", None)),
                }
                for g in employer_grants
            ],
            "legacy_grants": [g.to_dict() for g in legacy_grants],
            "termination_events": [
                {
                    "id": te.id,
                    "client_id": te.client_id,
                    "employment_id": te.employment_id,
                    "planned_termination_date": _d(te.planned_termination_date),
                    "actual_termination_date": _d(te.actual_termination_date),
                    "reason": te.reason.value if getattr(te, "reason", None) is not None else None,
                    "severance_basis_nominal": _f(te.severance_basis_nominal),
                    "package_paths": _loads_maybe(te.package_paths),
                    "created_at": _dt(getattr(te, "created_at", None)),
                    "updated_at": _dt(getattr(te, "updated_at", None)),
                }
                for te in termination_events
            ],
            "fixation_results": [
                {
                    "id": fr.id,
                    "client_id": fr.client_id,
                    "created_at": _dt(fr.created_at),
                    "exempt_capital_remaining": _f(fr.exempt_capital_remaining),
                    "used_commutation": _f(fr.used_commutation),
                    "raw_payload": fr.raw_payload,
                    "raw_result": fr.raw_result,
                    "notes": fr.notes,
                }
                for fr in fixation_results
            ],
            "pensions": [p.to_dict() for p in pensions],
            "commutations": [c.to_dict() for c in commutations],
            "scenarios": [
                {
                    "id": s.id,
                    "client_id": s.client_id,
                    "scenario_name": s.scenario_name,
                    "apply_tax_planning": s.apply_tax_planning,
                    "apply_capitalization": s.apply_capitalization,
                    "apply_exemption_shield": s.apply_exemption_shield,
                    "parameters": _loads_maybe(s.parameters),
                    "summary_results": _loads_maybe(s.summary_results),
                    "cashflow_projection": _loads_maybe(s.cashflow_projection),
                    "created_at": _dt(s.created_at),
                }
                for s in scenarios
            ],
        },
    }

    return json.dumps(result, ensure_ascii=False)
