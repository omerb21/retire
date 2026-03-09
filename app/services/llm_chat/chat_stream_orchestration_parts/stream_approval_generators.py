import json
from datetime import datetime, timezone
from typing import Any

from app.guards.tool_intent_guard import is_conceptual_no_execute_request
from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
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
from app.services.llm_chat.chat_orchestration_helpers_parts.scenario_storage import (
    load_execution_veto,
    load_normalized_target_plan_context,
    store_normalized_target_plan_context,
)
from app.services.llm_chat.message_utils import (
    extract_latest_target_pension_plan_payload,
)
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
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    decide_stream_planning_execution_policy,
)
from app.services.llm_chat.pending_approvals import (
    load_pending_approval_ui_action_if_match,
    store_pending_approval_ui_action,
)
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)

from .stream_tool_execution import _execute_tool_call
from .stream_top_level_helpers import (
    _build_transform_accounts_from_target_plan_payload,
    _store_pending_approval_request,
)

_PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO = (
    "pending_pre_retirement_plan_resolution"
)


def _current_turn_text_from_request(request) -> str:
    try:
        for message in reversed(request.messages or []):
            role = getattr(message, "role", None)
            if role is None and isinstance(message, dict):
                role = message.get("role")
            if role != "user":
                continue
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            return str(content or "")
    except Exception:
        pass
    return str(getattr(request, "user_message", None) or "")


def _emit_planning_execution_gate_trace(
    *,
    stream_request_id: str,
    event_type: str,
    decision,
    tool_name: str | None,
) -> None:
    try:
        from app.services.agent_trace_logger import log_trace_event

        log_trace_event(
            trace_id=stream_request_id,
            event_type=event_type,
            payload={
                "planning_only": bool(decision.planning_only),
                "explicit_execution_intent": bool(decision.explicit_execution_intent),
                "explicit_execution_veto": bool(decision.explicit_execution_veto),
                "reason_code": str(decision.reason_code or ""),
                "tool_name": tool_name,
            },
        )
    except Exception:
        pass


def _planning_only_gate_reply(decision) -> str:
    if bool(decision.explicit_execution_veto):
        return sanitize_user_visible_text(
            "לא אבצע עזיבת עבודה ולא אבקש אישור לביצוע. נשארים במצב תכנון בלבד. "
            "כדי לעבור לביצוע בפועל כתוב במפורש 'בצע עזיבת עבודה'."
        )
    return sanitize_user_visible_text(
        "הפנייה הנוכחית נשארת במצב תכנון בלבד. לא אבצע עזיבת עבודה ולא אבקש אישור לביצוע. "
        "כדי לעבור לביצוע בפועל כתוב במפורש 'בצע עזיבת עבודה'."
    )


def _emit_termination_parser_trace(
    *,
    stream_request_id: str,
    event_type: str,
    decision,
    requested_execution: bool,
    mapping_is_unambiguous: bool,
    tool_name: str | None,
    tool_args: dict[str, Any] | None,
) -> None:
    try:
        from app.services.agent_trace_logger import log_trace_event

        payload_args = tool_args if isinstance(tool_args, dict) else {}
        log_trace_event(
            trace_id=stream_request_id,
            event_type=event_type,
            payload={
                "planning_only": bool(decision.planning_only),
                "explicit_execution_intent": bool(decision.explicit_execution_intent),
                "explicit_execution_veto": bool(decision.explicit_execution_veto),
                "reason_code": str(decision.reason_code or ""),
                "requested_execution": bool(requested_execution),
                "mapping_is_unambiguous": bool(mapping_is_unambiguous),
                "tool_name": tool_name,
                "has_exempt_choice": isinstance(payload_args.get("exempt_choice"), str),
                "has_taxable_choice": isinstance(
                    payload_args.get("taxable_choice"), str
                ),
            },
        )
    except Exception:
        pass


def _termination_missing_requested_execution_reply() -> str:
    return sanitize_user_visible_text(
        "לא אבצע עזיבת עבודה ולא אבקש אישור לביצוע בלי בקשת ביצוע מפורשת. "
        "כדי לעבור לביצוע בפועל כתוב במפורש 'בצע עזיבת עבודה'."
    )


def _termination_ambiguous_mapping_reply() -> str:
    return sanitize_user_visible_text(
        "לא אבצע עזיבת עבודה ולא אבקש אישור לביצוע כי ההנחיה אינה ממפה באופן חד-משמעי את בחירת הפטור והחייב. "
        "לא הוחלו ברירות מחדל לביצוע."
    )


def _termination_mapping_is_unambiguous(
    *, user_text: str | None, tool_args: dict[str, Any] | None
) -> bool:
    lowered = str(user_text or "").lower()
    args = dict(tool_args or {}) if isinstance(tool_args, dict) else {}
    exempt_choice = str(args.get("exempt_choice") or "").strip()
    taxable_choice = str(args.get("taxable_choice") or "").strip()
    has_all_scope = any(token in lowered for token in ("הכל", "כולם", "שניהם"))
    has_withdrawal = any(
        token in lowered
        for token in (
            "משיכה",
            "למשיכה",
            "חד פעמ",
            "חד-פעמ",
            "הוני",
            "הונית",
            "הון",
        )
    )
    has_no_exemption = any(
        token in lowered for token in ("ללא פטור", "בלי שימוש בפטור", "ללא שימוש בפטור")
    )
    if has_all_scope and has_withdrawal:
        if not exempt_choice or not taxable_choice:
            return False
        if has_no_exemption:
            return False
    return True


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


def _emit_normalized_target_plan_fallback_loaded(
    *, stream_request_id: str, source: str
) -> None:
    try:
        from app.services.agent_trace_logger import log_trace_event

        log_trace_event(
            trace_id=stream_request_id,
            event_type="normalized_target_plan_context_fallback_loaded",
            payload={"source": source},
        )
    except Exception:
        pass


def _collect_raw_payload_keys(payload: object, prefix: str = "") -> list[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            current = f"{prefix}.{key}" if prefix else str(key)
            keys.add(current)
            keys.update(_collect_raw_payload_keys(value, current))
    elif isinstance(payload, list):
        for item in payload:
            current = f"{prefix}[]" if prefix else "[]"
            keys.update(_collect_raw_payload_keys(item, current))
    return sorted(keys)


def _build_normalized_context_from_payload(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None
    offsets = payload.get("offsets") if isinstance(payload.get("offsets"), dict) else {}
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    target_is_net = offsets.get("target_is_net")
    if target_is_net is None:
        target_is_net = args.get("target_is_net")
    if target_is_net is None:
        target_is_net = result.get("target_is_net")
    target_mode = "net" if bool(target_is_net) else "gross"
    requested_target = offsets.get("desired_net_total")
    if requested_target is None:
        requested_target = result.get("target_monthly_pension")
    if requested_target is None:
        requested_target = args.get("target_monthly_pension")
    effective_target = offsets.get("effective_plan_target")
    if effective_target is None:
        effective_target = result.get("target_monthly_pension")
    if effective_target is None:
        effective_target = args.get("target_monthly_pension")
    offset_used = offsets.get(
        "other_income_offset_net"
        if target_mode == "net"
        else "other_income_offset_gross"
    )
    if offset_used is None:
        offset_used = 0
    retirement_age = result.get("retirement_age")
    if retirement_age is None:
        retirement_age = args.get("retirement_age")
    if requested_target is None or effective_target is None:
        return None
    raw_payload_keys = _collect_raw_payload_keys(payload)
    if retirement_age is None and not raw_payload_keys:
        return None
    normalized = {
        "requested_target": float(requested_target or 0),
        "target_mode": target_mode,
        "offset_used": float(offset_used or 0),
        "effective_target": float(effective_target or 0),
        "retirement_age": int(retirement_age) if retirement_age is not None else None,
        "raw_payload_keys": raw_payload_keys,
    }
    if result.get("accumulated_pension") is not None:
        try:
            normalized["accumulated_pension"] = float(
                result.get("accumulated_pension") or 0
            )
        except Exception:
            pass
    return normalized


def _load_payload_without_message_fallback(
    *, db, client_id: int | None
) -> tuple[dict | None, str | None]:
    if client_id is None:
        return None, None
    try:
        payload = load_latest_target_pension_plan_data(db=db, client_id=client_id)
        if isinstance(payload, dict):
            return payload, "latest_target_pension_plan_data"
    except Exception:
        pass
    try:
        payload = load_latest_target_pension_plan(db=db, client_id=client_id)
        if isinstance(payload, dict):
            return payload, "latest_target_pension_plan"
    except Exception:
        pass
    return None, None


def _load_transient_target_plan_payload_from_messages(
    *, messages: object
) -> tuple[dict | None, str | None]:
    try:
        payload = extract_latest_target_pension_plan_payload(messages or [])
    except Exception:
        payload = None
    if isinstance(payload, dict):
        return payload, "transient_message_payload"
    return None, None


def _load_target_plan_payload_for_execution(
    *,
    db,
    client_id: int | None,
    stream_request_id: str,
    messages: object = None,
) -> tuple[dict | None, dict | None]:
    normalized_context = None
    if client_id is not None:
        try:
            normalized_context = load_normalized_target_plan_context(
                db=db,
                client_id=int(client_id),
                trace_id=stream_request_id,
            )
        except Exception:
            normalized_context = None
    payload, source = _load_payload_without_message_fallback(db=db, client_id=client_id)
    transient_payload, transient_source = (
        _load_transient_target_plan_payload_from_messages(messages=messages)
    )
    if not isinstance(payload, dict):
        payload = transient_payload
        source = transient_source
    if normalized_context is not None:
        return normalized_context, payload
    if not isinstance(payload, dict) or source is None:
        return None, None
    _emit_normalized_target_plan_fallback_loaded(
        stream_request_id=stream_request_id,
        source=source,
    )
    fallback_context = _build_normalized_context_from_payload(payload)
    if fallback_context is not None and client_id is not None:
        try:
            store_normalized_target_plan_context(
                db=db,
                client_id=int(client_id),
                requested_target=float(fallback_context.get("requested_target") or 0),
                target_mode=str(fallback_context.get("target_mode") or ""),
                offset_used=float(fallback_context.get("offset_used") or 0),
                effective_target=float(fallback_context.get("effective_target") or 0),
                retirement_age=fallback_context.get("retirement_age"),
                accumulated_pension=fallback_context.get("accumulated_pension"),
                raw_payload_keys=fallback_context.get("raw_payload_keys"),
                trace_id=stream_request_id,
            )
        except Exception:
            pass
    return fallback_context, payload


def _termination_execution_veto_is_active(
    *, db, client_id: int | None, trace_id: str
) -> bool:
    if client_id is None:
        return False
    try:
        veto = load_execution_veto(db=db, client_id=int(client_id), trace_id=trace_id)
    except Exception:
        veto = None
    return (
        isinstance(veto, dict)
        and veto.get("veto_active") is True
        and str(veto.get("scope") or "").strip() == "termination_execution"
    )


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

    current_turn_text = _current_turn_text_from_request(request)
    execution_gate = decide_stream_planning_execution_policy(current_turn_text)
    termination_veto_active = _termination_execution_veto_is_active(
        db=db,
        client_id=request.client_id,
        trace_id=stream_request_id,
    )

    if explicit_termination and (not termination_already_executed):
        if (
            execution_gate.planning_only
            or execution_gate.explicit_execution_veto
            or termination_veto_active
        ):
            _emit_termination_parser_trace(
                stream_request_id=stream_request_id,
                event_type="termination_parser_planning_blocked",
                decision=execution_gate,
                requested_execution=bool(execution_gate.explicit_execution_intent),
                mapping_is_unambiguous=True,
                tool_name="PROCESS_TERMINATION",
                tool_args=None,
            )
            yield _planning_only_gate_reply(execution_gate)
            return
        if not execution_gate.explicit_execution_intent:
            _emit_termination_parser_trace(
                stream_request_id=stream_request_id,
                event_type="termination_parser_missing_requested_execution_blocked",
                decision=execution_gate,
                requested_execution=False,
                mapping_is_unambiguous=True,
                tool_name="PROCESS_TERMINATION",
                tool_args=None,
            )
            yield _termination_missing_requested_execution_reply()
            return
        if is_conceptual_no_execute_request(
            getattr(request, "user_message", None) or ""
        ):
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
        tool_args: dict[str, Any] = {
            "confirmed": True,
            "requested_execution": True,
        }
        tool_args.update(extract_process_termination_choice_overrides(recent_user_text))
        termination_date_override = extract_process_termination_date_override(
            recent_user_text
        )
        if termination_date_override:
            tool_args["termination_date"] = termination_date_override
        if not _termination_mapping_is_unambiguous(
            user_text=recent_user_text,
            tool_args=tool_args,
        ):
            _emit_termination_parser_trace(
                stream_request_id=stream_request_id,
                event_type="termination_parser_ambiguous_mapping_blocked",
                decision=execution_gate,
                requested_execution=True,
                mapping_is_unambiguous=False,
                tool_name="PROCESS_TERMINATION",
                tool_args=tool_args,
            )
            yield _termination_ambiguous_mapping_reply()
            return

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
                db.query(PensionFund)
                .filter(PensionFund.client_id == request.client_id)
                .count()
                > 0
            ) or bool(
                db.query(CapitalAsset)
                .filter(CapitalAsset.client_id == request.client_id)
                .count()
                > 0
            )
        except Exception:
            has_db_state_sources = False

        blocked_decision = None
        if (not has_db_state_sources) and callable(_load_blocked_balances_decision):
            try:
                blocked_decision = _load_blocked_balances_decision(
                    db=db, client_id=request.client_id
                )
            except Exception:
                blocked_decision = None

        try:
            pending_blocked = (
                db.query(Scenario)
                .filter(Scenario.client_id == request.client_id)
                .filter(
                    Scenario.scenario_name
                    == _PENDING_PRE_RETIREMENT_PLAN_RESOLUTION_SCENARIO
                )
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

        _normalized_target_context, payload = _load_target_plan_payload_for_execution(
            db=db,
            client_id=request.client_id,
            stream_request_id=stream_request_id,
            messages=request.messages,
        )

        def _extract_execution_plan_accounts(p: object) -> tuple[dict | None, list]:
            if not isinstance(p, dict):
                return None, []
            res = p.get("result") if isinstance(p.get("result"), dict) else {}
            exec_plan = (
                res.get("execution_plan")
                if isinstance(res.get("execution_plan"), dict)
                else None
            )
            if not isinstance(exec_plan, dict):
                return None, []
            raw = exec_plan.get("accounts")
            accounts = raw if isinstance(raw, list) else []
            return exec_plan, accounts

        execution_plan, accounts_for_execution = _extract_execution_plan_accounts(
            payload
        )
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
                "כתוב: יעד נטו: <מספר>."
            )
            return

        result = (
            payload.get("result") if isinstance(payload.get("result"), dict) else {}
        )

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
            accounts = (
                accounts_for_execution
                or _build_transform_accounts_from_target_plan_payload(payload)
            )
            if not accounts:
                non_exec_reason = None
                try:
                    res_obj = (
                        payload.get("result")
                        if isinstance(payload.get("result"), dict)
                        else {}
                    )
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
            if _should_apply_restore_transform_cooldown(
                db=db, client_id=request.client_id
            ):
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
            format_tool_output_for_user_stream(
                "CALCULATE_FIXATION_OF_RIGHTS", tool_result
            )
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

    _normalized_target_context, payload = _load_target_plan_payload_for_execution(
        db=db,
        client_id=request.client_id,
        stream_request_id=stream_request_id,
        messages=request.messages,
    )

    def _extract_execution_plan_accounts(p: object) -> tuple[dict | None, list]:
        if not isinstance(p, dict):
            return None, []
        res = p.get("result") if isinstance(p.get("result"), dict) else {}
        exec_plan = (
            res.get("execution_plan")
            if isinstance(res.get("execution_plan"), dict)
            else None
        )
        if not isinstance(exec_plan, dict):
            return None, []
        raw = exec_plan.get("accounts")
        accounts = raw if isinstance(raw, list) else []
        return exec_plan, accounts

    execution_plan, accounts_for_execution = _extract_execution_plan_accounts(payload)
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
            "כתוב: יעד נטו: <מספר>."
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
        accounts = (
            accounts_for_execution
            or _build_transform_accounts_from_target_plan_payload(payload)
        )
        if not accounts:
            non_exec_reason = None
            try:
                res_obj = (
                    payload.get("result")
                    if isinstance(payload.get("result"), dict)
                    else {}
                )
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

    current_turn_text = _current_turn_text_from_request(request)
    execution_gate = decide_stream_planning_execution_policy(current_turn_text)
    termination_veto_active = _termination_execution_veto_is_active(
        db=db,
        client_id=request.client_id,
        trace_id=stream_request_id,
    )
    if approved_tool_name == "PROCESS_TERMINATION" and (
        execution_gate.planning_only
        or execution_gate.explicit_execution_veto
        or termination_veto_active
    ):
        _emit_termination_parser_trace(
            stream_request_id=stream_request_id,
            event_type="termination_parser_planning_blocked",
            decision=execution_gate,
            requested_execution=bool(execution_gate.explicit_execution_intent),
            mapping_is_unambiguous=True,
            tool_name=str(approved_tool_name or ""),
            tool_args=(
                dict(approved_tool_args or {})
                if isinstance(approved_tool_args, dict)
                else None
            ),
        )
        yield _planning_only_gate_reply(execution_gate)
        return

    tool_args = (
        dict(approved_tool_args or {}) if isinstance(approved_tool_args, dict) else {}
    )
    if approved_tool_name == "PROCESS_TERMINATION":
        if tool_args.get("requested_execution") is not True:
            _emit_termination_parser_trace(
                stream_request_id=stream_request_id,
                event_type="termination_parser_missing_requested_execution_blocked",
                decision=execution_gate,
                requested_execution=False,
                mapping_is_unambiguous=_termination_mapping_is_unambiguous(
                    user_text=current_turn_text,
                    tool_args=tool_args,
                ),
                tool_name=str(approved_tool_name or ""),
                tool_args=tool_args,
            )
            yield _termination_missing_requested_execution_reply()
            return
        if not _termination_mapping_is_unambiguous(
            user_text=current_turn_text,
            tool_args=tool_args,
        ):
            _emit_termination_parser_trace(
                stream_request_id=stream_request_id,
                event_type="termination_parser_ambiguous_mapping_blocked",
                decision=execution_gate,
                requested_execution=True,
                mapping_is_unambiguous=False,
                tool_name=str(approved_tool_name or ""),
                tool_args=tool_args,
            )
            yield _termination_ambiguous_mapping_reply()
            return
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

        term_success = (
            isinstance(parsed_term, dict) and parsed_term.get("success") is True
        )

        if (
            term_success
            and isinstance(pending_build, dict)
            and (not termination_veto_active)
        ):
            plan_args = pending_build.get("plan_args")
            if (
                isinstance(plan_args, dict)
                and plan_args.get("target_monthly_pension") is not None
            ):
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
                    + format_tool_output_for_user_stream(
                        "BUILD_TARGET_PENSION_PLAN", plan_result
                    )
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
