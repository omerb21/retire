import json
import os
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.models.scenario import Scenario
from app.services.current_employer_service import CurrentEmployerService
from app.services.retirement.services.termination_service import (
    TerminationService as ScenarioTerminationService,
)

router = APIRouter(prefix="/api/v1/debug", tags=["debug-severance"])


def _check_enabled_and_auth(x_admin_token: Optional[str] = Header(None)) -> None:
    enabled = (os.getenv("DEBUG_ENDPOINTS_ENABLED") or "").strip()
    if enabled != "1":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    expected = (os.getenv("ADMIN_DEBUG_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token not configured",
        )

    if not x_admin_token or x_admin_token.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token"
        )


def _employer_to_payload(employer: CurrentEmployer) -> dict[str, Any]:
    return {
        "id": getattr(employer, "id", None),
        "client_id": getattr(employer, "client_id", None),
        "employer_name": getattr(employer, "employer_name", None),
        "employer_id_number": getattr(employer, "employer_id_number", None),
        "start_date": getattr(employer, "start_date", None),
        "end_date": getattr(employer, "end_date", None),
        "last_salary": getattr(employer, "last_salary", None),
        "severance_accrued": getattr(employer, "severance_accrued", None),
        "updated_at": getattr(employer, "updated_at", None),
    }


def _choose_employer_reason(
    candidates: list[CurrentEmployer],
) -> tuple[Optional[CurrentEmployer], str]:
    if not candidates:
        return None, "none"

    complete_candidates = [
        c
        for c in candidates
        if float(getattr(c, "severance_accrued", None) or 0.0) > 0.0
        and float(getattr(c, "last_salary", None) or 0.0) > 0.0
    ]

    chosen = candidates[0]
    reason = "latest"

    if len(candidates) > 1 and complete_candidates:
        latest_severance = float(getattr(chosen, "severance_accrued", None) or 0.0)
        latest_salary = float(getattr(chosen, "last_salary", None) or 0.0)
        latest_missing_critical_fields = latest_severance <= 0.0 or latest_salary <= 0.0

        if latest_missing_critical_fields:
            chosen = complete_candidates[0]
            reason = "fallback_complete_due_to_missing_latest_fields"

    return chosen, reason


def _load_latest_retirement_age(*, db: Session, client_id: int) -> Optional[int]:
    row = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.parameters.like('%"retirement_age":%'))
        .order_by(Scenario.created_at.desc(), Scenario.id.desc())
        .first()
    )
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        params = json.loads(row.parameters)
    except Exception:
        return None
    try:
        age = params.get("retirement_age")
        return int(age) if age is not None else None
    except Exception:
        return None


@router.get(
    "/current-employer/{client_id}",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def debug_current_employer(
    client_id: int,
    retirement_age: Optional[int] = Query(None, ge=1, le=120),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    candidates = (
        db.execute(
            select(CurrentEmployer)
            .where(CurrentEmployer.client_id == client_id)
            .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
        )
        .scalars()
        .all()
    )

    chosen, selection_reason = _choose_employer_reason(candidates)

    selected_employer = _employer_to_payload(chosen) if chosen is not None else None

    if retirement_age is None:
        retirement_age = _load_latest_retirement_age(db=db, client_id=client_id)

    termination_inputs: dict[str, Any] = {
        "retirement_age": retirement_age,
        "termination_date_source": None,
        "termination_date": None,
    }
    termination_result: dict[str, Any] = {}

    used_fallback_expected_severance = False

    if chosen is not None and retirement_age is not None:
        try:
            retirement_year = int(getattr(client, "birth_date").year) + int(
                retirement_age
            )
            fallback_date = date(retirement_year, 1, 1)
        except Exception:
            fallback_date = None

        termination_date = getattr(chosen, "end_date", None) or fallback_date
        termination_inputs["termination_date"] = termination_date
        termination_inputs["termination_date_source"] = (
            "employer_end_date"
            if getattr(chosen, "end_date", None)
            else "scenario_fallback"
        )

        try:
            accrued = float(getattr(chosen, "severance_accrued", None) or 0.0)
        except Exception:
            accrued = 0.0

        used_fallback_expected_severance = accrued <= 0.0

        termination_inputs.update(
            {
                "employer_start_date": getattr(chosen, "start_date", None),
                "employer_last_salary": getattr(chosen, "last_salary", None),
                "employer_severance_accrued": getattr(
                    chosen, "severance_accrued", None
                ),
            }
        )

        if termination_date is not None:
            try:
                scenario_term = ScenarioTerminationService(
                    db=db,
                    client_id=client_id,
                    retirement_age=int(retirement_age),
                    add_action_callback=None,
                    use_current_employer_termination=True,
                )
                breakdown = scenario_term._calculate_severance_breakdown(
                    chosen, termination_date
                )
                if isinstance(breakdown, dict):
                    termination_result = dict(breakdown)
                    termination_result["severance_source"] = (
                        "employer_severance_accrued"
                        if not used_fallback_expected_severance
                        else "formula_last_salary_x_service_years"
                    )
            except Exception:
                termination_result = {}

    return {
        "client_id": client_id,
        "selected_employer": selected_employer,
        "selection_reason": selection_reason,
        "termination_inputs": termination_inputs,
        "termination_result": termination_result,
        "used_fallback_expected_severance": bool(used_fallback_expected_severance),
    }


@router.get(
    "/latest-snapshot/{client_id}",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def debug_latest_snapshot(
    client_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "undo_snapshot")
        .order_by(Scenario.created_at.desc(), Scenario.id.desc())
        .first()
    )

    if row is None or not getattr(row, "parameters", None):
        raise HTTPException(status_code=404, detail="No undo_snapshot found")

    try:
        params = json.loads(row.parameters)
    except Exception:
        raise HTTPException(status_code=500, detail="Snapshot payload invalid")

    snapshot = params.get("snapshot") if isinstance(params, dict) else None
    data = snapshot.get("data") if isinstance(snapshot, dict) else None
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Snapshot data missing")

    current_employer = data.get("current_employer")
    employer_has_severance_key = False
    employer_severance_value = None
    if isinstance(current_employer, dict):
        employer_has_severance_key = "severance_accrued" in current_employer
        employer_severance_value = current_employer.get("severance_accrued")

    saved_counts = {
        "pension_funds": (
            len(data.get("pension_funds") or [])
            if isinstance(data.get("pension_funds"), list)
            else None
        ),
        "capital_assets": (
            len(data.get("capital_assets") or [])
            if isinstance(data.get("capital_assets"), list)
            else None
        ),
        "additional_incomes": (
            len(data.get("additional_incomes") or [])
            if isinstance(data.get("additional_incomes"), list)
            else None
        ),
        "grants": (
            len(data.get("grants") or [])
            if isinstance(data.get("grants"), list)
            else None
        ),
        "legacy_grants": (
            len(data.get("legacy_grants") or [])
            if isinstance(data.get("legacy_grants"), list)
            else None
        ),
        "has_employer": bool(data.get("current_employer")),
        "has_termination": bool(data.get("termination_event")),
        "has_fixation": bool(data.get("fixation_result")),
    }

    try:
        from app.models.additional_income import AdditionalIncome
        from app.models.capital_asset import CapitalAsset
        from app.models.fixation_result import FixationResult
        from app.models.grant import Grant
        from app.models.pension_fund import PensionFund
        from app.models.termination_event import TerminationEvent

        employer_count = int(
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == client_id)
            .count()
        )

        current_counts = {
            "pension_funds": int(
                db.query(PensionFund).filter(PensionFund.client_id == client_id).count()
            ),
            "capital_assets": int(
                db.query(CapitalAsset)
                .filter(CapitalAsset.client_id == client_id)
                .count()
            ),
            "additional_incomes": int(
                db.query(AdditionalIncome)
                .filter(AdditionalIncome.client_id == client_id)
                .count()
            ),
            "legacy_grants": int(
                db.query(Grant).filter(Grant.client_id == client_id).count()
            ),
            "termination_events": int(
                db.query(TerminationEvent)
                .filter(TerminationEvent.client_id == client_id)
                .count()
            ),
            "fixation_results": int(
                db.query(FixationResult)
                .filter(FixationResult.client_id == client_id)
                .count()
            ),
            "current_employers": employer_count,
        }
    except Exception:
        current_counts = {}

    return {
        "client_id": client_id,
        "snapshot_scenario_id": getattr(row, "id", None),
        "saved_counts": saved_counts,
        "current_employer_in_snapshot": {
            "present": isinstance(current_employer, dict),
            "has_severance_accrued_key": bool(employer_has_severance_key),
            "severance_accrued": employer_severance_value,
        },
        "current_db_counts": current_counts,
    }
