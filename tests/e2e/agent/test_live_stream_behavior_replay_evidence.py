import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

import app.services.agent_execution.execute_agent_request as exec_mod
import app.services.llm_chat.chat_orchestration_helpers_parts.scenario_storage as scenario_storage_mod
import app.services.llm_chat.chat_orchestration_parts.orchestrator_impl_parts.steps_parts.runner_step_handlers as runner_step_handlers
import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_approval_cancel_handling as approval_cancel_mod
import app.services.llm_chat.chat_stream_orchestration_parts.stream_approval_generators as stream_approval_mod
import app.services.llm_chat.chat_stream_orchestration_parts.stream_system_prompt_generators as stream_prompt_mod
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario

_JSONL_PATH = Path(__file__).with_name("golden_behavior_8.jsonl")
_OUTPUT_PATH = Path(__file__).with_name("live_stream_behavior_replay_evidence_output.json")
_SUBSET_IDS = (
    "BEHAVIOR_01_GREETING_NO_SUMMARY_REPORT",
    "BEHAVIOR_02_PORTFOLIO_ANALYSIS_SHORT_DEFAULT",
    "BEHAVIOR_03_TARGET_PLAN_NO_TERMINATION_FORCED",
    "BEHAVIOR_05_PLANNING_REQUEST_MUST_NOT_EXECUTE_TERMINATION",
    "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET",
    "BEHAVIOR_07_COMPARE_PLANS_INSTEAD_OF_NEW_PLAN",
    "BEHAVIOR_08_GENERAL_QUESTIONS_MUST_GIVE_USEFUL_ANSWER",
)

_BASELINE_USER_TURNS_BY_CASE_ID = {
    "BEHAVIOR_01_GREETING_NO_SUMMARY_REPORT": ["שלום"],
    "BEHAVIOR_02_PORTFOLIO_ANALYSIS_SHORT_DEFAULT": ["ניתוח תיק"],
    "BEHAVIOR_03_TARGET_PLAN_NO_TERMINATION_FORCED": [
        "תכנית פרישה",
        "יעד 30000 נטו",
    ],
    "BEHAVIOR_05_PLANNING_REQUEST_MUST_NOT_EXECUTE_TERMINATION": [
        "בנה תכנית קצבת יעד 30000 נטו לגיל 76"
    ],
    "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET": [
        "יעד 30000 נטו",
        "בנה תכנית קצבת יעד 30000 נטו לגיל 76",
    ],
    "BEHAVIOR_07_COMPARE_PLANS_INSTEAD_OF_NEW_PLAN": [
        "השווה תכנית פרישה גיל 72 לעומת גיל 76"
    ],
    "BEHAVIOR_08_GENERAL_QUESTIONS_MUST_GIVE_USEFUL_ANSWER": ["מה תמליץ לי?"],
}

_EXPLICIT_TOOL_TRACE_EVENT_TYPES = {"tool_call", "tool_result"}
_EXECUTION_TOOL_NAMES = {
    "PROCESS_TERMINATION",
    "TRANSFORM_FUNDS_TO_ASSETS",
    "CALCULATE_FIXATION_OF_RIGHTS",
    "RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
}

_TURN_REQUIRED_KEYS = {
    "turn_index",
    "user_text",
    "visible_reply_text",
    "reply_source_hint",
    "trace_event_types",
    "legacy_fallback_detected",
    "pending_approval_snapshot",
    "target_plan_snapshot",
    "execution_detected",
    "raw_http_status",
}


class _TraceCapture:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def fake_log_trace_event(
        self, *, trace_id=None, event_type: str, payload=None, **kwargs
    ) -> None:
        _ = kwargs
        self.events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )


def _install_trace_capture(monkeypatch) -> _TraceCapture:
    import app.services.agent_execution.execute_agent_request as entry_mod
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod
    import app.services.llm_chat.capability_router.router_facade as router_facade_mod
    import app.services.llm_chat.tool_execution as tool_execution_mod

    capture = _TraceCapture()
    monkeypatch.setattr(entry_mod, "log_trace_event", capture.fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", capture.fake_log_trace_event)
    monkeypatch.setattr(
        trace_logger_mod, "log_trace_event", capture.fake_log_trace_event
    )
    monkeypatch.setattr(
        router_facade_mod, "log_trace_event", capture.fake_log_trace_event
    )
    monkeypatch.setattr(
        tool_execution_mod, "_log_agent_trace", capture.fake_log_trace_event
    )
    return capture


def _load_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with _JSONL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            parsed = json.loads(raw)
            if str(parsed.get("id") or "") in _SUBSET_IDS:
                rows.append(_normalize_case(parsed))
    rows.sort(key=lambda row: _SUBSET_IDS.index(str(row["id"])))
    return rows


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(case)
    baseline_user_turns = _BASELINE_USER_TURNS_BY_CASE_ID.get(str(case.get("id") or ""))
    if baseline_user_turns is not None:
        normalized["conversation"] = [
            {"role": "user", "content": user_text} for user_text in baseline_user_turns
        ]
    return normalized


def _ensure_client(Session, *, client_id: int) -> None:
    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Replay Evidence User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.commit()


def _clear_client_state(Session, *, client_id: int) -> None:
    with Session() as db:
        db.query(Scenario).filter(Scenario.client_id == client_id).delete(
            synchronize_session=False
        )
        db.commit()


def _seed_executable_target_plan(Session, *, client_id: int) -> None:
    payload = {
        "tool_name": "BUILD_TARGET_PENSION_PLAN",
        "args": {"target_monthly_pension": 5000, "target_is_net": True},
        "result": {
            "target_monthly_pension": 5000,
            "target_is_net": True,
            "accumulated_pension": 5000,
            "estimated_monthly_net": 5000,
            "estimated_monthly_tax": 0,
            "remaining_capital": 100000,
            "execution_plan": {
                "accounts": [
                    {
                        "account_id": "C1",
                        "account_number": "C1",
                        "component": "תגמולים",
                        "amount_to_convert": 1000.0,
                    }
                ],
                "target_gross": 5000,
                "target_net": 5000,
                "expected_total_gross": 5000,
                "expected_total_net": 5000,
            },
        },
    }
    with Session() as db:
        for scenario_name in ("target_pension_plan", "target_pension_plan_data"):
            db.add(
                Scenario(
                    client_id=client_id,
                    scenario_name=scenario_name,
                    apply_tax_planning=False,
                    apply_capitalization=False,
                    apply_exemption_shield=False,
                    parameters=json.dumps(payload, ensure_ascii=False),
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.commit()


def _build_tool_call_reply(tool_name: str, arguments: dict[str, Any]) -> str:
    transparency = {
        "action": "live_stream_replay_evidence",
        "tool_name": tool_name,
        "tool_arguments_summary": json.dumps(arguments, ensure_ascii=False),
        "rag_sources": [],
    }
    risk = {
        "risk_level": "low",
        "approval_required": False,
        "conflict_with_rag": False,
        "risks": [],
        "affected_areas": [],
        "mitigations": [],
    }
    tool_call = {"name": tool_name, "arguments": arguments}
    return "\n".join(
        [
            f"###TRANSPARENCY_LOG### {json.dumps(transparency, ensure_ascii=False)}",
            f"###RISK_REVIEW### {json.dumps(risk, ensure_ascii=False)}",
            f"###TOOL_CALL### {json.dumps(tool_call, ensure_ascii=False)}",
        ]
    )


class _FakeLLMService:
    def __init__(self, case: dict[str, Any], recorder: list[dict[str, Any]], context: dict[str, Any]):
        self.case = case
        self.recorder = recorder
        self.context = context

    def _record(self, *, method: str, output: str) -> None:
        self.recorder.append(
            {
                "kind": "llm_reply",
                "case_id": self.context.get("case_id"),
                "turn_idx": self.context.get("turn_idx"),
                "method": method,
                "reply_preview": str(output or "")[:300],
            }
        )

    def _respond(self, messages) -> str:
        case_id = str(self.case["id"])
        user_messages = [
            str(getattr(msg, "content", "") or msg.get("content") or "")
            for msg in messages
            if (
                getattr(msg, "role", None) == "user"
                or (isinstance(msg, dict) and msg.get("role") == "user")
            )
        ]
        system_messages = [
            str(getattr(msg, "content", "") or msg.get("content") or "")
            for msg in messages
            if (
                getattr(msg, "role", None) == "system"
                or (isinstance(msg, dict) and msg.get("role") == "system")
            )
        ]
        user_count = len(user_messages)
        has_system_followup = any(
            ("🔧 **פלט כלי" in content) or ("אזהרה:" in content)
            for content in system_messages
        )

        if has_system_followup:
            if case_id == "BEHAVIOR_02_PORTFOLIO_ANALYSIS_SHORT_DEFAULT":
                return "פירוט לפי תכנית: כל החשבונות והיתרות זמינים כאן."
            if case_id == "BEHAVIOR_03_TARGET_PLAN_NO_TERMINATION_FORCED":
                return "בניתי תכנית, ואפשר גם לבצע עזיבת עבודה כבר עכשיו אם תרצה."
            if case_id == "BEHAVIOR_05_PLANNING_REQUEST_MUST_NOT_EXECUTE_TERMINATION":
                return "סטטוס: בוצע בהצלחה וגם עזיבת עבודה הושלמה."
            if case_id == "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET":
                return "יעד קצבה לתכנית (נטו, אחרי קיזוז הכנסות נוספות): 12,239."
            return "תשובה מקומית לאחר הרצת כלי."

        if case_id == "BEHAVIOR_01_GREETING_NO_SUMMARY_REPORT":
            return "שלום, אני יכול לעזור בנושאי פרישה."

        if case_id == "BEHAVIOR_02_PORTFOLIO_ANALYSIS_SHORT_DEFAULT":
            return _build_tool_call_reply("GET_PENSION_PRODUCTS", {})

        if case_id == "BEHAVIOR_03_TARGET_PLAN_NO_TERMINATION_FORCED":
            if user_count == 1:
                return "מה היעד החודשי שחשוב לך?"
            return _build_tool_call_reply(
                "BUILD_TARGET_PENSION_PLAN",
                {"target_monthly_pension": 30000, "target_is_net": True},
            )

        if case_id == "BEHAVIOR_05_PLANNING_REQUEST_MUST_NOT_EXECUTE_TERMINATION":
            return _build_tool_call_reply(
                "BUILD_TARGET_PENSION_PLAN",
                {
                    "target_monthly_pension": 30000,
                    "target_is_net": True,
                    "retirement_age": 76,
                },
            )

        if case_id == "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET":
            if user_count == 1:
                return "מה גיל הפרישה שתרצה לבדוק?"
            return _build_tool_call_reply(
                "BUILD_TARGET_PENSION_PLAN",
                {
                    "target_monthly_pension": 30000,
                    "target_is_net": True,
                    "retirement_age": 76,
                },
            )

        if case_id == "BEHAVIOR_07_COMPARE_PLANS_INSTEAD_OF_NEW_PLAN":
            return "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו. כתוב: יעד נטו."

        if case_id == "BEHAVIOR_08_GENERAL_QUESTIONS_MUST_GIVE_USEFUL_ANSWER":
            return "אני יכול להסביר את העיקרון בלבד, בלי מספרים ובלי המלצה."

        raise AssertionError(f"unsupported fake case_id={case_id}")

    def chat(self, messages, client_id=None):
        _ = client_id
        out = self._respond(messages)
        self._record(method="chat", output=out)
        return out

    def chat_stream(self, messages, client_id=None):
        _ = client_id
        out = self._respond(messages)
        self._record(method="chat_stream", output=out)
        yield out


def _extract_target_value(args: dict[str, Any]) -> float:
    try:
        return float(args.get("target_monthly_pension") or 0)
    except Exception:
        return 0.0


def _fake_compute_effective_plan_target(context: dict[str, Any], desired_total: float):
    case_id = str(context.get("case_id") or "")
    if case_id == "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET":
        return SimpleNamespace(
            desired_net_total=30000.0,
            other_income_offset_net=8880.0,
            other_income_offset_gross=8880.0,
            effective_plan_target=21120.0,
        )
    return SimpleNamespace(
        desired_net_total=float(desired_total or 0),
        other_income_offset_net=0.0,
        other_income_offset_gross=0.0,
        effective_plan_target=float(desired_total or 0),
    )


def _build_target_plan_tool_result(args: dict[str, Any], context: dict[str, Any]) -> str:
    desired_total = _extract_target_value(args)
    breakdown = _fake_compute_effective_plan_target(context, desired_total)
    payload = {
        "tool_name": "BUILD_TARGET_PENSION_PLAN",
        "args": dict(args),
        "result": {
            "target_monthly_pension": desired_total,
            "target_is_net": bool(args.get("target_is_net")),
            "retirement_age": args.get("retirement_age"),
            "target_achieved": True,
            "accumulated_pension": breakdown.effective_plan_target,
            "estimated_monthly_net": breakdown.effective_plan_target,
            "estimated_monthly_tax": 0,
            "remaining_capital": 500000,
            "plan_steps": [{"step_number": 1}],
            "sources_used": [
                {
                    "source_type": "pension_fund_from_portfolio",
                    "account_number": "A-001",
                    "component_field": "תגמולי_עובד_אחרי_2000",
                    "balance_used": 1000,
                    "pension_used": 10,
                }
            ],
            "execution_plan": {
                "accounts": [],
                "target_gross": breakdown.effective_plan_target,
                "target_net": breakdown.effective_plan_target,
                "expected_total_gross": breakdown.effective_plan_target,
                "expected_total_net": breakdown.effective_plan_target,
            },
        },
    }
    return (
        "OK\n\n###TARGET_PENSION_PLAN_DATA###\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n###END_TARGET_PENSION_PLAN_DATA###"
    )


def _load_pending_approval_snapshot(Session, *, client_id: int) -> dict[str, Any]:
    with Session() as db:
        loaded = scenario_storage_mod.load_pending_approval_request(
            db=db, client_id=client_id
        )
    if loaded is None:
        return {
            "has_pending_approval": False,
            "tool_name": None,
            "approval_request_id": None,
            "approval_type": None,
        }
    tool_name, tool_args = loaded
    approval_request_id = (
        tool_args.get("approval_id") if isinstance(tool_args.get("approval_id"), str) else None
    )
    approval_type = (
        tool_args.get("approval_type") if isinstance(tool_args.get("approval_type"), str) else None
    )
    return {
        "has_pending_approval": True,
        "tool_name": tool_name,
        "approval_request_id": approval_request_id,
        "approval_type": approval_type,
    }


def _collect_raw_payload_keys(payload: Any, prefix: str = "") -> list[str]:
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


def _extract_exact_storage_field(payload: Any, field_name: str) -> Any:
    if isinstance(payload, dict):
        if field_name in payload:
            return payload.get(field_name)
        for value in payload.values():
            found = _extract_exact_storage_field(value, field_name)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_exact_storage_field(item, field_name)
            if found is not None:
                return found
    return None


def _load_target_plan_snapshot(Session, *, client_id: int) -> dict[str, Any]:
    with Session() as db:
        target_plan_data_payload = scenario_storage_mod.load_latest_target_pension_plan_data(
            db=db, client_id=client_id
        )
        target_plan_payload = scenario_storage_mod.load_latest_target_pension_plan(
            db=db, client_id=client_id
        )

    payload = (
        target_plan_data_payload
        if isinstance(target_plan_data_payload, dict)
        else target_plan_payload
        if isinstance(target_plan_payload, dict)
        else None
    )

    if not isinstance(payload, dict):
        return {
            "requested_target_net": None,
            "requested_target_gross": None,
            "effective_target_after_offset": None,
            "additional_income_offset": None,
            "target_is_net": None,
            "target_monthly_pension": None,
            "retirement_age": None,
            "accumulated_pension": None,
            "raw_payload_keys": [],
        }

    return {
        "requested_target_net": _extract_exact_storage_field(
            payload, "requested_target_net"
        ),
        "requested_target_gross": _extract_exact_storage_field(
            payload, "requested_target_gross"
        ),
        "effective_target_after_offset": _extract_exact_storage_field(
            payload, "effective_target_after_offset"
        ),
        "additional_income_offset": _extract_exact_storage_field(
            payload, "additional_income_offset"
        ),
        "target_is_net": _extract_exact_storage_field(payload, "target_is_net"),
        "target_monthly_pension": _extract_exact_storage_field(
            payload, "target_monthly_pension"
        ),
        "retirement_age": _extract_exact_storage_field(payload, "retirement_age"),
        "accumulated_pension": _extract_exact_storage_field(
            payload, "accumulated_pension"
        ),
        "raw_payload_keys": _collect_raw_payload_keys(payload),
    }


def _producer_for_turn(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    producer_events = [event for event in events if event.get("kind") == "producer"]
    if producer_events:
        return producer_events[-1]
    llm_events = [event for event in events if event.get("kind") == "llm_reply"]
    if llm_events:
        return llm_events[-1]
    return None


def _build_reply_source_hint(
    *, producer: dict[str, Any] | None, visible_reply_text: str
) -> dict[str, Any] | None:
    if isinstance(producer, dict) and producer.get("kind") == "producer":
        return {
            "kind": "runtime_producer",
            "source": producer.get("source"),
        }
    if isinstance(producer, dict) and producer.get("kind") == "llm_reply":
        return {
            "kind": "runtime_llm",
            "method": producer.get("method"),
        }
    if visible_reply_text == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה.":
        return {
            "kind": "deterministic_match",
            "source": "stream_system_prompt_generators.generate_cashflow",
        }
    return None


def _detect_execution(
    *, turn_trace_events: list[dict[str, Any]], turn_events: list[dict[str, Any]]
) -> bool:
    for event in turn_trace_events:
        if str(event.get("event_type") or "") not in _EXPLICIT_TOOL_TRACE_EVENT_TYPES:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if str(payload.get("tool_name") or "") in _EXECUTION_TOOL_NAMES:
            return True
    if any(
        event.get("kind") == "tool_call"
        and str(event.get("tool_name") or "") in _EXECUTION_TOOL_NAMES
        for event in turn_events
    ):
        return True
    state_mutation_ops = {
        str(event.get("op") or "")
        for event in turn_events
        if event.get("kind") == "state"
    }
    return bool(
        state_mutation_ops
        & {
            "store_pending_approval_request",
        }
    )


def _build_artifact(*, scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    turn_count = sum(len(scenario.get("turns") or []) for scenario in scenarios)
    return {
        "metadata": {
            "endpoint": "/api/v1/llm/pension-chat-stream",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scenario_count": len(scenarios),
            "turn_count": turn_count,
        },
        "scenarios": scenarios,
    }


def _instrument_runtime(monkeypatch, recorder: list[dict[str, Any]], context: dict[str, Any]) -> None:
    original_local_no_tool = runner_step_handlers._build_local_no_tool_reply
    original_target_reply = stream_prompt_mod._build_target_plan_reply_text
    original_prompt_ui_action = stream_prompt_mod.build_approval_request_ui_action
    original_approval_ui_action = stream_approval_mod.build_approval_request_ui_action
    original_prompt_store_pending = stream_prompt_mod.store_pending_approval_request
    original_stream_store_pending = getattr(stream_orch, "store_pending_approval_request")
    original_cancel_load_pending = approval_cancel_mod.load_pending_approval_request
    original_prompt_store_plan = stream_prompt_mod.store_latest_target_pension_plan
    original_prompt_store_plan_data = stream_prompt_mod.store_latest_target_pension_plan_data
    original_prompt_load_plan = stream_prompt_mod.load_latest_target_pension_plan
    original_prompt_load_plan_data = stream_prompt_mod.load_latest_target_pension_plan_data
    original_approval_load_plan = stream_approval_mod.load_latest_target_pension_plan
    original_approval_load_plan_data = stream_approval_mod.load_latest_target_pension_plan_data

    def _record(kind: str, **payload: Any) -> None:
        recorder.append(
            {
                "kind": kind,
                "case_id": context.get("case_id"),
                "turn_idx": context.get("turn_idx"),
                **payload,
            }
        )

    def _wrap_local_no_tool(*args, **kwargs):
        out = original_local_no_tool(*args, **kwargs)
        if isinstance(out, str) and out.strip():
            _record(
                "producer",
                source="runner_step_handlers._build_local_no_tool_reply",
                reply_preview=out[:300],
            )
        return out

    def _wrap_target_reply(*args, **kwargs):
        out = original_target_reply(*args, **kwargs)
        if isinstance(out, str) and out.strip():
            _record(
                "producer",
                source="stream_system_prompt_generators._build_target_plan_reply_text",
                reply_preview=out[:300],
            )
        return out

    def _wrap_prompt_ui_action(*args, **kwargs):
        out = original_prompt_ui_action(*args, **kwargs)
        _record(
            "producer",
            source="stream_system_prompt_generators.build_approval_request_ui_action",
            tool_name=kwargs.get("tool_name"),
            reply_preview=str(out or "")[:300],
        )
        return out

    def _wrap_approval_ui_action(*args, **kwargs):
        out = original_approval_ui_action(*args, **kwargs)
        _record(
            "producer",
            source="stream_approval_generators.build_approval_request_ui_action",
            tool_name=kwargs.get("tool_name"),
            reply_preview=str(out or "")[:300],
        )
        return out

    def _wrap_state_call(label: str, source: str, fn):
        def _inner(*args, **kwargs):
            result = fn(*args, **kwargs)
            _record("state", op=label, source=source)
            return result

        return _inner

    monkeypatch.setattr(
        runner_step_handlers, "_build_local_no_tool_reply", _wrap_local_no_tool
    )
    monkeypatch.setattr(
        stream_prompt_mod, "_build_target_plan_reply_text", _wrap_target_reply
    )
    monkeypatch.setattr(
        stream_prompt_mod, "build_approval_request_ui_action", _wrap_prompt_ui_action
    )
    monkeypatch.setattr(
        stream_approval_mod,
        "build_approval_request_ui_action",
        _wrap_approval_ui_action,
    )
    monkeypatch.setattr(
        stream_prompt_mod,
        "store_pending_approval_request",
        _wrap_state_call(
            "store_pending_approval_request",
            "stream_system_prompt_generators.store_pending_approval_request",
            original_prompt_store_pending,
        ),
    )
    monkeypatch.setattr(
        stream_orch,
        "store_pending_approval_request",
        _wrap_state_call(
            "store_pending_approval_request",
            "chat_stream_orchestration.store_pending_approval_request",
            original_stream_store_pending,
        ),
    )
    monkeypatch.setattr(
        approval_cancel_mod,
        "load_pending_approval_request",
        _wrap_state_call(
            "load_pending_approval_request",
            "stream_loop_approval_cancel_handling.load_pending_approval_request",
            original_cancel_load_pending,
        ),
    )
    monkeypatch.setattr(
        stream_prompt_mod,
        "store_latest_target_pension_plan",
        _wrap_state_call(
            "store_latest_target_pension_plan",
            "stream_system_prompt_generators.store_latest_target_pension_plan",
            original_prompt_store_plan,
        ),
    )
    monkeypatch.setattr(
        stream_prompt_mod,
        "store_latest_target_pension_plan_data",
        _wrap_state_call(
            "store_latest_target_pension_plan_data",
            "stream_system_prompt_generators.store_latest_target_pension_plan_data",
            original_prompt_store_plan_data,
        ),
    )
    monkeypatch.setattr(
        stream_prompt_mod,
        "load_latest_target_pension_plan",
        _wrap_state_call(
            "load_latest_target_pension_plan",
            "stream_system_prompt_generators.load_latest_target_pension_plan",
            original_prompt_load_plan,
        ),
    )
    monkeypatch.setattr(
        stream_prompt_mod,
        "load_latest_target_pension_plan_data",
        _wrap_state_call(
            "load_latest_target_pension_plan_data",
            "stream_system_prompt_generators.load_latest_target_pension_plan_data",
            original_prompt_load_plan_data,
        ),
    )
    monkeypatch.setattr(
        stream_approval_mod,
        "load_latest_target_pension_plan",
        _wrap_state_call(
            "load_latest_target_pension_plan",
            "stream_approval_generators.load_latest_target_pension_plan",
            original_approval_load_plan,
        ),
    )
    monkeypatch.setattr(
        stream_approval_mod,
        "load_latest_target_pension_plan_data",
        _wrap_state_call(
            "load_latest_target_pension_plan_data",
            "stream_approval_generators.load_latest_target_pension_plan_data",
            original_approval_load_plan_data,
        ),
    )


def _replay_case(
    *,
    api: TestClient,
    Session,
    case: dict[str, Any],
    client_id: int,
    capture: _TraceCapture,
    recorder: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, Any]:
    history: list[dict[str, str]] = []
    turns: list[dict[str, Any]] = []
    turn_idx = 0

    for message in case["conversation"]:
        if str(message.get("role")) != "user":
            continue
        turn_idx += 1
        user_text = str(message.get("content") or "")
        trace_id = f"{case['id']}-turn-{turn_idx}"
        context["turn_idx"] = turn_idx
        trace_event_start = len(capture.events)
        response = api.post(
            "/api/v1/llm/pension-chat-stream",
            json={
                "client_id": client_id,
                "messages": history + [{"role": "user", "content": user_text}],
                "pension_portfolio": [],
                "trace_id": trace_id,
            },
        )
        assert response.status_code == 200
        body = response.text
        assert isinstance(body, str) and body.strip()
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": body})

        turn_events = [
            event
            for event in recorder
            if event.get("case_id") == case["id"]
            and event.get("turn_idx") == turn_idx
        ]
        turn_trace_events = list(capture.events[trace_event_start:])
        legacy_fallback_detected = any(
            event.get("event_type") == "legacy_fallback_entered"
            for event in turn_trace_events
        )
        producer = _producer_for_turn(turn_events)
        turn_record = {
            "turn_index": turn_idx,
            "user_text": user_text,
            "visible_reply_text": body,
            "reply_source_hint": _build_reply_source_hint(
                producer=producer, visible_reply_text=body
            ),
            "trace_event_types": [
                str(event.get("event_type") or "") for event in turn_trace_events
            ],
            "legacy_fallback_detected": legacy_fallback_detected,
            "pending_approval_snapshot": _load_pending_approval_snapshot(
                Session, client_id=client_id
            ),
            "target_plan_snapshot": _load_target_plan_snapshot(
                Session, client_id=client_id
            ),
            "execution_detected": _detect_execution(
                turn_trace_events=turn_trace_events, turn_events=turn_events
            ),
            "raw_http_status": response.status_code,
        }
        assert set(turn_record.keys()) == _TURN_REQUIRED_KEYS
        turns.append(turn_record)

    return {"scenario_id": case["id"], "turns": turns}


def _assert_pending_approval_present(turn_record: dict[str, Any]) -> None:
    pending = turn_record.get("pending_approval_snapshot")
    assert isinstance(pending, dict)
    assert pending.get("has_pending_approval") is True


def _run_proven_replay_scenario(
    *,
    monkeypatch,
    Session,
    capture: _TraceCapture,
    recorder: list[dict[str, Any]],
    context: dict[str, Any],
    client_id: int,
    scenario_id: str,
    second_turn_text: str,
) -> dict[str, Any]:
    _ensure_client(Session, client_id=client_id)
    _clear_client_state(Session, client_id=client_id)
    _seed_executable_target_plan(Session, client_id=client_id)

    def _llm_must_not_run(*args, **kwargs):
        raise AssertionError("LLM must not be called for deterministic replay scenario")

    def _execute_must_not_run(**kwargs):
        tool_name = str(kwargs.get("tool_name") or "")
        raise AssertionError(f"Execution tool must not run in guarded replay scenario: {tool_name}")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat", _llm_must_not_run)
    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", _llm_must_not_run)
    monkeypatch.setattr(exec_mod.pension_llm_service, "chat", _llm_must_not_run)
    monkeypatch.setattr(stream_orch, "execute_tool_call", _execute_must_not_run)

    case = {
        "id": scenario_id,
        "conversation": [
            {"role": "user", "content": "בצע את התכנית"},
            {"role": "user", "content": second_turn_text},
        ],
    }
    context["case_id"] = scenario_id
    context["turn_idx"] = None
    api = TestClient(app)
    return _replay_case(
        api=api,
        Session=Session,
        case=case,
        client_id=client_id,
        capture=capture,
        recorder=recorder,
        context=context,
    )


def test_live_stream_behavior_subset_turn_by_turn_replay_evidence(
    monkeypatch, _test_db
) -> None:
    import app.services.agent_execution.tool_executor as tool_exec_mod

    Session = _test_db["Session"]
    capture = _install_trace_capture(monkeypatch)
    recorder: list[dict[str, Any]] = []
    context: dict[str, Any] = {"case_id": None, "turn_idx": None}
    _instrument_runtime(monkeypatch, recorder, context)

    def fake_execute_tool_call(**kwargs):
        tool_name = str(kwargs.get("tool_name") or "")
        args = kwargs.get("args") if isinstance(kwargs.get("args"), dict) else {}
        recorder.append(
            {
                "kind": "tool_call",
                "case_id": context.get("case_id"),
                "turn_idx": context.get("turn_idx"),
                "tool_name": tool_name,
                "args": dict(args),
            }
        )
        if tool_name == "GET_PENSION_PRODUCTS":
            return json.dumps(
                {
                    "summary": "קיים מוצר פנסיוני אחד",
                    "products": [
                        {"category": "pension", "fund_name": "פנסיה א", "balance": 123456}
                    ],
                },
                ensure_ascii=False,
            )
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            return _build_target_plan_tool_result(args, context)
        if tool_name == "PROCESS_TERMINATION":
            return json.dumps({"status": "done", "choices": args}, ensure_ascii=False)
        return json.dumps({"status": "ok", "tool_name": tool_name}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(tool_exec_mod, "execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(
        stream_prompt_mod,
        "compute_effective_plan_target",
        lambda **kwargs: _fake_compute_effective_plan_target(
            context, float(kwargs.get("desired_total") or 0)
        ),
    )

    api = TestClient(app)
    scenarios: list[dict[str, Any]] = []

    for idx, case in enumerate(_load_cases(), start=1):
        client_id = 981000000 + idx
        _ensure_client(Session, client_id=client_id)
        _clear_client_state(Session, client_id=client_id)
        context["case_id"] = case["id"]
        context["turn_idx"] = None
        fake_llm_service = _FakeLLMService(case, recorder, context)
        monkeypatch.setattr(stream_orch.pension_llm_service, "chat", fake_llm_service.chat)
        monkeypatch.setattr(
            stream_orch.pension_llm_service,
            "chat_stream",
            fake_llm_service.chat_stream,
        )
        monkeypatch.setattr(exec_mod.pension_llm_service, "chat", fake_llm_service.chat)
        case_report = _replay_case(
            api=api,
            Session=Session,
            case=case,
            client_id=client_id,
            capture=capture,
            recorder=recorder,
            context=context,
        )
        scenarios.append(case_report)

    artifact = _build_artifact(scenarios=scenarios)
    _OUTPUT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    planning_baseline = next(
        scenario
        for scenario in scenarios
        if scenario.get("scenario_id") == "BEHAVIOR_03_TARGET_PLAN_NO_TERMINATION_FORCED"
    )
    planning_turn = planning_baseline["turns"][1]
    assert planning_turn["pending_approval_snapshot"]["has_pending_approval"] is False
    assert planning_turn["execution_detected"] is False
    assert "PROCESS_TERMINATION" not in planning_turn["visible_reply_text"]
    assert artifact.get("metadata")
    assert scenarios
    assert all(scenario.get("turns") for scenario in scenarios)


def test_live_stream_replay_veto_blocks_proven_pending_approval_replay(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]
    capture = _install_trace_capture(monkeypatch)
    recorder: list[dict[str, Any]] = []
    context: dict[str, Any] = {"case_id": None, "turn_idx": None}
    _instrument_runtime(monkeypatch, recorder, context)

    scenario = _run_proven_replay_scenario(
        monkeypatch=monkeypatch,
        Session=Session,
        capture=capture,
        recorder=recorder,
        context=context,
        client_id=981100001,
        scenario_id="STAGE_B_REPLAY_VETO_BLOCKS_APPROVAL_REPLAY",
        second_turn_text="לא לבצע עזיבת עבודה",
    )

    assert len(scenario["turns"]) == 2
    _assert_pending_approval_present(scenario["turns"][0])
    second_turn = scenario["turns"][1]
    assert second_turn["execution_detected"] is False
    assert second_turn["pending_approval_snapshot"]["has_pending_approval"] is True
    assert second_turn["pending_approval_snapshot"]["tool_name"] == "TRANSFORM_FUNDS_TO_ASSETS"
    assert "planning_execution_gate_blocked_approval_replay" in second_turn[
        "trace_event_types"
    ], second_turn
    assert "planning_execution_gate_blocked_execution_consume" not in second_turn[
        "trace_event_types"
    ], second_turn


def test_live_stream_replay_planning_followup_blocks_proven_pending_approval_replay(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]
    capture = _install_trace_capture(monkeypatch)
    recorder: list[dict[str, Any]] = []
    context: dict[str, Any] = {"case_id": None, "turn_idx": None}
    _instrument_runtime(monkeypatch, recorder, context)

    scenario = _run_proven_replay_scenario(
        monkeypatch=monkeypatch,
        Session=Session,
        capture=capture,
        recorder=recorder,
        context=context,
        client_id=981100002,
        scenario_id="STAGE_B_REPLAY_PLANNING_FOLLOWUP_BLOCKS_APPROVAL_REPLAY",
        second_turn_text="רק תכנון",
    )

    assert len(scenario["turns"]) == 2
    _assert_pending_approval_present(scenario["turns"][0])
    second_turn = scenario["turns"][1]
    assert second_turn["execution_detected"] is False
    assert second_turn["pending_approval_snapshot"]["has_pending_approval"] is True
    assert second_turn["pending_approval_snapshot"]["tool_name"] == "TRANSFORM_FUNDS_TO_ASSETS"
    assert "planning_execution_gate_blocked_approval_replay" in second_turn[
        "trace_event_types"
    ], second_turn
    assert "planning_execution_gate_blocked_execution_consume" not in second_turn[
        "trace_event_types"
    ], second_turn
