import json
from datetime import date

from app.models.client import Client
from app.models.scenario import Scenario

from app.services.llm_chat.chat_orchestration_helpers import (
    load_latest_target_pension_plan,
    load_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
    store_latest_target_pension_plan_data,
)
from app.services.llm_chat.message_utils import (
    extract_latest_target_pension_plan_payload,
    extract_target_pension_from_message,
)

from app.services.llm_chat.orchestration_utils import (
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
)
from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
    compute_existing_income_offset_monthly,
)
from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot_models

from .chat_helpers import _infer_target_is_net_explicit
from .stream_formatters import _format_data_awareness_snapshot, _format_list_all_entities
from .stream_more_nested_helpers import _format_system_inventory_snapshot
from .stream_tool_execution import _execute_tool_call

_PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO = "pending_pre_retirement_plan_resolution"
_IGNORE_BLOCKED_BALANCES_DECISION_SCENARIO = "ignore_blocked_balances_decision"


def _load_ignore_blocked_balances_decision(*, db, client_id: int) -> bool:
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
    return bool(parsed.get("ignore_blocked_balances")) is True


def _today() -> date:
    return date.today()


def _coerce_float_safe(value: object) -> float:
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


def _compute_existing_fixed_net_income_monthly(*, db, client_id: int) -> float:
    return compute_existing_income_offset_monthly(
        db=db,
        client_id=client_id,
        target_is_net=True,
    )


def _detect_blocked_balances_in_snapshot(*, portfolio: object) -> bool:
    if not isinstance(portfolio, list) or not portfolio:
        return False
    for item in portfolio:
        if isinstance(item, dict):
            data = item
        else:
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                try:
                    dumped = model_dump()
                    data = dumped if isinstance(dumped, dict) else {}
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


def _store_pending_pre_retirement_plan_resolution(*, db, client_id: int, payload: dict) -> None:
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

    portfolio_for_plan = effective_portfolio
    if (not isinstance(portfolio_for_plan, list) or not portfolio_for_plan) and request.client_id is not None:
        try:
            loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
            if loaded is not None:
                portfolio_for_plan, _snapshot_at = loaded
        except Exception:
            portfolio_for_plan = effective_portfolio

    plan_args = {
        "target_monthly_pension": float(target_val),
        "target_is_net": bool(explicit_is_net),
    }

    existing_income_offset = compute_existing_income_offset_monthly(
        db=db,
        client_id=request.client_id,
        target_is_net=bool(explicit_is_net),
    )
    effective_target = max(float(target_val) - float(existing_income_offset), 0.0)
    if effective_target <= 0:
        yield "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת"
        return

    birth_date = None
    try:
        client_obj = db.query(Client).filter(Client.id == request.client_id).first()
        birth_date = getattr(client_obj, "birth_date", None) if client_obj else None
    except Exception:
        birth_date = None
    try:
        if birth_date == date(1970, 1, 1):
            birth_date = None
    except Exception:
        birth_date = None

    resolved_ret_age, _src = resolve_target_retirement_age(
        original_user_msg,
        birth_date,
        _today(),
        None,
    )
    if resolved_ret_age is not None:
        try:
            plan_args["retirement_age"] = int(resolved_ret_age)
        except Exception:
            pass

    plan_args["target_monthly_pension"] = float(effective_target)
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
    breakdown_lines: list[str] = []
    breakdown_lines.append("✅ חישוב דטרמיניסטי (תיקון):")
    breakdown_lines.append(
        f"- יעד חודשי מבוקש ({'נטו' if explicit_is_net else 'ברוטו'}): {float(target_val):,.0f} ₪"
    )
    breakdown_lines.append(
        f"- קיזוז הכנסות נוספות ({'נטו' if explicit_is_net else 'ברוטו'}): {float(existing_income_offset):,.0f} ₪"
    )
    breakdown_lines.append(f"- יעד קצבה נדרש: {float(effective_target):,.0f} ₪")

    yield (
        sanitize_user_visible_text("\n".join(breakdown_lines))
        + "\n\n🔧 **פלט כלי (בניית תכנית קצבה - תיקון):**\n"
        + sanitize_user_visible_text(format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result))
    )


def generate_system_results(*, computed_data, original_user_msg, request, db, effective_portfolio, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    tool_result = _execute_tool_call(
        "GET_PENSION_PRODUCTS",
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
        format_tool_output_for_user_stream("GET_PENSION_PRODUCTS", tool_result)
    )


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

    portfolio_for_plan = effective_portfolio
    if (not isinstance(portfolio_for_plan, list) or not portfolio_for_plan) and request.client_id is not None:
        try:
            loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
            if loaded is not None:
                portfolio_for_plan, _snapshot_at = loaded
        except Exception:
            portfolio_for_plan = effective_portfolio

    plan_args = {
        "target_monthly_pension": float(target_val),
        "target_is_net": bool(explicit_is_net),
    }

    existing_income_offset = compute_existing_income_offset_monthly(
        db=db,
        client_id=request.client_id,
        target_is_net=bool(explicit_is_net),
    )
    effective_target = max(float(target_val) - float(existing_income_offset), 0.0)
    if effective_target <= 0:
        yield "היעד כבר מושג מהכנסות קיימות, אין צורך בבניית קצבה נוספת"
        return

    ignore_blocked = False
    try:
        ignore_blocked = _load_ignore_blocked_balances_decision(db=db, client_id=request.client_id)
    except Exception:
        ignore_blocked = False

    if (not ignore_blocked) and _detect_blocked_balances_in_snapshot(portfolio=portfolio_for_plan):
        _store_pending_pre_retirement_plan_resolution(
            db=db,
            client_id=request.client_id,
            payload={
                "requested_target": float(target_val),
                "target_is_net": bool(explicit_is_net),
                "retirement_age": None,
            },
        )
        yield "קיימות יתרות חסומות שיכולות להגדיל את הקצבה.\nהאם לכלול אותן בתכנון?\n\nאפשרויות:\nכן\nלא"
        return

    plan_args["target_monthly_pension"] = float(effective_target)
    plan_result = _execute_tool_call(
        "BUILD_TARGET_PENSION_PLAN",
        plan_args,
        request.client_id,
        db,
        pension_portfolio=portfolio_for_plan,
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

    breakdown_lines: list[str] = []
    breakdown_lines.append("✅ חישוב דטרמיניסטי:")
    breakdown_lines.append(
        f"- יעד חודשי מבוקש ({'נטו' if explicit_is_net else 'ברוטו'}): {float(target_val):,.0f} ₪"
    )
    breakdown_lines.append(
        f"- קיזוז הכנסות נוספות ({'נטו' if explicit_is_net else 'ברוטו'}): {float(existing_income_offset):,.0f} ₪"
    )
    breakdown_lines.append(f"- יעד קצבה נדרש: {float(effective_target):,.0f} ₪")

    yield sanitize_user_visible_text(
        "\n".join(breakdown_lines)
        + "\n\n🔧 **פלט כלי (בניית תכנית קצבה):**\n"
        + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
    )


def generate_cashflow(*, computed_data, original_user_msg, request, db, effective_portfolio, force_max_exemption, stream_request_id) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    plan_payload = None
    try:
        plan_payload = extract_latest_target_pension_plan_payload(request.messages)
    except Exception:
        plan_payload = None
    if plan_payload is None and request.client_id is not None:
        try:
            plan_payload = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)
        except Exception:
            plan_payload = None
    if plan_payload is None and request.client_id is not None:
        try:
            plan_payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)
        except Exception:
            plan_payload = None

    if not isinstance(plan_payload, dict):
        yield "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
        return

    plan_res = plan_payload.get("result") if isinstance(plan_payload.get("result"), dict) else {}

    pension_gross = plan_res.get("accumulated_pension")
    pension_net = plan_res.get("estimated_monthly_net")
    pension_tax = plan_res.get("estimated_monthly_tax")
    capital_remaining = plan_res.get("remaining_capital")
    target_achieved = plan_res.get("target_achieved")
    gap_to_target = plan_res.get("gap_to_target")

    yield "כותרת: תזרים (הקרנה) מתוך תוצאת התכנית האחרונה שנבנתה במערכת\n\n"

    if pension_gross is not None:
        try:
            yield f"- קצבה ברוטו (מתוך התכנית): {float(pension_gross):,.0f} ₪/חודש\n"
        except Exception:
            pass
    if pension_tax is not None:
        try:
            yield f"- מס חודשי (מתוך התכנית): {float(pension_tax):,.0f} ₪\n"
        except Exception:
            pass
    if pension_net is not None:
        try:
            yield f"- קצבה נטו (מתוך התכנית): {float(pension_net):,.0f} ₪/חודש\n"
        except Exception:
            pass
    if capital_remaining is not None:
        try:
            yield f"- הון שנותר (מתוך התכנית): {float(capital_remaining):,.0f} ₪\n"
        except Exception:
            pass

    if target_achieved is True:
        yield "\nסטטוס: לפי התכנית האחרונה – היעד הושג, ולכן אין גירעון שמקורו בתזרים.\n"
        return

    # If the plan did not achieve the target, we can surface the gap as-is from the plan result.
    if gap_to_target is not None:
        try:
            gap_val = float(gap_to_target)
        except Exception:
            gap_val = None
        if gap_val is not None and gap_val > 0:
            yield f"\nסטטוס: לפי התכנית האחרונה – קיים פער ליעד (מתוך התכנית): {gap_val:,.0f} ₪/חודש.\n"
            return

    yield "\nסטטוס: לא נמצאה אינדיקציה ברורה בתוצאת התכנית האם היעד הושג או מהו הפער.\n"
