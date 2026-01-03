import json

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
