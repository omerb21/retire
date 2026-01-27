import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Scenario


def store_latest_target_pension_plan(*, db: Session, client_id: int, tool_result: str) -> bool:
    payload = _extract_target_plan_payload_from_tool_result(tool_result)
    if not payload:
        return False

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


def store_latest_target_pension_plan_data(*, db: Session, client_id: int, tool_result: str) -> bool:
    payload = _extract_target_plan_payload_from_tool_result(tool_result)
    if not payload:
        return False

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


def _extract_target_plan_payload_from_tool_result(tool_result: str) -> dict | None:
    marker = "###TARGET_PENSION_PLAN_DATA###"
    end_marker = "###END_TARGET_PENSION_PLAN_DATA###"
    if not isinstance(tool_result, str) or not tool_result:
        return None
    if marker not in tool_result or end_marker not in tool_result:
        return None

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
    return parsed if isinstance(parsed, dict) else None
