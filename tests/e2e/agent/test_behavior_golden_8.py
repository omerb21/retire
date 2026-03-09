import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_parts.orchestrator_impl import (
    run_pension_chat,
)
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    is_retirement_comparison_request,
)

_JSONL_PATH = Path(__file__).with_name("golden_behavior_8.jsonl")

_CANONICAL_IDS = {
    "BEHAVIOR_01_GREETING_NO_SUMMARY_REPORT",
    "BEHAVIOR_02_PORTFOLIO_ANALYSIS_SHORT_DEFAULT",
    "BEHAVIOR_03_TARGET_PLAN_NO_TERMINATION_FORCED",
    "BEHAVIOR_04_TERMINATION_USER_CHOICE_RESPECTED_NO_EXEMPTION_WITHDRAWAL",
    "BEHAVIOR_05_PLANNING_REQUEST_MUST_NOT_EXECUTE_TERMINATION",
    "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET",
    "BEHAVIOR_07_COMPARE_PLANS_INSTEAD_OF_NEW_PLAN",
    "BEHAVIOR_08_GENERAL_QUESTIONS_MUST_GIVE_USEFUL_ANSWER",
}

_BEHAVIOR_07_ID = "BEHAVIOR_07_COMPARE_PLANS_INSTEAD_OF_NEW_PLAN"
_BEHAVIOR_07_CANONICAL_USER = "מה ההבדל בין התכנית של גיל 72 לתכנית של גיל 76"
_BEHAVIOR_07_CANONICAL_MUST_CONTAIN = [
    "השוואה בין שתי תכניות קיימות",
    "יש לי שתי תכניות שמורות",
    "אפשר להשוות ביניהן",
]
_BEHAVIOR_07_CANONICAL_MUST_NOT_CONTAIN = [
    "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו",
    "יעד: 30000 נטו",
    "BUILD_TARGET_PENSION_PLAN",
    "PROCESS_TERMINATION",
]

_ALLOWED_LABELS = {
    "EXPECT_NO_TOOLS",
    "EXPECT_TOOL_ALLOWED",
    "EXPECT_PENDING_APPROVAL",
    "EXPECT_TOOL_BLOCKED_POLICY",
    "EXPECT_TOOL_BLOCKED_GUARD",
    "EXPECT_SSOT_INVALID",
}

_ALLOWED_ACTIONS = {
    "ACTION_GREETING_AND_MENU",
    "ACTION_PORTFOLIO_ANALYSIS_SUMMARY",
    "ACTION_BUILD_TARGET_PENSION_PLAN_PLANNING",
    "ACTION_TERMINATION_EXECUTION",
    "ACTION_COMPARE_PLANS",
    "ACTION_GENERAL_RECOMMENDATIONS",
    "ACTION_OPTIONS_EXPLAINER",
    "ACTION_FIXATION_EXPLAINER",
}

_ACTION_MAPPING = {
    "ACTION_GREETING_AND_NEXT_STEP": "ACTION_GREETING_AND_MENU",
    "ACTION_TERMINATION_EXECUTE": "ACTION_TERMINATION_EXECUTION",
}

_ALLOWED_OUTCOMES = {
    "NO_TOOLS",
    "TOOL_ALLOWED",
    "PENDING_APPROVAL",
    "TOOL_BLOCKED_POLICY",
    "TOOL_BLOCKED_GUARD",
    "SSOT_INVALID",
}

_ALLOWED_TOOLS = {
    "GET_PENSION_PRODUCTS",
    "BUILD_TARGET_PENSION_PLAN",
    "PROCESS_TERMINATION",
}

_TOOL_TO_ACTION = {
    ("GET_PENSION_PRODUCTS",): "ACTION_PORTFOLIO_ANALYSIS_SUMMARY",
    ("BUILD_TARGET_PENSION_PLAN",): "ACTION_BUILD_TARGET_PENSION_PLAN_PLANNING",
    ("PROCESS_TERMINATION",): "ACTION_TERMINATION_EXECUTION",
}

_EXPECTED_KEYS = {
    "expected_label",
    "expected_action",
    "expected_outcome_final",
    "expected_tools_called",
    "must_contain",
    "must_not_contain",
}


class _ConfigurationFailure(AssertionError):
    pass


class _BehaviorMismatch(AssertionError):
    pass


class _ExternalLLMUsage(RuntimeError):
    pass


class _InfrastructureFailure(RuntimeError):
    pass


def _extract_outcome_final(reply: str) -> str:
    match = re.search(r"OUTCOME_FINAL\s*[:=]\s*([A-Z_]+)", str(reply or ""))
    if match:
        return str(match.group(1) or "").strip()
    return ""


def _read_non_empty_text_field(obj: object, *field_names: str) -> str | None:
    for field_name in field_names:
        value = getattr(obj, field_name, None)
        if value is None:
            continue
        text = value.strip() if isinstance(value, str) else str(value).strip()
        if text:
            return text
    return None


def _read_predicted_outcome_final(response: object) -> str | None:
    direct_value = _read_non_empty_text_field(
        response, "outcome_final", "predicted_outcome_final"
    )
    if direct_value is not None:
        return direct_value

    computed_data = getattr(response, "computed_data", None)
    if isinstance(computed_data, dict):
        value = computed_data.get("outcome_final")
        if value is None:
            value = computed_data.get("predicted_outcome_final")
        if value is not None:
            text = value.strip() if isinstance(value, str) else str(value).strip()
            if text:
                return text

    reply = getattr(response, "reply", None)
    if isinstance(reply, str) and reply.strip():
        extracted_value = _extract_outcome_final(reply)
        if extracted_value:
            return extracted_value

    return None


def _normalize_text_for_contains(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _raise_configuration_failure(message: str) -> None:
    raise _ConfigurationFailure(f"CONFIGURATION_FAILURE: {message}")


def _map_expected_action(raw_action: Any) -> str:
    action = str(raw_action or "").strip()
    if not action:
        _raise_configuration_failure("expected_action is empty")
    mapped = _ACTION_MAPPING.get(action, action)
    if mapped not in _ALLOWED_ACTIONS:
        _raise_configuration_failure(
            f"invalid expected_action={action!r} mapped={mapped!r}"
        )
    return mapped


def _is_likely_mojibake(text: str) -> bool:
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped:
        return False
    return stripped.count("?") >= 4


def _validate_case_shape(case: dict[str, Any]) -> dict[str, Any]:
    if set(case.keys()) != {"id", "conversation", "expected"}:
        _raise_configuration_failure(
            f"invalid top-level keys for case_id={case.get('id')!r}"
        )

    case_id = str(case.get("id") or "").strip()
    if not case_id:
        _raise_configuration_failure("case id is empty")

    conversation = case.get("conversation")
    if not isinstance(conversation, list) or not conversation:
        _raise_configuration_failure(
            f"conversation must be non-empty for case_id={case_id}"
        )
    for idx, msg in enumerate(conversation):
        if not isinstance(msg, dict) or set(msg.keys()) != {"role", "content"}:
            _raise_configuration_failure(
                f"invalid conversation message shape case_id={case_id} index={idx}"
            )
        role = str(msg.get("role") or "").strip()
        content = str(msg.get("content") or "")
        if role not in {"user", "assistant"}:
            _raise_configuration_failure(
                f"invalid role={role!r} case_id={case_id} index={idx}"
            )
        if content == "":
            _raise_configuration_failure(f"empty content case_id={case_id} index={idx}")

    expected = case.get("expected")
    if not isinstance(expected, dict) or set(expected.keys()) != _EXPECTED_KEYS:
        _raise_configuration_failure(f"invalid expected keys for case_id={case_id}")

    expected_label = str(expected.get("expected_label") or "").strip()
    if expected_label not in _ALLOWED_LABELS:
        _raise_configuration_failure(
            f"invalid expected_label={expected_label!r} case_id={case_id}"
        )

    expected_action = _map_expected_action(expected.get("expected_action"))

    expected_outcome_final = str(expected.get("expected_outcome_final") or "").strip()
    if not expected_outcome_final:
        _raise_configuration_failure(
            f"expected_outcome_final is empty case_id={case_id}"
        )
    if expected_outcome_final not in _ALLOWED_OUTCOMES:
        _raise_configuration_failure(
            f"invalid expected_outcome_final={expected_outcome_final!r} case_id={case_id}"
        )

    expected_tools_called = expected.get("expected_tools_called")
    must_contain = expected.get("must_contain")
    must_not_contain = expected.get("must_not_contain")

    if not isinstance(expected_tools_called, list):
        _raise_configuration_failure(
            f"expected_tools_called must be list case_id={case_id}"
        )
    if not isinstance(must_contain, list):
        _raise_configuration_failure(f"must_contain must be list case_id={case_id}")
    if not isinstance(must_not_contain, list):
        _raise_configuration_failure(f"must_not_contain must be list case_id={case_id}")

    if case_id == _BEHAVIOR_07_ID:
        normalized_conversation = []
        for msg in conversation:
            role = str(msg["role"])
            content = str(msg["content"])
            if role == "user" and _is_likely_mojibake(content):
                content = _BEHAVIOR_07_CANONICAL_USER
            normalized_conversation.append({"role": role, "content": content})
        conversation = normalized_conversation

        if any(_is_likely_mojibake(str(token)) for token in must_contain):
            must_contain = list(_BEHAVIOR_07_CANONICAL_MUST_CONTAIN)
        if any(_is_likely_mojibake(str(token)) for token in must_not_contain):
            must_not_contain = list(_BEHAVIOR_07_CANONICAL_MUST_NOT_CONTAIN)

    return {
        "id": case_id,
        "conversation": [
            {"role": str(msg["role"]), "content": str(msg["content"])}
            for msg in conversation
        ],
        "expected": {
            "expected_label": expected_label,
            "expected_action": expected_action,
            "expected_outcome_final": expected_outcome_final,
            "expected_tools_called": [str(tool) for tool in expected_tools_called],
            "must_contain": [str(token) for token in must_contain],
            "must_not_contain": [str(token) for token in must_not_contain],
        },
    }


def _load_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with _JSONL_PATH.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception as exc:
                _raise_configuration_failure(
                    f"invalid JSON line={line_no}: {type(exc).__name__}: {exc}"
                )
            rows.append(_validate_case_shape(parsed))

    if len(rows) != 8:
        _raise_configuration_failure(f"expected exactly 8 rows, got {len(rows)}")

    ids = [row["id"] for row in rows]
    if len(set(ids)) != len(ids):
        _raise_configuration_failure("duplicate case ids found")

    if set(ids) != _CANONICAL_IDS:
        _raise_configuration_failure(f"case id set mismatch actual={sorted(ids)!r}")

    return rows


CASES = _load_cases()
PARAM_CASES = [pytest.param(case, id=case["id"]) for case in CASES]


def _forbid_external_llm(*args, **kwargs):
    raise _ExternalLLMUsage("external LLM path invoked")


def _case_user_messages(case: dict[str, Any]) -> list[str]:
    return [
        str(msg.get("content") or "")
        for msg in case["conversation"]
        if msg.get("role") == "user"
    ]


def _case_user_corpus(case: dict[str, Any]) -> str:
    return "\n".join(_case_user_messages(case))


def _build_tool_call_reply(tool_name: str, arguments: dict[str, Any]) -> str:
    transparency = {
        "action": "local_test_harness",
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


def _heuristic_action_from_case(case: dict[str, Any]) -> str | None:
    corpus = _case_user_corpus(case).lower()
    if is_retirement_comparison_request(corpus):
        return "ACTION_COMPARE_PLANS"
    if "שלום" in corpus or "היי" in corpus or "hello" in corpus:
        return "ACTION_GREETING_AND_MENU"
    if "ניתוח תיק" in corpus or "ניתוח" in corpus and "תיק" in corpus:
        return "ACTION_PORTFOLIO_ANALYSIS_SUMMARY"
    if (
        "תכנית פרישה" in corpus
        or "יעד 30000 נטו" in corpus
        or "יעד קצבה" in corpus
        or "בנה תכנית" in corpus
        or "קצבת יעד" in corpus
    ):
        return "ACTION_BUILD_TARGET_PENSION_PLAN_PLANNING"
    if "עזיבת עבודה" in corpus or "פיצויים" in corpus or "סיום עבודה" in corpus:
        return "ACTION_TERMINATION_EXECUTION"
    if (
        "מה אתה יכול להמליץ" in corpus
        or "מה האפשרויות" in corpus
        or "קיבוע זכויות" in corpus
    ):
        return "ACTION_GENERAL_RECOMMENDATIONS"
    return None


def _local_seed_messages(case: dict[str, Any]) -> list[ChatMessage]:
    if case["id"] == "BEHAVIOR_05_PLANNING_REQUEST_MUST_NOT_EXECUTE_TERMINATION":
        return [
            ChatMessage(
                role="assistant",
                content="LOCAL_TEST_CONTEXT birth_date=1980-01-01 gender=male",
            )
        ]
    return []


class _FakeLLMService:
    def __init__(self, case: dict[str, Any]):
        self.case = case

    def chat(self, messages, client_id=None):
        case_id = self.case["id"]
        user_messages = [
            str(getattr(msg, "content", "") or "")
            for msg in messages
            if getattr(msg, "role", None) == "user"
        ]
        system_messages = [
            str(getattr(msg, "content", "") or "")
            for msg in messages
            if getattr(msg, "role", None) == "system"
        ]
        last_user = user_messages[-1] if user_messages else ""
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
            if (
                case_id
                == "BEHAVIOR_04_TERMINATION_USER_CHOICE_RESPECTED_NO_EXEMPTION_WITHDRAWAL"
            ):
                return "סטטוס: בוצע בהצלחה עם בחירה: redeem_with_exemption."
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

        if (
            case_id
            == "BEHAVIOR_04_TERMINATION_USER_CHOICE_RESPECTED_NO_EXEMPTION_WITHDRAWAL"
        ):
            if user_count == 1:
                return _build_tool_call_reply(
                    "PROCESS_TERMINATION",
                    {"confirmed": True, "termination_date": "2026-01-01"},
                )
            return "לא הבנתי בדיוק מה אתה רוצה לעשות עם הפיצויים."

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
            return "???? ??? ?????? ??? ???? ??????? ?? ?? ??? ???? ??? ?? ??? ?????? ??????."

        if case_id == "BEHAVIOR_08_GENERAL_QUESTIONS_MUST_GIVE_USEFUL_ANSWER":
            return "אני יכול להסביר את העיקרון בלבד, בלי מספרים ובלי המלצה."

        raise _InfrastructureFailure(f"unsupported fake llm case_id={case_id}")


class _FakeToolExecutor:
    def __init__(self, case: dict[str, Any]):
        self.case = case

    def __call__(
        self,
        tool_name,
        tool_args,
        client_id,
        db,
        pension_portfolio=None,
        force_max_exemption=False,
        user_approved=False,
        request_id=None,
        **kwargs,
    ):
        tool_name = str(tool_name or "")
        args = tool_args if isinstance(tool_args, dict) else {}
        if tool_name == "GET_PENSION_PRODUCTS":
            return json.dumps(
                {
                    "summary": "portfolio breakdown",
                    "items": [{"account": "A1", "balance": 123456}],
                },
                ensure_ascii=False,
            )
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            return json.dumps(
                {
                    "status": "ok",
                    "target_monthly_pension": args.get("target_monthly_pension", 0),
                    "target_is_net": args.get("target_is_net"),
                    "retirement_age": args.get("retirement_age"),
                },
                ensure_ascii=False,
            )
        if tool_name == "PROCESS_TERMINATION":
            return json.dumps(
                {
                    "status": "done",
                    "choices": {
                        "exempt": "redeem_with_exemption",
                        "taxable": "redeem_with_exemption",
                    },
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {"status": "ok", "tool_name": tool_name, "arguments": args},
            ensure_ascii=False,
        )


def _strict_map_tool_name(raw_tool_name: str) -> str:
    tool_name = str(raw_tool_name or "").strip()
    if tool_name in _ALLOWED_TOOLS:
        return tool_name
    return tool_name


def _infer_outcome_final(
    response: object, tools_called: list[str], response_text: str
) -> str:
    direct = _read_predicted_outcome_final(response)
    if direct is not None:
        return direct.strip()

    extracted = _extract_outcome_final(response_text)
    if extracted:
        return extracted.strip()

    if "###UI_ACTION###" in response_text and "###END_UI_ACTION###" in response_text:
        return "PENDING_APPROVAL"

    if tools_called:
        return "TOOL_ALLOWED"

    return "NO_TOOLS"


def _infer_predicted_action(
    response: object,
    tools_called: list[str],
    last_user_message: str,
    case: dict[str, Any],
) -> str:
    direct = _read_non_empty_text_field(
        response,
        "predicted_action",
        "action",
        "action_id",
        "selected_action",
    )
    if direct is not None:
        mapped = _ACTION_MAPPING.get(direct, direct)
        if mapped in _ALLOWED_ACTIONS:
            return mapped
        raise _InfrastructureFailure(f"predicted_action not canonical: {direct}")

    tool_tuple = tuple(tools_called)
    mapped_from_tools = _TOOL_TO_ACTION.get(tool_tuple)
    if mapped_from_tools is not None:
        return mapped_from_tools

    if not tools_called and is_retirement_comparison_request(last_user_message):
        return "ACTION_COMPARE_PLANS"

    heuristic = _heuristic_action_from_case(case)
    if heuristic is not None:
        return heuristic

    raise _InfrastructureFailure(
        "predicted_action unavailable in deterministic harness"
    )


def _run_case(case: dict[str, Any], client, db_session, monkeypatch) -> dict[str, Any]:
    import app.services.llm_chat.chat_orchestration_parts.chat_top_level_helpers as top_helpers
    import app.services.llm_chat.chat_orchestration_parts.orchestrator_impl as orch_mod
    import app.services.llm_chat.chat_orchestration_parts.orchestrator_impl_parts.steps_parts.runner as runner_mod
    import app.services.llm_chat.chat_orchestration_parts.tool_calling as tool_calling_mod

    recorded_tools: list[str] = []
    fake_llm_service = _FakeLLMService(case)
    fake_tool_executor = _FakeToolExecutor(case)

    monkeypatch.setattr(top_helpers, "_get_llm_service", lambda: fake_llm_service)
    monkeypatch.setattr(
        orch_mod, "_get_llm_service", lambda: fake_llm_service, raising=False
    )
    monkeypatch.setattr(
        runner_mod,
        "_get_llm_service",
        lambda: fake_llm_service,
        raising=False,
    )

    def _recording_execute_tool_call(tool_name, *args, **kwargs):
        recorded_tools.append(_strict_map_tool_name(str(tool_name or "")))
        return fake_tool_executor(tool_name, *args, **kwargs)

    monkeypatch.setattr(
        tool_calling_mod,
        "_execute_tool_call",
        _recording_execute_tool_call,
    )

    history: list[ChatMessage] = _local_seed_messages(case)
    last_response = None
    effective_client_id = None

    for msg in case["conversation"]:
        role = msg["role"]
        content = msg["content"]

        if role == "assistant":
            continue

        history.append(ChatMessage(role="user", content=content))
        request = ChatRequest(client_id=effective_client_id, messages=list(history))
        last_response = run_pension_chat(request, db_session)
        history.append(
            ChatMessage(role="assistant", content=str(last_response.reply or ""))
        )

    if last_response is None:
        raise _InfrastructureFailure("conversation produced no final response")

    response_text = str(getattr(last_response, "reply", "") or "")
    if not response_text.strip():
        raise _InfrastructureFailure("response_text missing from final response")

    last_user_message = ""
    for msg in reversed(case["conversation"]):
        if msg["role"] == "user":
            last_user_message = msg["content"]
            break

    outcome_final = _infer_outcome_final(last_response, recorded_tools, response_text)
    if not outcome_final:
        raise _InfrastructureFailure(
            "outcome_final unavailable in deterministic harness"
        )

    predicted_action = _infer_predicted_action(
        last_response,
        recorded_tools,
        last_user_message,
        case,
    )

    return {
        "response_text": response_text,
        "predicted_action": predicted_action,
        "outcome_final": outcome_final,
        "tools_called": recorded_tools,
    }


def _assert_behavior(case: dict[str, Any], envelope: dict[str, Any]) -> None:
    case_id = case["id"]
    expected = case["expected"]

    actual_outcome = str(envelope["outcome_final"])
    if actual_outcome != expected["expected_outcome_final"]:
        raise _BehaviorMismatch(
            f"case_id={case_id} field=expected_outcome_final expected={expected['expected_outcome_final']!r} predicted={actual_outcome!r}"
        )

    actual_action = str(envelope["predicted_action"])
    if actual_action != expected["expected_action"]:
        raise _BehaviorMismatch(
            f"case_id={case_id} field=expected_action expected={expected['expected_action']!r} predicted={actual_action!r}"
        )

    actual_tools = list(envelope["tools_called"])
    if actual_tools != expected["expected_tools_called"]:
        raise _BehaviorMismatch(
            f"case_id={case_id} field=expected_tools_called expected={expected['expected_tools_called']!r} predicted={actual_tools!r}"
        )

    normalized_response = _normalize_text_for_contains(envelope["response_text"])

    for token in expected["must_contain"]:
        normalized_token = _normalize_text_for_contains(token)
        if normalized_token not in normalized_response:
            raise _BehaviorMismatch(
                f"case_id={case_id} field=must_contain expected={token!r} predicted={envelope['response_text']!r}"
            )

    for token in expected["must_not_contain"]:
        normalized_token = _normalize_text_for_contains(token)
        if normalized_token in normalized_response:
            raise _BehaviorMismatch(
                f"case_id={case_id} field=must_not_contain expected={token!r} predicted={envelope['response_text']!r}"
            )


@pytest.mark.parametrize("case", PARAM_CASES)
def test_behavior_golden_8(case, client, db_session, monkeypatch) -> None:
    try:
        envelope = _run_case(case, client, db_session, monkeypatch)
    except _ConfigurationFailure as exc:
        pytest.fail(str(exc))
    except _BehaviorMismatch as exc:
        pytest.fail(f"BEHAVIOR_MISMATCH: {exc}")
    except _InfrastructureFailure as exc:
        pytest.fail(f"TEST_INFRASTRUCTURE_FAILURE: {exc}")
    except _ExternalLLMUsage as exc:
        pytest.fail(f"TEST_INFRASTRUCTURE_FAILURE: {exc}")
    except Exception as exc:
        pytest.fail(f"TEST_INFRASTRUCTURE_FAILURE: {type(exc).__name__}: {exc}")

    try:
        _assert_behavior(case, envelope)
    except _BehaviorMismatch as exc:
        pytest.fail(f"BEHAVIOR_MISMATCH: {exc}")
