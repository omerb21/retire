from __future__ import annotations

from typing import Any

import yaml


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded if isinstance(loaded, dict) else {}


def test_stage16_golden_qa_suite(monkeypatch) -> None:
    import app.services.agent_trace_logger as trace_logger_mod
    from app.services.llm_chat.capability_router.qa_claims_guard import \
        guard_qa_answer_payload

    fixture = _load_yaml("tests/fixtures/stage16/golden_qa_questions.yaml")
    questions = fixture.get("questions") if isinstance(fixture.get("questions"), list) else []
    assert questions

    events: list[dict[str, Any]] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append({"trace_id": trace_id, "event_type": event_type, "payload": payload})

    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    for q in questions:
        question_id = str(q.get("question_id") or "")
        qa_payload = q.get("qa_answer_payload") if isinstance(q.get("qa_answer_payload"), dict) else {}
        expected = q.get("expected") if isinstance(q.get("expected"), dict) else {}

        events.clear()

        out = guard_qa_answer_payload(
            qa_answer_payload=qa_payload,
            trace_id=f"trace_{question_id}",
            client_id=1,
            detected_capability_id="default_qa_v1",
        )

        blocked = isinstance(out, dict) and out.get("status") == "policy_blocked"
        assert blocked is bool(expected.get("blocked"))

        if blocked:
            assert out.get("policy_reasons") == expected.get("policy_reasons")
        else:
            assert out.get("mode") == "QA"
            assert isinstance(out.get("answer_blocks"), list)

        for e in events:
            assert e.get("event_type") not in {"tool_call", "tool_result"}
