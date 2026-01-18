import json

from sqlalchemy.orm import Session

from app.models import Commutation, CurrentEmployer, FixationResult, Grant, Pension, TerminationEvent


def _yes_no_unknown(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def get_fixation_status_snapshot(*, client_id: int, db: Session) -> dict:
    missing_inputs: list[str] = []

    has_prior_fixation_val: bool | None = None
    try:
        has_prior_fixation_val = (
            db.query(FixationResult).filter(FixationResult.client_id == client_id).count() > 0
        )
    except Exception:
        has_prior_fixation_val = None

    has_161d_val: bool | None = None
    try:
        has_161d_val = (
            db.query(FixationResult).filter(FixationResult.client_id == client_id).count() > 0
        )
    except Exception:
        has_161d_val = None

    has_161_val: bool | None = None
    try:
        has_161_val = (
            db.query(TerminationEvent).filter(TerminationEvent.client_id == client_id).count() > 0
        )
    except Exception:
        has_161_val = None

    has_commutation_val: bool | None = None
    try:
        has_commutation_val = (
            db.query(Commutation)
            .join(Pension, Pension.id == Commutation.pension_id)
            .filter(Pension.client_id == client_id)
            .count()
            > 0
        )
    except Exception:
        has_commutation_val = None

    has_exempt_grants_val: bool | None = None
    try:
        has_exempt_grants_val = db.query(Grant).filter(Grant.client_id == client_id).count() > 0
    except Exception:
        has_exempt_grants_val = None

    employment_ended_val: bool | None = None
    try:
        employer = (
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )
        if employer is None:
            employment_ended_val = None
        else:
            employment_ended_val = employer.end_date is not None
    except Exception:
        employment_ended_val = None

    if has_prior_fixation_val is False:
        missing_inputs.append("לא נמצא קיבוע קודם במערכת")
    if has_161_val is False:
        missing_inputs.append("אין תיעוד מסמכי/אירוע סיום עבודה (161)")
    if has_161d_val is False:
        missing_inputs.append("לא נמצא טופס/תוצאת קיבוע (161ד) במערכת")
    if has_commutation_val is False:
        missing_inputs.append("לא נמצא תיעוד היוונים במערכת")
    if has_exempt_grants_val is False:
        missing_inputs.append("לא נמצאו מענקים ממעסיקים קודמים (Grant) במערכת")

    payload = {
        "has_prior_fixation": _yes_no_unknown(has_prior_fixation_val),
        "has_161": _yes_no_unknown(has_161_val),
        "has_161d": _yes_no_unknown(has_161d_val),
        "has_commutation": _yes_no_unknown(has_commutation_val),
        "has_exempt_grants": _yes_no_unknown(has_exempt_grants_val),
        "employment_ended": _yes_no_unknown(employment_ended_val),
        "missing_inputs": missing_inputs,
    }
    return payload


def handle_get_fixation_status_snapshot(*, args: dict, client_id: int, db: Session) -> str:
    _ = args
    payload = get_fixation_status_snapshot(client_id=client_id, db=db)
    return json.dumps(payload, ensure_ascii=False)
