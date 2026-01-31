import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Scenario


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


def _derive_execution_plan_accounts_from_sources_used(sources_used: object) -> list[dict]:
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
        from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot
        from app.services.llm_chat.chat_orchestration_helpers_parts.target_plan_conversion import (
            _clean_account_name_for_transform,
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

        row["amount_to_convert"] = float(row.get("amount_to_convert") or 0) + float(amount_to_convert)
        if expected_monthly_pension > 0:
            row["expected_monthly_pension"] = float(row.get("expected_monthly_pension") or 0) + float(
                expected_monthly_pension
            )

    return list(aggregated.values())


def store_latest_target_pension_plan(*, db: Session, client_id: int, tool_result: object) -> bool:
    payload = _extract_target_plan_payload_from_tool_result(tool_result)
    if not payload:
        return False

    try:
        plan_res = payload.get("result") if isinstance(payload.get("result"), dict) else None
        if isinstance(plan_res, dict):
            target_achieved = bool(plan_res.get("target_achieved"))
            plan_steps = plan_res.get("plan_steps")
            sources_used = plan_res.get("sources_used")

            has_steps = isinstance(plan_steps, list) and bool(plan_steps)
            has_sources = isinstance(sources_used, list) and bool(sources_used)

            execution_plan = (
                plan_res.get("execution_plan")
                if isinstance(plan_res.get("execution_plan"), dict)
                else None
            )
            raw_accounts = execution_plan.get("accounts") if isinstance(execution_plan, dict) else None
            accounts = raw_accounts if isinstance(raw_accounts, list) else []

            if target_achieved and (has_steps or has_sources) and (not accounts):
                enriched = _derive_execution_plan_accounts_from_sources_used(sources_used)
                if not enriched:
                    enriched = _derive_execution_plan_accounts_from_plan_steps(
                        db=db,
                        client_id=client_id,
                        plan_steps=plan_steps,
                    )

                if enriched:
                    execution_plan = dict(execution_plan) if isinstance(execution_plan, dict) else {}
                    execution_plan["accounts"] = enriched
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

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_approval"
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False

    try:
        payload = {"tool_name": tool_name, "arguments": tool_args}
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


def load_pending_approval_request(*, db: Session, client_id: int) -> tuple[str, dict] | None:
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


def store_undo_snapshot(*, db: Session, client_id: int, snapshot_payload: dict) -> int | None:
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
        meta = snapshot_payload.get("_meta") if isinstance(snapshot_payload.get("_meta"), dict) else {}
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


def load_latest_retirement_cashflow_analysis(*, db: Session, client_id: int) -> dict | None:
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


def store_latest_target_pension_plan_data(*, db: Session, client_id: int, tool_result: object) -> bool:
    payload = _extract_target_plan_payload_from_tool_result(tool_result)
    if not payload:
        return False

    try:
        plan_res = payload.get("result") if isinstance(payload.get("result"), dict) else None
        if isinstance(plan_res, dict):
            target_achieved = bool(plan_res.get("target_achieved"))
            plan_steps = plan_res.get("plan_steps")
            sources_used = plan_res.get("sources_used")

            has_steps = isinstance(plan_steps, list) and bool(plan_steps)
            has_sources = isinstance(sources_used, list) and bool(sources_used)

            execution_plan = (
                plan_res.get("execution_plan")
                if isinstance(plan_res.get("execution_plan"), dict)
                else None
            )
            raw_accounts = execution_plan.get("accounts") if isinstance(execution_plan, dict) else None
            accounts = raw_accounts if isinstance(raw_accounts, list) else []

            if target_achieved and (has_steps or has_sources) and (not accounts):
                enriched = _derive_execution_plan_accounts_from_sources_used(sources_used)
                if not enriched:
                    enriched = _derive_execution_plan_accounts_from_plan_steps(
                        db=db,
                        client_id=client_id,
                        plan_steps=plan_steps,
                    )

                if enriched:
                    execution_plan = dict(execution_plan) if isinstance(execution_plan, dict) else {}
                    execution_plan["accounts"] = enriched
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

    if isinstance(parsed.get("tool_name"), str) and isinstance(parsed.get("result"), dict):
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
