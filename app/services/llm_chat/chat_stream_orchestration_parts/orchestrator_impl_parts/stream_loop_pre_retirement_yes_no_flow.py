import json

from fastapi.responses import StreamingResponse

from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_pre_retirement_plan_resolution import (
    _store_ignore_blocked_balances_decision,
 )
from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot_models


def _has_positive_component_amounts(raw: object) -> bool:
    if not isinstance(raw, dict) or not raw:
        return False
    for _k, v in raw.items():
        try:
            if float(v or 0) > 0:
                return True
        except Exception:
            continue
    return False


def _accounts_are_thin(accounts: object) -> bool:
    if not isinstance(accounts, list) or not accounts:
        return True

    for acc in accounts:
        if not isinstance(acc, dict):
            return True

        raw_balance = acc.get("balance")
        if raw_balance is None:
            raw_balance = acc.get("יתרה")
        if raw_balance is None:
            raw_balance = acc.get("current_balance")

        try:
            if float(raw_balance or 0) > 0:
                continue
        except Exception:
            pass

        if _has_positive_component_amounts(acc.get("specific_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_components")):
            continue

        return True

    return False


def _maybe_handle_pre_retirement_plan_resolution_yes_no(
    *,
    request,
    db,
    stream_request_id: str,
    lowered_user_msg: str,
    load_pending_pre_retirement_plan_resolution,
    clear_pending_pre_retirement_plan_resolution,
    load_latest_pension_portfolio_snapshot_models,
    coerce_float_safe,
    compute_existing_income_offset_monthly,
    build_transform_accounts_from_portfolio,
    execute_tool_call,
    sanitize_user_visible_text,
    format_tool_output_for_user_stream,
    store_pending_approval_request,
    build_approval_request_ui_action,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
    clear_pending_plan_target_marker,
    clear_pending_approval_request,
 ):
    normalized = (lowered_user_msg or "").strip()
    answer = None
    if normalized in {"כן", "לא"}:
        answer = normalized
    else:
        for token in ("כן", "לא"):
            if normalized.startswith(token):
                rest = normalized[len(token) :]
                if not rest:
                    answer = token
                    break
                if rest[:1] in {" ", "\t", "\n", ".", ",", "!", "?", ":", ";", "-", "–", "—"}:
                    answer = token
                    break

    if answer is None:
        return None

    pending_payload = None
    try:
        pending_payload = load_pending_pre_retirement_plan_resolution(
            db=db,
            client_id=request.client_id,
        )
    except Exception:
        pending_payload = None

    if not (isinstance(pending_payload, dict) and pending_payload.get("requested_target") is not None):
        return None

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    try:
        loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded
    except Exception:
        pass

    requested_target = coerce_float_safe(pending_payload.get("requested_target"))
    target_is_net_val = bool(pending_payload.get("target_is_net", True))
    retirement_age_val = pending_payload.get("retirement_age")
    retirement_age_int = None
    if retirement_age_val is not None:
        try:
            retirement_age_int = int(retirement_age_val)
        except Exception:
            retirement_age_int = None

    if answer == "לא":
        try:
            clear_pending_pre_retirement_plan_resolution(db=db, client_id=request.client_id)
        except Exception:
            pass
        try:
            _store_ignore_blocked_balances_decision(
                db=db,
                client_id=request.client_id,
                ignore_blocked_balances=True,
                decision="no",
            )
        except Exception:
            pass
        return StreamingResponse(
            iter(
                [
                    "קיבלתי – לא נכלול יתרות חסומות.\n"
                    "כדי לבנות תכנית יעד (ללא ביצוע), בקש שוב: 'בנה תכנית יעד ...'.\n"
                    "כדי לבצע בפועל, בקש: 'בצע את התכנית'."
                ]
            ),
            media_type="text/plain; charset=utf-8",
        )

    try:
        clear_pending_pre_retirement_plan_resolution(db=db, client_id=request.client_id)
    except Exception:
        pass

    try:
        _store_ignore_blocked_balances_decision(
            db=db,
            client_id=request.client_id,
            ignore_blocked_balances=False,
            decision="yes",
        )
    except Exception:
        pass

    return StreamingResponse(
        iter(
            [
                "קיבלתי – נכלול יתרות חסומות לחישוב תיאורטי.\n"
                "כדי לבצע פעולה תפעולית (המרה לנכסים) נדרש אישור, והוא נוצר רק כשתבקש לבצע.\n"
                "כתוב: 'בצע את התכנית'."
            ]
        ),
        media_type="text/plain; charset=utf-8",
    )
