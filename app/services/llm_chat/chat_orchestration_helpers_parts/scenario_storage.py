import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Scenario
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    load_current_employer_termination_plan_preview,
)
from app.services.llm_chat.pending_approvals import compute_args_hash

_APPROVAL_EXECUTION_RECEIPT_SCENARIO = "approval_execution_receipt"
_DEFAULT_APPROVAL_EXECUTION_RECEIPT_TTL_SECONDS = 5 * 60
_EXECUTION_VETO_SCENARIO = "execution_veto"
_NORMALIZED_TARGET_PLAN_CONTEXT_SCENARIO = "normalized_target_plan_context"
_EXECUTION_VETO_SCOPE_TERMINATION = "termination_execution"


def _log_trace_event_if_possible(
    *, trace_id: str | None, event_type: str, payload: dict
) -> None:
    try:
        from app.services.agent_trace_logger import log_trace_event

        log_trace_event(
            trace_id=trace_id,
            event_type=event_type,
            payload=payload,
        )
    except Exception:
        pass


def _load_latest_scenario_payload(
    *, db: Session, client_id: int, scenario_name: str
) -> dict | None:
    if client_id is None:
        return None
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == scenario_name)
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
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


def _validate_execution_veto_payload(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None
    scope = str(payload.get("scope") or "").strip()
    if scope != _EXECUTION_VETO_SCOPE_TERMINATION:
        return None
    return {
        "veto_active": bool(payload.get("veto_active")),
        "scope": scope,
        "reason_code": (
            str(payload.get("reason_code")).strip()
            if payload.get("reason_code") is not None
            else None
        ),
        "source_text": (
            str(payload.get("source_text")).strip()
            if payload.get("source_text") is not None
            else None
        ),
    }


def store_execution_veto(
    *,
    db: Session,
    client_id: int,
    veto_active: bool,
    scope: str,
    reason_code: str | None = None,
    source_text: str | None = None,
    trace_id: str | None = None,
) -> bool:
    if client_id is None:
        return False
    if str(scope or "").strip() != _EXECUTION_VETO_SCOPE_TERMINATION:
        return False
    payload = {
        "veto_active": bool(veto_active),
        "scope": _EXECUTION_VETO_SCOPE_TERMINATION,
        "reason_code": str(reason_code).strip() if reason_code is not None else None,
        "source_text": str(source_text).strip() if source_text is not None else None,
    }
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _EXECUTION_VETO_SCENARIO
        ).delete(synchronize_session=False)
        db.flush()
        scenario = Scenario(
            client_id=client_id,
            scenario_name=_EXECUTION_VETO_SCENARIO,
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
    _log_trace_event_if_possible(
        trace_id=trace_id,
        event_type="execution_veto_stored",
        payload={
            "veto_active": bool(veto_active),
            "scope": _EXECUTION_VETO_SCOPE_TERMINATION,
        },
    )
    return True


def load_execution_veto(
    *, db: Session, client_id: int, trace_id: str | None = None
) -> dict | None:
    payload = _validate_execution_veto_payload(
        _load_latest_scenario_payload(
            db=db,
            client_id=client_id,
            scenario_name=_EXECUTION_VETO_SCENARIO,
        )
    )
    if payload is None:
        return None
    _log_trace_event_if_possible(
        trace_id=trace_id,
        event_type="execution_veto_loaded",
        payload={
            "veto_active": bool(payload.get("veto_active")),
            "scope": str(payload.get("scope") or ""),
        },
    )
    return payload


def clear_execution_veto(
    *,
    db: Session,
    client_id: int,
    scope: str,
    trace_id: str | None = None,
) -> bool:
    if client_id is None:
        return False
    if str(scope or "").strip() != _EXECUTION_VETO_SCOPE_TERMINATION:
        return False
    existing = _validate_execution_veto_payload(
        _load_latest_scenario_payload(
            db=db,
            client_id=client_id,
            scenario_name=_EXECUTION_VETO_SCENARIO,
        )
    )
    if existing is None:
        return False
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _EXECUTION_VETO_SCENARIO
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
    _log_trace_event_if_possible(
        trace_id=trace_id,
        event_type="execution_veto_cleared",
        payload={"scope": _EXECUTION_VETO_SCOPE_TERMINATION},
    )
    return True


def _validate_normalized_target_plan_context(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None
    required_keys = (
        "requested_target",
        "target_mode",
        "offset_used",
        "effective_target",
        "retirement_age",
    )
    if any(key not in payload for key in required_keys):
        return None
    target_mode = str(payload.get("target_mode") or "").strip()
    if target_mode not in {"net", "gross"}:
        return None
    try:
        requested_target = float(payload.get("requested_target") or 0)
        offset_used = float(payload.get("offset_used") or 0)
        effective_target = float(payload.get("effective_target") or 0)
    except Exception:
        return None
    retirement_age_raw = payload.get("retirement_age")
    retirement_age = None
    if retirement_age_raw is not None:
        try:
            retirement_age = int(retirement_age_raw)
        except Exception:
            return None
    normalized = {
        "requested_target": requested_target,
        "target_mode": target_mode,
        "offset_used": offset_used,
        "effective_target": effective_target,
        "retirement_age": retirement_age,
    }
    if payload.get("accumulated_pension") is not None:
        try:
            normalized["accumulated_pension"] = float(
                payload.get("accumulated_pension") or 0
            )
        except Exception:
            pass
    raw_payload_keys = payload.get("raw_payload_keys")
    if isinstance(raw_payload_keys, list):
        normalized["raw_payload_keys"] = [str(item) for item in raw_payload_keys]
    return normalized


def store_normalized_target_plan_context(
    *,
    db: Session,
    client_id: int,
    requested_target: float,
    target_mode: str,
    offset_used: float,
    effective_target: float,
    retirement_age: int | None,
    accumulated_pension: float | None = None,
    raw_payload_keys: list[str] | None = None,
    trace_id: str | None = None,
) -> bool:
    if client_id is None:
        return False
    target_mode_value = str(target_mode or "").strip().lower()
    if target_mode_value not in {"net", "gross"}:
        return False
    payload = {
        "requested_target": float(requested_target or 0),
        "target_mode": target_mode_value,
        "offset_used": float(offset_used or 0),
        "effective_target": float(effective_target or 0),
        "retirement_age": int(retirement_age) if retirement_age is not None else None,
    }
    if accumulated_pension is not None:
        payload["accumulated_pension"] = float(accumulated_pension or 0)
    if isinstance(raw_payload_keys, list):
        payload["raw_payload_keys"] = [str(item) for item in raw_payload_keys]
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _NORMALIZED_TARGET_PLAN_CONTEXT_SCENARIO
        ).delete(synchronize_session=False)
        db.flush()
        scenario = Scenario(
            client_id=client_id,
            scenario_name=_NORMALIZED_TARGET_PLAN_CONTEXT_SCENARIO,
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
    _log_trace_event_if_possible(
        trace_id=trace_id,
        event_type="normalized_target_plan_context_stored",
        payload={
            "target_mode": target_mode_value,
            "effective_target": float(effective_target or 0),
        },
    )
    return True


def load_normalized_target_plan_context(
    *, db: Session, client_id: int, trace_id: str | None = None
) -> dict | None:
    payload = _validate_normalized_target_plan_context(
        _load_latest_scenario_payload(
            db=db,
            client_id=client_id,
            scenario_name=_NORMALIZED_TARGET_PLAN_CONTEXT_SCENARIO,
        )
    )
    if payload is None:
        return None
    _log_trace_event_if_possible(
        trace_id=trace_id,
        event_type="normalized_target_plan_context_loaded",
        payload={"source": "normalized"},
    )
    return payload


def clear_normalized_target_plan_context(*, db: Session, client_id: int) -> bool:
    if client_id is None:
        return False
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _NORMALIZED_TARGET_PLAN_CONTEXT_SCENARIO
        ).delete(synchronize_session=False)
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def was_approval_execution_recently_recorded(
    *, db: Session, client_id: int, tool_name: str, tool_args: dict
) -> bool:
    if client_id is None:
        return False
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False
    if not isinstance(tool_args, dict):
        tool_args = {}

    args_hash = compute_args_hash(tool_args)
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == _APPROVAL_EXECUTION_RECEIPT_SCENARIO)
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
        return False
    if not isinstance(parsed, dict):
        return False
    if str(parsed.get("tool_name") or "").strip() != tool_name:
        return False
    if str(parsed.get("args_hash") or "").strip() != args_hash:
        return False

    expires_raw = parsed.get("expires_at")
    if isinstance(expires_raw, str) and expires_raw.strip():
        try:
            expires_at = datetime.fromisoformat(expires_raw)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return expires_at > datetime.now(timezone.utc)
        except Exception:
            return False
    return False


def store_approval_execution_receipt(
    *,
    db: Session,
    client_id: int,
    tool_name: str,
    tool_args: dict,
    ttl_seconds: int = _DEFAULT_APPROVAL_EXECUTION_RECEIPT_TTL_SECONDS,
) -> bool:
    if client_id is None:
        return False
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False
    if not isinstance(tool_args, dict):
        tool_args = {}

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        seconds=int(ttl_seconds or _DEFAULT_APPROVAL_EXECUTION_RECEIPT_TTL_SECONDS)
    )
    args_hash = compute_args_hash(tool_args)

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _APPROVAL_EXECUTION_RECEIPT_SCENARIO
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False

    payload = {
        "tool_name": tool_name,
        "args_hash": args_hash,
        "executed_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name=_APPROVAL_EXECUTION_RECEIPT_SCENARIO,
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def _safe_float(value: object) -> float:
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


def _derive_execution_plan_accounts_from_sources_used(
    sources_used: object,
) -> list[dict]:
    sources_list = sources_used if isinstance(sources_used, list) else []
    enriched: list[dict] = []
    for src in sources_list:
        if not isinstance(src, dict):
            continue
        src_type = str(src.get("source_type") or "").strip()
        if src_type not in {"pension_fund", "pension_fund_from_portfolio"}:
            continue
        acc_id = src.get("account_number")
        if acc_id is None:
            acc_id = src.get("source_id")
        if acc_id is None:
            continue
        component = src.get("component_field")
        if component is None:
            component = src.get("fund_type")
        if component is None:
            component = "unknown"
        amount_to_convert = _safe_float(src.get("balance_used"))
        expected_monthly_pension = _safe_float(src.get("pension_used"))
        if amount_to_convert <= 0 or expected_monthly_pension <= 0:
            continue
        enriched.append(
            {
                "account_id": str(acc_id),
                "component": str(component),
                "amount_to_convert": float(amount_to_convert),
                "expected_monthly_pension": float(expected_monthly_pension),
            }
        )
    return enriched


def _derive_execution_plan_accounts_from_plan_steps(
    *,
    db: Session,
    client_id: int,
    plan_steps: object,
) -> list[dict]:
    steps = plan_steps if isinstance(plan_steps, list) else []
    if not steps:
        return []

    snapshot_by_name: dict[str, str] = {}
    try:
        from app.services.llm_chat.chat_orchestration_helpers_parts.target_plan_conversion import (
            _clean_account_name_for_transform,
        )
        from app.services.pension_portfolio.snapshot_loader import (
            load_latest_pension_portfolio_snapshot,
        )

        loaded = load_latest_pension_portfolio_snapshot(db=db, client_id=client_id)
        if isinstance(loaded, tuple) and len(loaded) == 2:
            portfolio = loaded[0]
        else:
            portfolio = None
        if isinstance(portfolio, list):
            for item in portfolio:
                if not isinstance(item, dict):
                    continue
                acc_num = str(
                    item.get("account_number")
                    or item.get("מספר_חשבון")
                    or item.get("מספר חשבון")
                    or item.get("מספר-חשבון")
                    or ""
                ).strip()
                if not acc_num:
                    continue
                name_raw = (
                    item.get("account_name")
                    or item.get("שם_תכנית")
                    or item.get("שם תכנית")
                    or ""
                )
                name = _clean_account_name_for_transform(str(name_raw))
                if name:
                    snapshot_by_name[name] = acc_num
    except Exception:
        snapshot_by_name = {}

    aggregated: dict[tuple[str, str], dict] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue

        acc_id_raw = step.get("account_number")
        if acc_id_raw is None:
            acc_id_raw = step.get("account_id")
        if acc_id_raw is None:
            acc_id_raw = step.get("account")

        acc_id = str(acc_id_raw or "").strip()
        if not acc_id:
            src_name = str(step.get("source_name") or "").strip()
            if src_name:
                try:
                    from app.services.llm_chat.chat_orchestration_helpers_parts.target_plan_conversion import (
                        _clean_account_name_for_transform,
                    )

                    cleaned = _clean_account_name_for_transform(src_name)
                except Exception:
                    cleaned = src_name
                acc_id = str(snapshot_by_name.get(cleaned) or "").strip()

        if not acc_id:
            continue

        component_raw = step.get("component_field")
        if component_raw is None:
            component_raw = step.get("component")
        if component_raw is None:
            component_raw = step.get("field")
        component = str(component_raw or "").strip()
        if not component:
            continue

        amount_to_convert = _safe_float(step.get("amount_to_convert"))
        if amount_to_convert <= 0:
            amount_to_convert = _safe_float(step.get("balance_used"))
        if amount_to_convert <= 0:
            amount_to_convert = _safe_float(step.get("amount"))
        if amount_to_convert <= 0:
            pension_added = _safe_float(step.get("pension_added"))
            annuity_factor = _safe_float(step.get("annuity_factor"))
            if pension_added > 0 and annuity_factor > 0:
                amount_to_convert = float(pension_added) * float(annuity_factor)
        if amount_to_convert <= 0:
            continue

        expected_monthly_pension = _safe_float(step.get("expected_monthly_pension"))
        if expected_monthly_pension <= 0:
            expected_monthly_pension = _safe_float(step.get("pension_used"))
        if expected_monthly_pension <= 0:
            expected_monthly_pension = _safe_float(step.get("pension_added"))

        key = (acc_id, component)
        row = aggregated.get(key)
        if row is None:
            row = {
                "account_id": acc_id,
                "component": component,
                "amount_to_convert": 0.0,
                "expected_monthly_pension": 0.0,
            }
            aggregated[key] = row

        row["amount_to_convert"] = float(row.get("amount_to_convert") or 0) + float(
            amount_to_convert
        )
        if expected_monthly_pension > 0:
            row["expected_monthly_pension"] = float(
                row.get("expected_monthly_pension") or 0
            ) + float(expected_monthly_pension)

    return list(aggregated.values())


def store_latest_target_pension_plan(
    *, db: Session, client_id: int, tool_result: object
) -> bool:
    payload = _extract_target_plan_payload_from_tool_result(tool_result)
    if not payload:
        return False
    try:
        plan_res = (
            payload.get("result") if isinstance(payload.get("result"), dict) else None
        )
        if isinstance(plan_res, dict):
            plan_steps = plan_res.get("plan_steps")
            sources_used = plan_res.get("sources_used")

            has_steps = isinstance(plan_steps, list) and bool(plan_steps)
            has_sources = isinstance(sources_used, list) and bool(sources_used)

            execution_plan = (
                plan_res.get("execution_plan")
                if isinstance(plan_res.get("execution_plan"), dict)
                else None
            )
            raw_accounts = (
                execution_plan.get("accounts")
                if isinstance(execution_plan, dict)
                else None
            )
            accounts = raw_accounts if isinstance(raw_accounts, list) else []

            if (has_steps or has_sources) and (not accounts):
                enriched = _derive_execution_plan_accounts_from_sources_used(
                    sources_used
                )
                if not enriched:
                    enriched = _derive_execution_plan_accounts_from_plan_steps(
                        db=db,
                        client_id=client_id,
                        plan_steps=plan_steps,
                    )

                if enriched:
                    execution_plan = (
                        dict(execution_plan) if isinstance(execution_plan, dict) else {}
                    )
                    execution_plan["accounts"] = enriched
                    plan_res = dict(plan_res)
                    plan_res["execution_plan"] = execution_plan
                    payload = dict(payload)
                    payload["result"] = plan_res
                else:
                    execution_plan = (
                        dict(execution_plan) if isinstance(execution_plan, dict) else {}
                    )
                    execution_plan["accounts"] = []
                    execution_plan.setdefault(
                        "non_executable_reason",
                        "תכנית היעד האחרונה אינה כוללת רכיבים לביצוע כרגע. נסה לבנות מחדש תכנית יעד או להשלים נתונים חסרים.",
                    )
                    plan_res = dict(plan_res)
                    plan_res["execution_plan"] = execution_plan
                    payload = dict(payload)
                    payload["result"] = plan_res
            elif (not has_steps) and (not has_sources):
                execution_plan = (
                    dict(execution_plan) if isinstance(execution_plan, dict) else {}
                )
                execution_plan["accounts"] = []
                execution_plan.setdefault(
                    "non_executable_reason",
                    "תכנית היעד האחרונה לא כוללת מקורות (plan_steps/sources_used) ולכן אינה ניתנת לביצוע. יש לבנות תכנית יעד מחדש.",
                )
                plan_res = dict(plan_res)
                plan_res["execution_plan"] = execution_plan
                payload = dict(payload)
                payload["result"] = plan_res
    except Exception:
        pass

    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    meta = dict(meta)
    meta["operation_type"] = "BUILD_TARGET_PENSION_PLAN"
    meta["stored_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload = dict(payload)
    payload["_meta"] = meta

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name="target_pension_plan",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def store_pending_approval_request(
    *, db: Session, client_id: int, tool_name: str, tool_args: dict
) -> bool:
    if client_id is None:
        return False
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False
    if not isinstance(tool_args, dict):
        tool_args = {}

    if tool_name == "PROCESS_TERMINATION":
        approval_id = tool_args.get("approval_id")
        if not isinstance(approval_id, str) or not approval_id.strip():
            tool_args["approval_id"] = str(uuid4())

        preview_id = tool_args.get("preview_id")
        if not isinstance(preview_id, str) or not preview_id.strip():
            try:
                preview_payload = load_current_employer_termination_plan_preview(
                    db=db,
                    client_id=int(client_id),
                )
            except Exception:
                preview_payload = None
            preview_id = (
                preview_payload.get("preview_id")
                if isinstance(preview_payload, dict)
                else None
            )
            if isinstance(preview_id, str) and preview_id.strip():
                tool_args["preview_id"] = preview_id.strip()

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_approval"
        ).delete(synchronize_session=False)
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "approval_executed"
        ).delete(synchronize_session=False)
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _APPROVAL_EXECUTION_RECEIPT_SCENARIO
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=15)

    try:
        payload = {
            "tool_name": tool_name,
            "arguments": tool_args,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        scenario = Scenario(
            client_id=client_id,
            scenario_name="pending_approval",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_pending_approval_request(
    *, db: Session, client_id: int
) -> tuple[str, dict] | None:
    if client_id is None:
        return None
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
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
    if not isinstance(parsed, dict):
        return None
    tool_name = parsed.get("tool_name")
    tool_args = parsed.get("arguments")
    if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
        return None
    return tool_name, tool_args


def clear_pending_approval_request(*, db: Session, client_id: int) -> bool:
    if client_id is None:
        return False
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_approval"
        ).delete(synchronize_session=False)
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def store_undo_snapshot(
    *, db: Session, client_id: int, snapshot_payload: dict
) -> int | None:
    if client_id is None:
        return None
    if not isinstance(snapshot_payload, dict):
        snapshot_payload = {"raw": str(snapshot_payload or "")}

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "undo_snapshot"
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None

    try:
        meta = (
            snapshot_payload.get("_meta")
            if isinstance(snapshot_payload.get("_meta"), dict)
            else {}
        )
        meta = dict(meta)
        meta["stored_at_utc"] = datetime.now(timezone.utc).isoformat()
        snapshot_payload = dict(snapshot_payload)
        snapshot_payload["_meta"] = meta

        scenario = Scenario(
            client_id=client_id,
            scenario_name="undo_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(snapshot_payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return int(getattr(scenario, "id", 0) or 0) or None
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None


def load_undo_snapshot(*, db: Session, client_id: int) -> tuple[int, dict] | None:
    if client_id is None:
        return None
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "undo_snapshot")
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
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
    if not isinstance(parsed, dict):
        return None

    scenario_id = int(getattr(row, "id", 0) or 0)
    if scenario_id <= 0:
        return None
    return scenario_id, parsed


def clear_undo_snapshot(*, db: Session, client_id: int) -> bool:
    if client_id is None:
        return False
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "undo_snapshot"
        ).delete(synchronize_session=False)
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_latest_target_pension_plan(*, db: Session, client_id: int) -> dict | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "target_pension_plan")
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


def _normalize_recent_target_plan_payload(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}

    retirement_age_raw = args.get("retirement_age")
    if retirement_age_raw is None:
        retirement_age_raw = result.get("retirement_age")
    if retirement_age_raw is None:
        retirement_age_raw = result.get("target_retirement_age")

    retirement_age = None
    if retirement_age_raw is not None:
        try:
            retirement_age = int(retirement_age_raw)
        except Exception:
            retirement_age = None

    target_monthly_pension = None
    target_raw = args.get("target_monthly_pension")
    if target_raw is None:
        target_raw = result.get("target_monthly_pension")
    if target_raw is not None:
        try:
            target_monthly_pension = float(target_raw)
        except Exception:
            target_monthly_pension = None

    target_is_net_raw = args.get("target_is_net")
    if target_is_net_raw is None:
        target_is_net_raw = result.get("target_is_net")
    target_is_net = None
    if target_is_net_raw is not None:
        target_is_net = bool(target_is_net_raw)

    return {
        "payload": payload,
        "retirement_age": retirement_age,
        "target_monthly_pension": target_monthly_pension,
        "target_is_net": target_is_net,
        "stored_at_utc": str(meta.get("stored_at_utc") or "").strip() or None,
    }


def load_recent_target_pension_plans(
    *, db: Session, client_id: int, limit: int = 10
) -> list[dict]:
    if client_id is None:
        return []
    try:
        limit_int = max(1, int(limit or 10))
    except Exception:
        limit_int = 10

    try:
        rows = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "target_pension_plan")
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
            .limit(limit_int * 3)
            .all()
        )
    except Exception:
        rows = []

    normalized_rows: list[dict] = []
    seen_keys: set[tuple[object, object, object]] = set()
    for row in rows:
        params = getattr(row, "parameters", None)
        if not params:
            continue
        try:
            parsed = json.loads(params)
        except Exception:
            continue
        normalized = _normalize_recent_target_plan_payload(parsed)
        if normalized is None:
            continue
        dedupe_key = (
            normalized.get("retirement_age"),
            normalized.get("target_monthly_pension"),
            normalized.get("target_is_net"),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        normalized_rows.append(normalized)
        if len(normalized_rows) >= limit_int:
            break
    return normalized_rows


def store_latest_retirement_cashflow_analysis(
    *, db: Session, client_id: int, tool_result: str
) -> bool:
    if client_id is None:
        return False

    payload: dict
    try:
        parsed = json.loads(tool_result) if isinstance(tool_result, str) else None
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        payload = dict(parsed)
    else:
        payload = {"raw": str(tool_result or "")}

    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    meta = dict(meta)
    meta["operation_type"] = "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
    meta["stored_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["_meta"] = meta

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name="retirement_cashflow_analysis",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_latest_retirement_cashflow_analysis(
    *, db: Session, client_id: int
) -> dict | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "retirement_cashflow_analysis")
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


def store_latest_target_pension_plan_data(
    *, db: Session, client_id: int, tool_result: object
) -> bool:
    payload = _extract_target_plan_payload_from_tool_result(tool_result)
    if not payload:
        return False

    try:
        plan_res = (
            payload.get("result") if isinstance(payload.get("result"), dict) else None
        )
        if isinstance(plan_res, dict):
            plan_steps = plan_res.get("plan_steps")
            sources_used = plan_res.get("sources_used")

            has_steps = isinstance(plan_steps, list) and bool(plan_steps)
            has_sources = isinstance(sources_used, list) and bool(sources_used)

            execution_plan = (
                plan_res.get("execution_plan")
                if isinstance(plan_res.get("execution_plan"), dict)
                else None
            )
            raw_accounts = (
                execution_plan.get("accounts")
                if isinstance(execution_plan, dict)
                else None
            )
            accounts = raw_accounts if isinstance(raw_accounts, list) else []

            if (has_steps or has_sources) and (not accounts):
                enriched = _derive_execution_plan_accounts_from_sources_used(
                    sources_used
                )
                if not enriched:
                    enriched = _derive_execution_plan_accounts_from_plan_steps(
                        db=db,
                        client_id=client_id,
                        plan_steps=plan_steps,
                    )

                if enriched:
                    execution_plan = (
                        dict(execution_plan) if isinstance(execution_plan, dict) else {}
                    )
                    execution_plan["accounts"] = enriched
                    plan_res = dict(plan_res)
                    plan_res["execution_plan"] = execution_plan
                    payload = dict(payload)
                    payload["result"] = plan_res
                else:
                    execution_plan = (
                        dict(execution_plan) if isinstance(execution_plan, dict) else {}
                    )
                    execution_plan["accounts"] = []
                    execution_plan.setdefault(
                        "non_executable_reason",
                        "תכנית היעד האחרונה אינה כוללת רכיבים לביצוע כרגע. נסה לבנות מחדש תכנית יעד או להשלים נתונים חסרים.",
                    )
                    plan_res = dict(plan_res)
                    plan_res["execution_plan"] = execution_plan
                    payload = dict(payload)
                    payload["result"] = plan_res
            elif (not has_steps) and (not has_sources):
                execution_plan = (
                    dict(execution_plan) if isinstance(execution_plan, dict) else {}
                )
                execution_plan["accounts"] = []
                execution_plan.setdefault(
                    "non_executable_reason",
                    "תכנית היעד האחרונה לא כוללת מקורות (plan_steps/sources_used) ולכן אינה ניתנת לביצוע. יש לבנות תכנית יעד מחדש.",
                )
                plan_res = dict(plan_res)
                plan_res["execution_plan"] = execution_plan
                payload = dict(payload)
                payload["result"] = plan_res
    except Exception:
        pass

    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    meta = dict(meta)
    meta["operation_type"] = "BUILD_TARGET_PENSION_PLAN"
    meta["stored_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload = dict(payload)
    payload["_meta"] = meta

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name="target_pension_plan_data",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_latest_target_pension_plan_data(*, db: Session, client_id: int) -> dict | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "target_pension_plan_data")
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


def store_pending_plan_target_marker(
    *,
    db: Session,
    client_id: int,
    ttl_seconds: int = 300,
    source: str = "",
    pending_retirement_age: int | None = None,
    pending_retirement_date: str | None = None,
) -> bool:
    if client_id is None:
        return False
    try:
        ttl_seconds_int = int(ttl_seconds or 0)
    except Exception:
        ttl_seconds_int = 300
    if ttl_seconds_int <= 0:
        ttl_seconds_int = 300

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds_int)
    payload = {
        "kind": "pending_plan_target",
        "active": True,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "_meta": {"source": str(source or "").strip()},
    }

    if pending_retirement_age is not None:
        try:
            age_val = int(pending_retirement_age)
        except Exception:
            age_val = None
        if age_val is not None and 40 <= age_val <= 80:
            payload["pending_retirement_age"] = int(age_val)

    if isinstance(pending_retirement_date, str) and pending_retirement_date.strip():
        payload["pending_retirement_date"] = pending_retirement_date.strip()

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_plan_target"
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name="pending_plan_target",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_pending_plan_target_marker(*, db: Session, client_id: int) -> dict | None:
    if client_id is None:
        return None
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
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
    if not isinstance(parsed, dict):
        return None
    if str(parsed.get("kind") or "").strip() != "pending_plan_target":
        return None
    if parsed.get("active", True) is False:
        return None

    expires_raw = parsed.get("expires_at")
    if isinstance(expires_raw, str) and expires_raw.strip():
        try:
            expires_at = datetime.fromisoformat(expires_raw.strip())
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at:
                parsed = dict(parsed)
                parsed["_expired"] = True
        except Exception:
            pass
    return parsed


def clear_pending_plan_target_marker(*, db: Session, client_id: int) -> bool:
    if client_id is None:
        return False
    try:
        (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .delete(synchronize_session=False)
        )
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def _extract_target_plan_payload_from_tool_result(tool_result: object) -> dict | None:
    parsed: object | None = None

    if isinstance(tool_result, dict):
        parsed = tool_result
    elif isinstance(tool_result, str) and tool_result:
        marker = "###TARGET_PENSION_PLAN_DATA###"
        end_marker = "###END_TARGET_PENSION_PLAN_DATA###"

        if marker in tool_result and end_marker in tool_result:
            start = tool_result.rfind(marker)
            end = tool_result.find(end_marker, start + len(marker))
            if start < 0 or end < 0 or end <= start:
                return None
            raw_json = tool_result[start + len(marker) : end].strip()
            if not raw_json:
                return None
            try:
                parsed = json.loads(raw_json)
            except Exception:
                return None
        else:
            try:
                parsed = json.loads(tool_result)
            except Exception:
                parsed = None

    if not isinstance(parsed, dict):
        return None

    if isinstance(parsed.get("tool_name"), str) and isinstance(
        parsed.get("result"), dict
    ):
        payload = dict(parsed)
        if not isinstance(payload.get("args"), dict):
            args = payload.get("arguments")
            payload["args"] = args if isinstance(args, dict) else {}
        return payload

    tool_name = parsed.get("tool_name")
    if not isinstance(tool_name, str):
        tool_name = parsed.get("name")
    if not isinstance(tool_name, str):
        try:
            is_success = bool(parsed.get("success"))
        except Exception:
            is_success = False
        if is_success and isinstance(parsed.get("result"), dict):
            tool_name = "BUILD_TARGET_PENSION_PLAN"

    res = parsed.get("result")
    if isinstance(tool_name, str) and isinstance(res, dict):
        args = parsed.get("args")
        if not isinstance(args, dict):
            args = parsed.get("arguments")
        if not isinstance(args, dict):
            args = {}
        payload = dict(parsed)
        payload["tool_name"] = tool_name
        payload["args"] = args
        payload["result"] = res
        return payload

    return None
