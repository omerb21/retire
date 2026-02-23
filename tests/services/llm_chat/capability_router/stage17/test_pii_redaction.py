import json


def test_pii_redaction_removes_pii_before_persist(monkeypatch) -> None:
    from app.services.agent_eyes import event_collector as ec

    monkeypatch.setenv("TRACE_PII_REDACTION_ENABLED", "1")

    persisted = []

    class FakeSession:
        def add(self, row):
            persisted.append(row)

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    ec._session_factory_override = lambda: FakeSession()

    payload = {
        "email": "user@example.com",
        "phone": "050-1234567",
        "id": "123456789",
        "address": "Main St 1, Tel Aviv",
        "note": "contact user@example.com please",
    }

    ec.emit_event("pii_test", payload)

    assert persisted
    row = persisted[-1]
    pj = getattr(row, "payload_json", None)
    assert isinstance(pj, str)

    assert "user@example.com" not in pj
    assert "050-1234567" not in pj
    assert "123456789" not in pj
    assert "Main St" not in pj

    parsed = json.loads(pj)
    assert parsed.get("email") == "[REDACTED]"
    assert parsed.get("phone") == "[REDACTED]"
    assert parsed.get("id") == "[REDACTED]"
    assert parsed.get("address") == "[REDACTED]"
    assert "user@example.com" not in (parsed.get("note") or "")


def test_pii_redaction_failure_never_persists_original_payload(monkeypatch) -> None:
    from app.services.agent_eyes import event_collector as ec
    import app.services.agent_trace_logger as trace_logger_mod

    monkeypatch.setenv("TRACE_PII_REDACTION_ENABLED", "1")

    persisted = []

    class FakeSession:
        def add(self, row):
            persisted.append(row)

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    ec._session_factory_override = lambda: FakeSession()

    events = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = (trace_id, kwargs)
        events.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    class Unserializable:
        def __repr__(self) -> str:
            return "Unserializable(user@example.com)"

    payload = Unserializable()

    ec.emit_event("pii_test_fail", payload)

    assert persisted
    row = persisted[-1]
    pj = getattr(row, "payload_json", None)
    assert isinstance(pj, str)

    assert "user@example.com" not in pj

    parsed = json.loads(pj)
    assert parsed == {"redaction_failed": True}

    assert any(e.get("event_type") == "pii_redaction_failed" for e in events)
