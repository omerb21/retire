import json
from typing import Any

from app.models.client import Client
from app.services.llm_chat.chat_orchestration_helpers import (
    load_latest_target_pension_plan,
    store_latest_target_pension_plan,
    store_latest_target_pension_plan_data,
)
from app.services.llm_chat.message_utils import extract_target_pension_from_message

from app.services.llm_chat.orchestration_utils import (
    compute_default_retirement_date_for_tool_call,
    extract_desired_monthly_income_from_text,
    format_tool_output_for_user_stream,
    infer_desired_income_is_net_explicit,
    sanitize_user_visible_text,
)

from .chat_helpers import _format_system_results_from_cashflow, _infer_target_is_net_explicit
from .stream_formatters import _format_data_awareness_snapshot, _format_list_all_entities
from .stream_more_nested_helpers import _format_system_inventory_snapshot
from .stream_tool_execution import _execute_tool_call


def generate_adjust_reply(*, computed_data, payload, original_user_msg, request, db, effective_portfolio, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    if not isinstance(payload, dict):
        yield (
            "כדי לתקן את תכנית יעד הקצבה אני צריך תכנית יעד אחרונה קיימת. "
            "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של <מספר>' (ואפשר לציין ברוטו/נטו)."
        )
        return

    plan_res = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    raw_target = plan_res.get("target_monthly_pension")
    try:
        target_val = float(raw_target or 0)
    except Exception:
        target_val = 0.0

    explicit_is_net = _infer_target_is_net_explicit(original_user_msg)
    if explicit_is_net is None:
        prev_is_net = payload.get("args", {}).get("target_is_net") if isinstance(payload.get("args"), dict) else None
        prev_mode = "נטו" if prev_is_net is True else "ברוטו"
        yield (
            "כדי לתקן את התכנית צריך להבהיר: היעד שביקשת הוא **ברוטו** או **נטו**?\n\n"
            f"(התכנית האחרונה נבנתה במצב: {prev_mode})\n\n"
            "כתוב אחת מהאפשרויות:\n"
            "- '28000 ברוטו'\n"
            "- '28000 נטו'"
        )
        return

    if target_val <= 0:
        yield (
            "לא הצלחתי לקרוא את יעד הקצבה מתוך התכנית האחרונה. "
            "בבקשה בקש שוב: 'בנה תכנית משיכה לקצבת יעד של 28000' (ברוטו/נטו)."
        )
        return

    plan_args = {
        "target_monthly_pension": float(target_val),
        "target_is_net": bool(explicit_is_net),
    }
    plan_result = _execute_tool_call(
        "BUILD_TARGET_PENSION_PLAN",
        plan_args,
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=False,
        user_approved=True,
        request_id=stream_request_id,
    )

    try:
        store_latest_target_pension_plan(db=db, client_id=request.client_id, tool_result=plan_result)
    except Exception:
        pass
    try:
        store_latest_target_pension_plan_data(db=db, client_id=request.client_id, tool_result=plan_result)
    except Exception:
        pass
    yield (
        "🔧 **פלט כלי (בניית תכנית קצבה - תיקון):**\n"
        + sanitize_user_visible_text(
            format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
        )
    )


def generate_system_results(*, computed_data, original_user_msg, request, db, effective_portfolio, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    birth_date_for_default_date = None
    gender_for_default_date = None
    try:
        client_obj = db.query(Client).filter(Client.id == request.client_id).first()
        birth_date_for_default_date = getattr(client_obj, "birth_date", None) if client_obj else None
        gender_for_default_date = getattr(client_obj, "gender", None) if client_obj else None
    except Exception:
        birth_date_for_default_date = None
        gender_for_default_date = None

    default_retirement_date = compute_default_retirement_date_for_tool_call(
        birth_date=birth_date_for_default_date,
        gender=gender_for_default_date,
        user_message=original_user_msg or "",
    )

    tool_result = _execute_tool_call(
        "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        {"retirement_date": default_retirement_date},
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=False,
        user_approved=True,
        request_id=stream_request_id,
    )

    if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
        yield sanitize_user_visible_text(tool_result)
        return

    yield sanitize_user_visible_text(_format_system_results_from_cashflow(tool_result))


def generate_system_inventory(*, computed_data, request, db, effective_portfolio, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    tool_result = _execute_tool_call(
        "GET_SYSTEM_STATE_SNAPSHOT",
        {},
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=False,
        user_approved=True,
        request_id=stream_request_id,
    )

    if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
        yield sanitize_user_visible_text(tool_result)
        return

    yield sanitize_user_visible_text(_format_system_inventory_snapshot(tool_result))


def generate_data_awareness(*, computed_data, request, db, effective_portfolio, effective_snapshot_at, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    tool_result = _execute_tool_call(
        "GET_SYSTEM_STATE_SNAPSHOT",
        {},
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=False,
        user_approved=True,
        request_id=stream_request_id,
    )

    if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
        yield sanitize_user_visible_text(tool_result)
        return

    yield sanitize_user_visible_text(
        _format_data_awareness_snapshot(
            tool_result,
            effective_portfolio=effective_portfolio,
            effective_snapshot_at=effective_snapshot_at,
        )
    )


def generate_list_all_entities(*, computed_data, request, db, effective_portfolio, effective_snapshot_at, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    tool_result = _execute_tool_call(
        "GET_SYSTEM_STATE_SNAPSHOT",
        {},
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=False,
        user_approved=True,
        request_id=stream_request_id,
    )

    if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
        yield sanitize_user_visible_text(tool_result)
        return

    yield sanitize_user_visible_text(
        _format_list_all_entities(
            tool_result,
            effective_portfolio=effective_portfolio,
            effective_snapshot_at=effective_snapshot_at,
        )
    )


def generate_target_plan(*, computed_data, original_user_msg, request, db, effective_portfolio, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    target_val = None
    try:
        target_val = float(extract_target_pension_from_message(original_user_msg) or 0)
    except Exception:
        target_val = 0.0

    if not target_val or target_val <= 0:
        yield "כדי לבנות תכנית יעד קצבה אני צריך יעד חודשי מספרי (למשל: 28000)."
        return

    lowered = (original_user_msg or "").lower()
    explicit_is_net = None
    if any(t in lowered for t in ("ברוטו", "gross", "bruto")):
        explicit_is_net = False
    elif any(t in lowered for t in ("נטו", "ביד", "אחרי מס", "net")):
        explicit_is_net = True

    if explicit_is_net is None:
        yield (
            "כדי לבנות תכנית יעד קצבה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
            "כתוב אחת מהאפשרויות:\n"
            "- '28000 ברוטו'\n"
            "- '28000 נטו'"
        )
        return

    plan_args = {
        "target_monthly_pension": float(target_val),
        "target_is_net": bool(explicit_is_net),
    }
    plan_result = _execute_tool_call(
        "BUILD_TARGET_PENSION_PLAN",
        plan_args,
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=False,
        user_approved=True,
        request_id=stream_request_id,
    )

    try:
        store_latest_target_pension_plan(db=db, client_id=request.client_id, tool_result=plan_result)
    except Exception:
        pass
    try:
        store_latest_target_pension_plan_data(db=db, client_id=request.client_id, tool_result=plan_result)
    except Exception:
        pass

    yield sanitize_user_visible_text(
        "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
        + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
    )


def generate_cashflow(*, computed_data, original_user_msg, request, db, effective_portfolio, force_max_exemption, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    birth_date_for_default_date = None
    gender_for_default_date = None
    try:
        client_obj = db.query(Client).filter(Client.id == request.client_id).first()
        birth_date_for_default_date = getattr(client_obj, "birth_date", None) if client_obj else None
        gender_for_default_date = getattr(client_obj, "gender", None) if client_obj else None
    except Exception:
        birth_date_for_default_date = None
        gender_for_default_date = None

    default_retirement_date = compute_default_retirement_date_for_tool_call(
        birth_date=birth_date_for_default_date,
        gender=gender_for_default_date,
        user_message=original_user_msg or "",
    )
    desired_income = extract_desired_monthly_income_from_text(original_user_msg)

    desired_income_is_net = infer_desired_income_is_net_explicit(original_user_msg)
    if desired_income is not None and desired_income_is_net is None:
        yield (
            "כדי לבנות תזרים לפי יעד הכנסה אני צריך להבהיר: היעד שציינת הוא **ברוטו** או **נטו**?\n\n"
            "כתוב אחת מהאפשרויות:\n"
            "- '40 אלף ברוטו'\n"
            "- '40 אלף נטו'"
        )
        return

    tool_args: dict[str, Any] = {"retirement_date": default_retirement_date}
    if desired_income is not None:
        tool_args["desired_monthly_income"] = float(desired_income)
    if desired_income_is_net is not None:
        tool_args["desired_income_is_net"] = bool(desired_income_is_net)

    tool_result = _execute_tool_call(
        "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        tool_args,
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        user_approved=True,
        request_id=stream_request_id,
    )

    if isinstance(tool_result, str) and tool_result.strip().lower().startswith("tool error"):
        yield sanitize_user_visible_text(tool_result)
        return
    # Deterministic: always present the tool's own explanation which is built from system state.
    try:
        parsed = json.loads(tool_result) if isinstance(tool_result, str) else {}
    except Exception:
        parsed = {}
    explanation = parsed.get("explanation") if isinstance(parsed, dict) else None
    if isinstance(explanation, str) and explanation.strip():
        yield sanitize_user_visible_text(explanation.strip())
    else:
        yield sanitize_user_visible_text(
            format_tool_output_for_user_stream("RUN_RETIREMENT_CASHFLOW_ANALYSIS", tool_result)
        )
