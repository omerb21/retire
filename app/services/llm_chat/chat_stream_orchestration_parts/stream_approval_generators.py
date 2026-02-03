import json
from datetime import datetime, timezone
from typing import Any

from app.models.scenario import Scenario
from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    build_forced_document_reply,
    build_pension_portfolio_update_after_transform,
    clear_pending_approval_request,
    format_transform_result_for_user,
    load_latest_target_pension_plan,
    load_latest_target_pension_plan_data,
    store_pending_plan_target_marker,
)
from app.services.llm_chat.message_utils import extract_latest_target_pension_plan_payload
from app.services.llm_chat.orchestration_utils import (
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
)
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    clear_pending_build_target_plan_after_termination,
    load_pending_build_target_plan_after_termination,
)
from app.guards.tool_intent_guard import is_conceptual_no_execute_request

from app.services.llm_chat.pending_approvals import (
    load_pending_approval_ui_action_if_match,
    store_pending_approval_ui_action,
)

from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot_models

from .stream_top_level_helpers import (
    _build_transform_accounts_from_target_plan_payload,
    _store_pending_approval_request,
)
from .stream_tool_execution import _execute_tool_call

_PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO = "pending_pre_retirement_plan_resolution"


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
        return False

    def _get_account_number(acc: dict) -> str:
        return str(
            acc.get("account_number")
            or acc.get("מספר_חשבון")
            or acc.get("מספר חשבון")
            or acc.get("מספר-חשבון")
            or ""
        ).strip()

    for acc in accounts:
        if not isinstance(acc, dict):
            continue

        account_number = _get_account_number(acc)
        if not account_number:
            continue

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


def _parse_iso_datetime_utc(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    cleaned = raw.strip()
    try:
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _should_apply_restore_transform_cooldown(*, db, client_id: int) -> bool:
    latest = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    if latest is None:
        return False
    try:
        params = json.loads(latest.parameters) if latest.parameters else {}
    except Exception:
        params = {}
    if not isinstance(params, dict):
        return False
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return False
    if str(meta.get("operation_type") or "").strip() != "restore_snapshot":
        return False
    restored_at = _parse_iso_datetime_utc(meta.get("restored_at_utc"))
    if restored_at is None:
        return False
    try:
        age_sec = (datetime.now(timezone.utc) - restored_at).total_seconds()
    except Exception:
        return False
    return 0 <= age_sec <= 30


def generate_forced_approval(
    *,
    computed_data,
    explicit_termination,
    termination_already_executed,
    request,
    db,
    effective_portfolio,
    force_max_exemption,
    stream_request_id,
    wants_execute_target_plan,
    wants_fixation_execute,
) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    # If the user explicitly asked to execute termination and it wasn't done yet,
    # we must request approval BEFORE running.
    if explicit_termination and (not termination_already_executed):
        if is_conceptual_no_execute_request(getattr(request, "user_message", None) or ""):
            yield (
                "כותרת: עזיבת עבודה – הסבר עקרוני (ללא ביצוע)\n\n"
                "כדי לבצע עזיבת עבודה במערכת צריך אישור מפורש. כרגע ביקשת בלי לבצע, לכן אני מסביר עקרונית בלבד:\n"
                "- מה מסמנים כ'סיום עבודה' ומה זה משנה לתיק\n"
                "- איך מטפלים בפיצויים: רצף קצבה / משיכה / שילוב\n"
                "- אילו נתונים נדרשים כדי לבצע בפועל (תאריך, סכומים, בחירות)\n"
            )
            return

        recent_user_text = "\n".join(
            [
                str(getattr(m, "content", ""))
                for m in (request.messages or [])
                if getattr(m, "role", None) == "user"
            ][-8:]
        )
        tool_args: dict[str, Any] = {"confirmed": True}
        tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
        termination_date_override = extract_process_termination_date_override(recent_user_text)
        if termination_date_override:
            tool_args["termination_date"] = termination_date_override

        try:
            _store_pending_approval_request(
                db=db,
                client_id=request.client_id,
                tool_name="PROCESS_TERMINATION",
                tool_args=tool_args,
            )
        except Exception:
            pass

        yield build_approval_request_ui_action(
            tool_name="PROCESS_TERMINATION",
            tool_args=tool_args,
            reason="נדרש אישור לפני ביצוע עזיבת עבודה במערכת.",
            risk_level="high",
            rag_sources=None,
        )
        return

    if wants_execute_target_plan:
        # Blocked balances gating: ask yes/no BEFORE creating approval, and persist decision.
        try:
            from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_pre_retirement_plan_resolution import (
                _detect_blocked_balances_in_snapshot,
                _load_blocked_balances_decision,
                _store_pending_pre_retirement_plan_resolution,
            )
        except Exception:
            _detect_blocked_balances_in_snapshot = None
            _load_blocked_balances_decision = None
            _store_pending_pre_retirement_plan_resolution = None

        has_db_state_sources = False
        try:
            has_db_state_sources = bool(
                db.query(PensionFund).filter(PensionFund.client_id == request.client_id).count() > 0
            ) or bool(
                db.query(CapitalAsset).filter(CapitalAsset.client_id == request.client_id).count() > 0
            )
        except Exception:
            has_db_state_sources = False

        blocked_decision = None
        if (not has_db_state_sources) and callable(_load_blocked_balances_decision):
            try:
                blocked_decision = _load_blocked_balances_decision(db=db, client_id=request.client_id)
            except Exception:
                blocked_decision = None

        try:
            pending_blocked = (
                db.query(Scenario)
                .filter(Scenario.client_id == request.client_id)
                .filter(Scenario.scenario_name == _PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO)
                .order_by(Scenario.created_at.desc())
                .first()
            )
        except Exception:
            pending_blocked = None

        # Blocked balances are handled by policy before BUILD_TARGET_PENSION_PLAN.
        # Execute-target-plan should not gate on blocked balances.

        try:
            pending_ui = load_pending_approval_ui_action_if_match(
                db=db,
                client_id=request.client_id,
                request_kind="execute_target_plan",
                tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            )
        except Exception:
            pending_ui = None
        if isinstance(pending_ui, str) and pending_ui.strip():
            yield pending_ui
            return

        payload_plan = load_latest_target_pension_plan(db=db, client_id=request.client_id)
        payload_data = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)

        def _extract_execution_plan_accounts(p: object) -> tuple[dict | None, list]:
            if not isinstance(p, dict):
                return None, []
            res = p.get("result") if isinstance(p.get("result"), dict) else {}
            exec_plan = res.get("execution_plan") if isinstance(res.get("execution_plan"), dict) else None
            if not isinstance(exec_plan, dict):
                return None, []
            raw = exec_plan.get("accounts")
            accounts = raw if isinstance(raw, list) else []
            return exec_plan, accounts

        plan_exec, plan_accounts = _extract_execution_plan_accounts(payload_plan)
        data_exec, data_accounts = _extract_execution_plan_accounts(payload_data)

        payload: dict | None = None
        execution_plan: dict | None = None
        accounts_for_execution: list = []

        if plan_accounts:
            payload = payload_plan if isinstance(payload_plan, dict) else None
            execution_plan = plan_exec
            accounts_for_execution = plan_accounts
        elif data_accounts:
            payload = payload_data if isinstance(payload_data, dict) else None
            execution_plan = data_exec
            accounts_for_execution = data_accounts
        else:
            # Plan exists but doesn't include execution_plan.accounts. Keep payload so we can derive accounts.
            if isinstance(payload_plan, dict):
                payload = payload_plan
            elif isinstance(payload_data, dict):
                payload = payload_data

        if not isinstance(payload, dict):
            msg_payload = extract_latest_target_pension_plan_payload(request.messages)
            if isinstance(msg_payload, dict):
                try:
                    store_latest_target_pension_plan(
                        db=db,
                        client_id=request.client_id,
                        tool_result=msg_payload,
                    )
                except Exception:
                    pass
                try:
                    store_latest_target_pension_plan_data(
                        db=db,
                        client_id=request.client_id,
                        tool_result=msg_payload,
                    )
                except Exception:
                    pass
                payload_plan = load_latest_target_pension_plan(db=db, client_id=request.client_id)
                payload_data = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)
                plan_exec, plan_accounts = _extract_execution_plan_accounts(payload_plan)
                data_exec, data_accounts = _extract_execution_plan_accounts(payload_data)
                if plan_accounts:
                    payload = payload_plan if isinstance(payload_plan, dict) else None
                    execution_plan = plan_exec
                    accounts_for_execution = plan_accounts
                elif data_accounts:
                    payload = payload_data if isinstance(payload_data, dict) else None
                    execution_plan = data_exec
                    accounts_for_execution = data_accounts
                else:
                    derived = _build_transform_accounts_from_target_plan_payload(msg_payload)
                    if derived:
                        payload = msg_payload
                        execution_plan = None
                        accounts_for_execution = derived

        if not isinstance(payload, dict):
            try:
                store_pending_plan_target_marker(
                    db=db,
                    client_id=request.client_id,
                    ttl_seconds=300,
                    source="execute_target_plan_prompt",
                )
            except Exception:
                pass
            yield (
                "כדי לבצע תכנית בפועל צריך קודם לבנות תכנית יעד עם מספר.\n"
                "כתוב: יעד נטו: <מספר>.\n"
                "לדוגמה: יעד נטו: 28000"
            )
            return

        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}

        transform_args: dict[str, Any] = {
            "use_provided_accounts_only": True,
            "ignore_blocked_balances": True,
            "skip_non_convertible_accounts": True,
        }

        if blocked_decision is not None:
            transform_args["ignore_blocked_balances"] = bool(blocked_decision)

        if execution_plan is not None:
            transform_args["execution_plan"] = execution_plan
            transform_args["accounts"] = accounts_for_execution
        else:
            accounts = accounts_for_execution or _build_transform_accounts_from_target_plan_payload(payload)
            if not accounts:
                non_exec_reason = None
                try:
                    res_obj = payload.get("result") if isinstance(payload.get("result"), dict) else {}
                    exec_obj = res_obj.get("execution_plan") if isinstance(res_obj.get("execution_plan"), dict) else {}
                    raw_reason = exec_obj.get("non_executable_reason")
                    if isinstance(raw_reason, str) and raw_reason.strip():
                        non_exec_reason = raw_reason.strip()
                except Exception:
                    non_exec_reason = None
                yield (
                    "\n\n" + non_exec_reason
                    if non_exec_reason
                    else "\n\nתכנית היעד האחרונה אינה ניתנת לביצוע כרגע. יש לבנות תכנית יעד מחדש או להשלים נתונים חסרים."
                )
                return
            transform_args["accounts"] = accounts

        if _accounts_are_thin(transform_args.get("accounts")):
            transform_args["use_provided_accounts_only"] = False

        reason = "נדרש אישור לפני ביצוע המרות לפי תכנית היעד במערכת."
        try:
            if _should_apply_restore_transform_cooldown(db=db, client_id=request.client_id):
                reason = "בוצע שחזור סנאפסוט ממש עכשיו. כדי למנוע כפל המרות, ודא שזו הפעולה הנכונה ואז אשר."
        except Exception:
            pass

        ui_action = build_approval_request_ui_action(
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=transform_args,
            reason=reason,
            risk_level="high",
            rag_sources=None,
        )

        try:
            store_pending_approval_ui_action(
                db=db,
                client_id=request.client_id,
                request_kind="execute_target_plan",
                tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                tool_args=transform_args,
                ui_action=ui_action,
            )
        except Exception:
            try:
                _store_pending_approval_request(
                    db=db,
                    client_id=request.client_id,
                    tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                    tool_args=transform_args,
                )
            except Exception:
                pass

        yield ui_action
        return

    if wants_fixation_execute:
        tool_args = {"save_result": True}

        tool_result = _execute_tool_call(
            "CALCULATE_FIXATION_OF_RIGHTS",
            tool_args,
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            user_approved=True,
            request_id=stream_request_id,
        )

        try:
            clear_pending_approval_request(db=db, client_id=request.client_id)
        except Exception:
            pass

        out = sanitize_user_visible_text(
            format_tool_output_for_user_stream("CALCULATE_FIXATION_OF_RIGHTS", tool_result)
        )
        yield out


def generate_execute_target_after_termination(
    *,
    computed_data,
    request,
    db,
    effective_portfolio,
    force_max_exemption,
    stream_request_id,
) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    payload_plan = load_latest_target_pension_plan(db=db, client_id=request.client_id)
    payload_data = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)

    def _extract_execution_plan_accounts(p: object) -> tuple[dict | None, list]:
        if not isinstance(p, dict):
            return None, []
        res = p.get("result") if isinstance(p.get("result"), dict) else {}
        exec_plan = res.get("execution_plan") if isinstance(res.get("execution_plan"), dict) else None
        if not isinstance(exec_plan, dict):
            return None, []
        raw = exec_plan.get("accounts")
        accounts = raw if isinstance(raw, list) else []
        return exec_plan, accounts

    plan_exec, plan_accounts = _extract_execution_plan_accounts(payload_plan)
    data_exec, data_accounts = _extract_execution_plan_accounts(payload_data)

    payload: dict | None = None
    execution_plan: dict | None = None
    accounts_for_execution: list = []

    if plan_accounts:
        payload = payload_plan if isinstance(payload_plan, dict) else None
        execution_plan = plan_exec
        accounts_for_execution = plan_accounts
    elif data_accounts:
        payload = payload_data if isinstance(payload_data, dict) else None
        execution_plan = data_exec
        accounts_for_execution = data_accounts
    else:
        # Plan exists but doesn't include execution_plan.accounts. Keep payload so we can derive accounts.
        if isinstance(payload_plan, dict):
            payload = payload_plan
        elif isinstance(payload_data, dict):
            payload = payload_data

    if not isinstance(payload, dict):
        msg_payload = extract_latest_target_pension_plan_payload(request.messages)
        if isinstance(msg_payload, dict):
            try:
                store_latest_target_pension_plan(
                    db=db,
                    client_id=request.client_id,
                    tool_result=msg_payload,
                )
            except Exception:
                pass
            try:
                store_latest_target_pension_plan_data(
                    db=db,
                    client_id=request.client_id,
                    tool_result=msg_payload,
                )
            except Exception:
                pass
            payload_plan = load_latest_target_pension_plan(db=db, client_id=request.client_id)
            payload_data = load_latest_target_pension_plan_data(db=db, client_id=request.client_id)
            plan_exec, plan_accounts = _extract_execution_plan_accounts(payload_plan)
            data_exec, data_accounts = _extract_execution_plan_accounts(payload_data)
            if plan_accounts:
                payload = payload_plan if isinstance(payload_plan, dict) else None
                execution_plan = plan_exec
                accounts_for_execution = plan_accounts
            elif data_accounts:
                payload = payload_data if isinstance(payload_data, dict) else None
                execution_plan = data_exec
                accounts_for_execution = data_accounts
            else:
                derived = _build_transform_accounts_from_target_plan_payload(msg_payload)
                if derived:
                    payload = msg_payload
                    execution_plan = None
                    accounts_for_execution = derived

    if not isinstance(payload, dict):
        try:
            store_pending_plan_target_marker(
                db=db,
                client_id=request.client_id,
                ttl_seconds=300,
                source="execute_target_plan_prompt",
            )
        except Exception:
            pass
        yield (
            "כדי לבצע תכנית בפועל צריך קודם לבנות תכנית יעד עם מספר.\n"
            "כתוב: יעד נטו: <מספר>.\n"
            "לדוגמה: יעד נטו: 28000"
        )
        return

    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}

    transform_args = {
        "use_provided_accounts_only": True,
        "ignore_blocked_balances": True,
        "skip_non_convertible_accounts": True,
    }
    if execution_plan is not None:
        transform_args["execution_plan"] = execution_plan
        transform_args["accounts"] = accounts_for_execution
    else:
        accounts = accounts_for_execution or _build_transform_accounts_from_target_plan_payload(payload)
        if not accounts:
            non_exec_reason = None
            try:
                res_obj = payload.get("result") if isinstance(payload.get("result"), dict) else {}
                exec_obj = (
                    res_obj.get("execution_plan")
                    if isinstance(res_obj.get("execution_plan"), dict)
                    else {}
                )
                raw_reason = exec_obj.get("non_executable_reason")
                if isinstance(raw_reason, str) and raw_reason.strip():
                    non_exec_reason = raw_reason.strip()
            except Exception:
                non_exec_reason = None
            msg = (
                non_exec_reason
                if non_exec_reason
                else "תכנית היעד האחרונה אינה ניתנת לביצוע כרגע. יש לבנות תכנית יעד מחדש או להשלים נתונים חסרים."
            )
            yield f"עזיבת עבודה כבר בוצעה. {msg}"
            return
        transform_args["accounts"] = accounts

    if _accounts_are_thin(transform_args.get("accounts")):
        transform_args["use_provided_accounts_only"] = False
    transform_result = _execute_tool_call(
        "TRANSFORM_FUNDS_TO_ASSETS",
        transform_args,
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        user_approved=True,
        request_id=stream_request_id,
    )

    try:
        clear_pending_approval_request(db=db, client_id=request.client_id)
    except Exception:
        pass

    portfolio_update_marker = build_pension_portfolio_update_after_transform(
        tool_name="TRANSFORM_FUNDS_TO_ASSETS",
        tool_result=transform_result,
        tool_args=transform_args,
        current_pension_portfolio=effective_portfolio,
    )
    if portfolio_update_marker:
        yield portfolio_update_marker
    yield sanitize_user_visible_text(
        format_tool_output_for_user_stream(
            "TRANSFORM_FUNDS_TO_ASSETS",
            transform_result,
        )
    )


def generate_approval_exec(
    *,
    computed_data,
    approved_tool_name,
    approved_tool_args,
    request,
    db,
    effective_portfolio,
    force_max_exemption,
    stream_request_id,
    is_portfolio_analysis,
) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    tool_args = dict(approved_tool_args or {}) if isinstance(approved_tool_args, dict) else {}
    tool_result = _execute_tool_call(
        approved_tool_name,
        tool_args,
        request.client_id,
        db,
        pension_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        user_approved=True,
        request_id=stream_request_id,
    )

    if approved_tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
        should_retry = False
        try:
            parsed = json.loads(tool_result)
        except Exception:
            parsed = None

        if isinstance(parsed, dict) and parsed.get("success") is True:
            try:
                total_converted = int(parsed.get("total_converted") or 0)
            except Exception:
                total_converted = 0
            try:
                skipped_zero_balance = int(parsed.get("skipped_zero_balance") or 0)
            except Exception:
                skipped_zero_balance = 0

            if (
                total_converted == 0
                and skipped_zero_balance > 0
                and bool(tool_args.get("use_provided_accounts_only")) is True
            ):
                should_retry = True

        if should_retry:
            retry_args = dict(tool_args)
            retry_args["use_provided_accounts_only"] = False
            yield "לא נטענו נתוני חשבון מלאים, מנסה לטעון מה־DB."
            tool_args = retry_args
            tool_result = _execute_tool_call(
                approved_tool_name,
                tool_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                user_approved=True,
                request_id=stream_request_id,
            )

    try:
        clear_pending_approval_request(db=db, client_id=request.client_id)
    except Exception:
        pass

    portfolio_update_marker = build_pension_portfolio_update_after_transform(
        tool_name=approved_tool_name,
        tool_result=tool_result,
        tool_args=tool_args,
        current_pension_portfolio=effective_portfolio,
    )
    if portfolio_update_marker:
        yield portfolio_update_marker

    forced_document_reply = build_forced_document_reply(
        tool_name=approved_tool_name,
        tool_result=tool_result,
    )
    if forced_document_reply:
        yield "\n\n" + sanitize_user_visible_text(forced_document_reply)
        return

    if approved_tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
        yield format_transform_result_for_user(tool_result=tool_result)
        return

    if approved_tool_name == "PROCESS_TERMINATION" and request.client_id is not None:
        pending_build = None
        try:
            pending_build = load_pending_build_target_plan_after_termination(
                db=db,
                client_id=int(request.client_id),
            )
        except Exception:
            pending_build = None

        parsed_term = None
        if isinstance(tool_result, str) and tool_result.strip():
            try:
                raw_json = tool_result.split("###SEVERANCE_RESET###", 1)[0].strip()
                parsed_term = json.loads(raw_json)
            except Exception:
                parsed_term = None

        term_success = isinstance(parsed_term, dict) and parsed_term.get("success") is True

        if term_success and isinstance(pending_build, dict):
            plan_args = pending_build.get("plan_args")
            if isinstance(plan_args, dict) and plan_args.get("target_monthly_pension") is not None:
                try:
                    clear_pending_build_target_plan_after_termination(
                        db=db,
                        client_id=int(request.client_id),
                    )
                except Exception:
                    pass

                try:
                    db.expire_all()
                except Exception:
                    pass

                refreshed_portfolio = effective_portfolio
                try:
                    loaded_after_term = load_latest_pension_portfolio_snapshot_models(
                        db,
                        request.client_id,
                    )
                    if loaded_after_term is not None:
                        refreshed_portfolio, _snapshot_at_after_term = loaded_after_term
                except Exception:
                    refreshed_portfolio = effective_portfolio

                plan_args = dict(plan_args)
                plan_args["ignore_blocked_balances"] = True
                plan_result = _execute_tool_call(
                    "BUILD_TARGET_PENSION_PLAN",
                    plan_args,
                    request.client_id,
                    db,
                    pension_portfolio=refreshed_portfolio,
                    force_max_exemption=force_max_exemption,
                    user_approved=True,
                    request_id=stream_request_id,
                )
                try:
                    store_latest_target_pension_plan(
                        db=db,
                        client_id=request.client_id,
                        tool_result=plan_result,
                    )
                except Exception:
                    pass
                try:
                    store_latest_target_pension_plan_data(
                        db=db,
                        client_id=request.client_id,
                        tool_result=plan_result,
                    )
                except Exception:
                    pass

                yield "\n\n" + sanitize_user_visible_text(
                    "🔧 **פלט כלי (בניית תכנית קצבה):**\n"
                    + format_tool_output_for_user_stream("BUILD_TARGET_PENSION_PLAN", plan_result)
                )

    out = sanitize_user_visible_text(
        format_tool_output_for_user_stream(approved_tool_name, tool_result)
    )
    if is_portfolio_analysis and isinstance(out, str) and out.strip():
        if "הערכה" not in out and "הערכה גסה" not in out and "ראשונית" not in out:
            out = (
                "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                + out
            )
    yield out
