import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import CurrentEmployer, EmployerGrant, GrantType
from app.models.scenario import Scenario


_BLOCKED_BALANCES_NOTICE_SHOWN_SCENARIO = "blocked_balances_notice_shown"
_CURRENT_EMPLOYER_SEVERANCE_DECISION_SCENARIO = "current_employer_severance_execution_decision"
_PENDING_CURRENT_EMPLOYER_SEVERANCE_TERMINATION_QUESTION_SCENARIO = (
    "pending_current_employer_severance_termination_question"
)
_PENDING_BUILD_TARGET_PLAN_AFTER_TERMINATION_SCENARIO = "pending_build_target_plan_after_termination"


@dataclass
class BlockedBalancesSummary:
    non_settled_severance_amount: float = 0.0
    prior_employers_continuity_rights_amount: float = 0.0
    current_employer_severance_amount: float = 0.0


def termination_already_executed_for_client(*, db: Session, client_id: int) -> bool:
    current_employer = None
    try:
        current_employer = (
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )
    except Exception:
        current_employer = None

    if current_employer is None:
        return False

    grants_count = 0
    try:
        grants_count = (
            db.query(EmployerGrant)
            .filter(
                EmployerGrant.employer_id == current_employer.id,
                GrantType.severance,
            )
            .count()
        )
    except Exception:
        grants_count = 0

    confirmed = False
    try:
        other_grants = current_employer.other_grants or {}
        if isinstance(other_grants, dict):
            confirmed = bool(other_grants.get("termination_confirmed"))
    except Exception:
        confirmed = False

    return bool(confirmed or (grants_count > 0))


def evaluate_blocked_balances_policy_for_build_target_plan(
    *,
    db: Session,
    client_id: int,
    portfolio,
    plan_args: dict,
) -> tuple[str, dict, str | None]:
    if not isinstance(plan_args, dict):
        plan_args = {}

    plan_args = dict(plan_args)
    plan_args["ignore_blocked_balances"] = True

    summary = compute_blocked_balances_summary_from_portfolio(portfolio)

    notice_text = None
    notice_kinds = blocked_balances_notice_kinds(summary)
    if notice_kinds:
        try:
            already_shown = load_blocked_balances_notice_shown(db=db, client_id=client_id)
        except Exception:
            already_shown = False
        if not already_shown:
            try:
                store_blocked_balances_notice_shown(db=db, client_id=client_id, kinds=notice_kinds)
            except Exception:
                pass
            notice_text = (
                "שים לב: קיימות יתרות חסומות בתיק (פיצויים שלא עברו התחשבנות / רצף זכויות). "
                "לפי המדיניות, הן לא ייכללו בבניית תכנית היעד כרגע."
            )

    needs_current_employer_handling = (
        float(getattr(summary, "current_employer_severance_amount", 0) or 0) > 0
    )
    if needs_current_employer_handling:
        try:
            already_executed = termination_already_executed_for_client(db=db, client_id=client_id)
        except Exception:
            already_executed = False

        if not already_executed:
            decision = None
            try:
                decision = load_current_employer_severance_execution_decision(db=db, client_id=client_id)
            except Exception:
                decision = None

            if decision is None:
                try:
                    store_pending_current_employer_severance_termination_question(
                        db=db,
                        client_id=client_id,
                        payload={"plan_args": plan_args},
                    )
                except Exception:
                    pass
                question = (
                    "כדי לכלול פיצויי מעסיק נוכחי בתכנון, צריך לבצע עזיבת עבודה במערכת (דורש אישור).\n"
                    "האם תרצה לבצע עזיבת עבודה עכשיו?\n\nאפשרויות:\nכן\nלא"
                )
                if notice_text:
                    question = notice_text + "\n\n" + question
                return "ask_current_employer_termination", plan_args, question

            if decision == "yes":
                try:
                    store_pending_build_target_plan_after_termination(
                        db=db,
                        client_id=client_id,
                        payload={"plan_args": plan_args},
                    )
                except Exception:
                    pass
                msg = "נדרש אישור לביצוע עזיבת עבודה לפני שנבנה מחדש את תכנית היעד."
                if notice_text:
                    msg = notice_text + "\n\n" + msg
                return "needs_termination_approval", plan_args, msg

    return "proceed", plan_args, notice_text


def blocked_balances_notice_kinds(summary: BlockedBalancesSummary) -> list[str]:
    kinds: list[str] = []
    if float(getattr(summary, "non_settled_severance_amount", 0) or 0) > 0:
        kinds.append("non_settled_severance")
    if float(getattr(summary, "prior_employers_continuity_rights_amount", 0) or 0) > 0:
        kinds.append("prior_employers_continuity_rights")
    return kinds


def has_any_blocked_balances(summary: BlockedBalancesSummary) -> bool:
    return bool(
        float(getattr(summary, "non_settled_severance_amount", 0) or 0) > 0
        or float(getattr(summary, "prior_employers_continuity_rights_amount", 0) or 0) > 0
        or float(getattr(summary, "current_employer_severance_amount", 0) or 0) > 0
    )


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


def compute_blocked_balances_summary_from_portfolio(portfolio: Any) -> BlockedBalancesSummary:
    out = BlockedBalancesSummary()
    if not isinstance(portfolio, list) or not portfolio:
        return out

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

        nested_sources: list[dict[str, Any]] = []
        for key in (
            "specific_amounts",
            "components",
            "selected_components",
            "selected_amounts",
        ):
            nested_val = data.get(key)
            if isinstance(nested_val, dict):
                nested_sources.append(nested_val)

        def _sum_from_all_sources(field: str) -> float:
            total = _coerce_float_safe(data.get(field))
            for src in nested_sources:
                total += _coerce_float_safe(src.get(field))
            return total

        out.non_settled_severance_amount += _sum_from_all_sources("פיצויים_שלא_עברו_התחשבנות")
        out.prior_employers_continuity_rights_amount += _sum_from_all_sources(
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות"
        )
        out.current_employer_severance_amount += _sum_from_all_sources("פיצויים_מעסיק_נוכחי")

    return out


def _load_latest_scenario_payload(*, db: Session, client_id: int, scenario_name: str) -> dict | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == scenario_name)
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


def _store_single_scenario_payload(*, db: Session, client_id: int, scenario_name: str, payload: dict) -> None:
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == scenario_name
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
            scenario_name=scenario_name,
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


def _clear_scenario(*, db: Session, client_id: int, scenario_name: str) -> None:
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == scenario_name
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def load_blocked_balances_notice_shown(*, db: Session, client_id: int) -> bool:
    payload = _load_latest_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_BLOCKED_BALANCES_NOTICE_SHOWN_SCENARIO,
    )
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("shown")) is True


def store_blocked_balances_notice_shown(*, db: Session, client_id: int, kinds: list[str]) -> None:
    payload = {
        "shown": True,
        "shown_at": datetime.now(timezone.utc).isoformat(),
        "kinds": list(kinds or []),
    }
    _store_single_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_BLOCKED_BALANCES_NOTICE_SHOWN_SCENARIO,
        payload=payload,
    )


def load_current_employer_severance_execution_decision(*, db: Session, client_id: int) -> str | None:
    payload = _load_latest_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_CURRENT_EMPLOYER_SEVERANCE_DECISION_SCENARIO,
    )
    if not isinstance(payload, dict):
        return None
    decision = payload.get("decision")
    if decision in {"yes", "no"}:
        return str(decision)
    return None


def store_current_employer_severance_execution_decision(
    *, db: Session, client_id: int, decision: str
) -> None:
    payload = {
        "decision": str(decision),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _store_single_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_CURRENT_EMPLOYER_SEVERANCE_DECISION_SCENARIO,
        payload=payload,
    )


def load_pending_current_employer_severance_termination_question(
    *, db: Session, client_id: int
) -> dict | None:
    return _load_latest_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_PENDING_CURRENT_EMPLOYER_SEVERANCE_TERMINATION_QUESTION_SCENARIO,
    )


def store_pending_current_employer_severance_termination_question(
    *, db: Session, client_id: int, payload: dict
) -> None:
    _store_single_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_PENDING_CURRENT_EMPLOYER_SEVERANCE_TERMINATION_QUESTION_SCENARIO,
        payload=payload,
    )


def clear_pending_current_employer_severance_termination_question(
    *, db: Session, client_id: int
) -> None:
    _clear_scenario(
        db=db,
        client_id=client_id,
        scenario_name=_PENDING_CURRENT_EMPLOYER_SEVERANCE_TERMINATION_QUESTION_SCENARIO,
    )


def load_pending_build_target_plan_after_termination(*, db: Session, client_id: int) -> dict | None:
    return _load_latest_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_PENDING_BUILD_TARGET_PLAN_AFTER_TERMINATION_SCENARIO,
    )


def store_pending_build_target_plan_after_termination(
    *, db: Session, client_id: int, payload: dict
) -> None:
    _store_single_scenario_payload(
        db=db,
        client_id=client_id,
        scenario_name=_PENDING_BUILD_TARGET_PLAN_AFTER_TERMINATION_SCENARIO,
        payload=payload,
    )


def clear_pending_build_target_plan_after_termination(*, db: Session, client_id: int) -> None:
    _clear_scenario(
        db=db,
        client_id=client_id,
        scenario_name=_PENDING_BUILD_TARGET_PLAN_AFTER_TERMINATION_SCENARIO,
    )
