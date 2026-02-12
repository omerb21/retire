import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
    compute_effective_plan_target,
    compute_existing_income_offset_monthly,
)


_PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO = "pending_pre_retirement_plan_resolution"
_IGNORE_BLOCKED_BALANCES_DECISION_SCENARIO = "ignore_blocked_balances_decision"


def _today() -> date:
    return date.today()


def _coerce_float_safe(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("₪", "").strip()
            return float(cleaned or 0)
        return float(value)
    except Exception:
        return 0.0


def _compute_existing_fixed_net_income_monthly(*, db: Session, client_id: int) -> float:
    return compute_existing_income_offset_monthly(
        db=db,
        client_id=client_id,
        target_is_net=True,
    )


def _detect_blocked_balances_in_snapshot(*, portfolio: Any) -> bool:
    if not isinstance(portfolio, list) or not portfolio:
        return False
    for item in portfolio:
        data = {}
        if isinstance(item, dict):
            data = item
        else:
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                try:
                    dumped = model_dump()
                    if isinstance(dumped, dict):
                        data = dumped
                except Exception:
                    data = {}
            else:
                raw = getattr(item, "__dict__", {})
                data = raw if isinstance(raw, dict) else {}

        for key in (
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
            "פיצויים_מעסיק_נוכחי",
        ):
            if _coerce_float_safe(data.get(key)) > 0:
                return True
            nested = data.get("specific_amounts")
            if isinstance(nested, dict) and _coerce_float_safe(nested.get(key)) > 0:
                return True
    return False


def _load_pending_pre_retirement_plan_resolution(
    *, db: Session, client_id: int
) -> dict | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == _PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO)
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clear_pending_pre_retirement_plan_resolution(*, db: Session, client_id: int) -> None:
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _load_ignore_blocked_balances_decision(*, db: Session, client_id: int) -> bool:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == _IGNORE_BLOCKED_BALANCES_DECISION_SCENARIO)
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return False
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        parsed = None
    if not isinstance(parsed, dict):
        return False
    raw = parsed.get("ignore_blocked_balances")
    return bool(raw) is True


def _load_blocked_balances_decision(*, db: Session, client_id: int) -> bool | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == _IGNORE_BLOCKED_BALANCES_DECISION_SCENARIO)
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        parsed = None
    if not isinstance(parsed, dict):
        return None
    if "ignore_blocked_balances" not in parsed:
        return None
    try:
        return bool(parsed.get("ignore_blocked_balances"))
    except Exception:
        return None


def _store_ignore_blocked_balances_decision(
    *, db: Session, client_id: int, ignore_blocked_balances: bool = True, decision: str = "no"
) -> None:
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _IGNORE_BLOCKED_BALANCES_DECISION_SCENARIO
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name=_IGNORE_BLOCKED_BALANCES_DECISION_SCENARIO,
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {"decision": str(decision), "ignore_blocked_balances": bool(ignore_blocked_balances)},
                ensure_ascii=False,
            ),
        )
        db.add(scenario)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _store_pending_pre_retirement_plan_resolution(*, db: Session, client_id: int, payload: dict) -> None:
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name=_PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO,
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload or {}, ensure_ascii=False),
        )
        db.add(scenario)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _pre_retirement_plan_resolution(
    *,
    db: Session,
    client_id: int,
    requested_target: float,
    target_is_net: bool,
    retirement_age: int | None,
    effective_portfolio: Any,
) -> tuple[str, dict | str]:
    has_db_state_sources = False
    try:
        has_db_state_sources = bool(
            db.query(PensionFund).filter(PensionFund.client_id == client_id).count() > 0
        ) or bool(db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).count() > 0)
    except Exception:
        has_db_state_sources = False

    breakdown = compute_effective_plan_target(
        db=db,
        client_id=int(client_id),
        desired_total=float(requested_target),
        target_is_net=bool(target_is_net),
    )
    if breakdown.effective_plan_target <= 0:
        return (
            "done_text",
            "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת.",
        )

    # If the DB already contains any pensions/assets, planning must use the current DB state.
    # In that case, snapshot blocked balances are irrelevant and must not gate the plan flow.
    has_blocked = False
    blocked_decision = None
    if not has_db_state_sources:
        try:
            blocked_decision = _load_blocked_balances_decision(db=db, client_id=client_id)
        except Exception:
            blocked_decision = None

        if blocked_decision is None:
            has_blocked = _detect_blocked_balances_in_snapshot(portfolio=effective_portfolio)

    if has_blocked:
        payload = {
            "requested_target": float(requested_target),
            "target_is_net": bool(target_is_net),
            "retirement_age": int(retirement_age) if retirement_age is not None else None,
        }
        _store_pending_pre_retirement_plan_resolution(db=db, client_id=client_id, payload=payload)
        return (
            "ask_blocked",
            "קיימות יתרות חסומות שיכולות להגדיל את הקצבה.\nהאם לכלול אותן בתכנון?\n\nאפשרויות:\nכן\nלא",
        )

    ignore_blocked_balances_val = True
    if blocked_decision is not None:
        ignore_blocked_balances_val = bool(blocked_decision)

    return (
        "proceed",
        {
            "target_monthly_pension": float(requested_target),
            "target_is_net": bool(target_is_net),
            "retirement_age": int(retirement_age) if retirement_age is not None else None,
            "ignore_blocked_balances": bool(ignore_blocked_balances_val),
        },
    )
