import json
from datetime import datetime, timezone

from fastapi.responses import StreamingResponse

from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_pre_retirement_plan_resolution import (
    _store_ignore_blocked_balances_decision,
 )
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    build_default_termination_plan_preview,
    clear_current_employer_termination_plan_preview,
    get_current_employer_severance_amount_ssot,
    load_current_employer_termination_plan_preview,
    clear_pending_current_employer_severance_termination_question,
    clear_pending_build_target_plan_after_termination,
    load_pending_current_employer_severance_termination_question,
    store_current_employer_severance_execution_decision,
    store_current_employer_termination_plan_preview,
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

    pending_current_employer = None
    try:
        pending_current_employer = load_pending_current_employer_severance_termination_question(
            db=db,
            client_id=request.client_id,
        )
    except Exception:
        pending_current_employer = None

    if isinstance(pending_current_employer, dict) and isinstance(pending_current_employer.get("plan_args"), dict):
        plan_args = dict(pending_current_employer.get("plan_args") or {})
        plan_args["ignore_blocked_balances"] = True

        effective_portfolio = request.pension_portfolio
        try:
            loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
            if loaded is not None:
                effective_portfolio, _effective_snapshot_at = loaded
        except Exception:
            pass

        if answer == "לא":
            try:
                clear_pending_current_employer_severance_termination_question(
                    db=db,
                    client_id=request.client_id,
                )
            except Exception:
                pass
            try:
                store_current_employer_severance_execution_decision(
                    db=db,
                    client_id=request.client_id,
                    decision="no",
                )
            except Exception:
                pass

            plan_result = execute_tool_call(
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
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=plan_result,
                )
            except Exception:
                pass

            return StreamingResponse(
                iter(
                    [
                        sanitize_user_visible_text(
                            "קיבלתי – נמשיך בלי לבצע עזיבת עבודה, תוך התעלמות מפיצויי מעסיק נוכחי.\n\n"
                            "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                            + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                        )
                    ]
                ),
                media_type="text/plain",
            )

        try:
            clear_pending_current_employer_severance_termination_question(
                db=db,
                client_id=request.client_id,
            )
        except Exception:
            pass
        try:
            store_current_employer_severance_execution_decision(
                db=db,
                client_id=request.client_id,
                decision="yes",
            )
        except Exception:
            pass

        current_employer_amount = 0.0
        try:
            current_employer_amount = float(
                get_current_employer_severance_amount_ssot(db=db, client_id=int(request.client_id))
                or 0
            )
        except Exception:
            current_employer_amount = 0.0

        preview_text, args_template = build_default_termination_plan_preview(
            current_employer_amount=current_employer_amount,
            context={"plan_args": plan_args},
        )
        try:
            store_current_employer_termination_plan_preview(
                db=db,
                client_id=request.client_id,
                payload={
                    "plan_args": plan_args,
                    "termination_arguments_template": args_template,
                    "awaiting_user_confirmation": True,
                    "approved": False,
                    "declined": False,
                },
            )
        except Exception:
            pass

        return StreamingResponse(
            iter([preview_text]),
            media_type="text/plain",
        )

    preview_payload = None
    try:
        preview_payload = load_current_employer_termination_plan_preview(
            db=db,
            client_id=request.client_id,
        )
    except Exception:
        preview_payload = None

    if isinstance(preview_payload, dict) and bool(preview_payload.get("awaiting_user_confirmation")) is True:
        plan_args = preview_payload.get("plan_args")
        if not isinstance(plan_args, dict):
            plan_args = {}
        plan_args = dict(plan_args)
        plan_args["ignore_blocked_balances"] = True

        effective_portfolio = request.pension_portfolio
        try:
            loaded = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
            if loaded is not None:
                effective_portfolio, _effective_snapshot_at = loaded
        except Exception:
            pass

        if answer == "לא":
            try:
                store_current_employer_termination_plan_preview(
                    db=db,
                    client_id=request.client_id,
                    payload={
                        **preview_payload,
                        "awaiting_user_confirmation": False,
                        "approved": False,
                        "declined": True,
                        "declined_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                pass
            try:
                clear_pending_build_target_plan_after_termination(
                    db=db,
                    client_id=request.client_id,
                )
            except Exception:
                pass
            try:
                clear_pending_approval_request(db=db, client_id=request.client_id)
            except Exception:
                pass

            return StreamingResponse(
                iter(
                    [
                        "הבנתי – לא אבצע את תכנית ברירת המחדל לעזיבת עבודה.\n\n"
                        "כדי להמשיך, כתוב מה אתה רוצה לעשות עם הפיצויים:\n"
                        "- פטור: משיכה בפטור / משיכה ללא פטור (פריסה) / רצף קצבה\n"
                        "- חייב: רצף קצבה / משיכה (פריסה) / פיצול\n\n"
                        "לדוגמה: 'פטור למשיכה בפטור, חייב לפיצול 70% קצבה 30% מענק'."
                    ]
                ),
                media_type="text/plain",
            )

        try:
            store_current_employer_termination_plan_preview(
                db=db,
                client_id=request.client_id,
                payload={
                    **preview_payload,
                    "awaiting_user_confirmation": False,
                    "approved": True,
                    "declined": False,
                    "declined_at": None,
                },
            )
        except Exception:
            pass

        try:
            clear_pending_build_target_plan_after_termination(
                db=db,
                client_id=request.client_id,
            )
        except Exception:
            pass
        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

        termination_args = preview_payload.get("termination_arguments_template")
        if not isinstance(termination_args, dict):
            termination_args = {"confirmed": True}

        term_result = execute_tool_call(
            "PROCESS_TERMINATION",
            termination_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=stream_request_id,
        )

        parsed_term = None
        if isinstance(term_result, str) and term_result.strip():
            try:
                raw_json = term_result.split("###SEVERANCE_RESET###", 1)[0].strip()
                parsed_term = json.loads(raw_json)
            except Exception:
                parsed_term = None
        term_success = isinstance(parsed_term, dict) and parsed_term.get("success") is True

        if term_success:
            try:
                clear_current_employer_termination_plan_preview(
                    db=db,
                    client_id=request.client_id,
                )
            except Exception:
                pass

        term_text = sanitize_user_visible_text(
            "🔧 **פלט כלי (עזיבת עבודה):**\n" + format_tool_output_for_user_stream("PROCESS_TERMINATION", term_result)
        )

        if not term_success:
            return StreamingResponse(
                iter([term_text]),
                media_type="text/plain",
            )

        if plan_args.get("target_monthly_pension") is None:
            return StreamingResponse(
                iter([term_text]),
                media_type="text/plain",
            )

        refreshed_portfolio = effective_portfolio
        try:
            db.expire_all()
        except Exception:
            pass
        try:
            loaded_after_term = load_latest_pension_portfolio_snapshot_models(db, request.client_id)
            if loaded_after_term is not None:
                refreshed_portfolio, _snapshot_at_after = loaded_after_term
        except Exception:
            refreshed_portfolio = effective_portfolio

        plan_result = execute_tool_call(
            "BUILD_TARGET_PENSION_PLAN",
            plan_args,
            request.client_id,
            db,
            pension_portfolio=refreshed_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=stream_request_id,
        )
        try:
            store_latest_target_pension_plan_data(
                db=db,
                client_id=request.client_id,
                tool_result=plan_result,
            )
        except Exception:
            pass
        try:
            store_latest_target_pension_plan(
                db=db,
                client_id=request.client_id,
                tool_result=plan_result,
            )
        except Exception:
            pass

        plan_text = sanitize_user_visible_text(
            "🔧 **פלט כלי (בניית תכנית קצבה):**\n" + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
        )
        return StreamingResponse(
            iter([term_text + "\n\n" + plan_text]),
            media_type="text/plain",
        )

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
            media_type="text/plain",
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
        media_type="text/plain",
    )
