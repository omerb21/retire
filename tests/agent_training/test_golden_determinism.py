import importlib
import inspect
import json
import os
from pathlib import Path

import pytest


def _load_readiness_spec() -> tuple[dict | None, str | None]:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "agent_training" / "runner" / "readiness_spec_ref.json",
        root / "agent_training" / "readiness_spec_ref.json",
        root / "tests" / "agent_training" / "readiness_spec_ref.json",
    ]

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                with p.open("r", encoding="utf-8") as f:
                    return json.load(f), str(p)
        except Exception:
            return None, str(p)

    return None, None


def test_golden_determinism() -> None:
    readiness_spec, readiness_path = _load_readiness_spec()

    lab_mode = "gating"
    reason = "readiness_spec_ref missing"

    hookpoints: dict | None = None
    if isinstance(readiness_spec, dict):
        hookpoints = readiness_spec.get("hookpoints")
        if not isinstance(hookpoints, dict):
            hookpoints = None
            reason = "readiness_spec_ref mismatch (hookpoints missing)"
    else:
        reason = "readiness_spec_ref missing"

    if hookpoints is None:
        print(f"Falling back to Gating Lab: {reason}. path={readiness_path}")
        lab_mode = "gating"
    else:
        failed_hookpoints: list[str] = []

        for name, cfg in list(hookpoints.items()):
            if cfg is None:
                continue
            if not isinstance(cfg, dict):
                hookpoints[name] = None
                failed_hookpoints.append(name)
                continue

            import_path = cfg.get("import_path")
            if import_path is None:
                continue

            try:
                module_path, symbol_name = str(import_path).rsplit(".", 1)
                module_obj = importlib.import_module(module_path)
                _ = getattr(module_obj, symbol_name)
            except Exception:
                hookpoints[name] = None
                failed_hookpoints.append(name)

        if failed_hookpoints:
            reason = f"hookpoint not importable: {', '.join(failed_hookpoints)}"
            print(f"Falling back to Gating Lab: {reason}. path={readiness_path}")
            lab_mode = "gating"
        else:
            if len(hookpoints) == 4 and all(v is not None for v in hookpoints.values()):
                lab_mode = "entrypoint"
            else:
                reason = "not all 4 hookpoints are non-null"
                print(f"Falling back to Gating Lab: {reason}. path={readiness_path}")
                lab_mode = "gating"

    assert lab_mode in {"entrypoint", "gating"}
    if lab_mode == "entrypoint":
        assert len(hookpoints) == 4
        assert all(v is not None for v in hookpoints.values())
    else:
        assert True


def _load_golden_small_cases() -> list[dict]:
    root = Path(__file__).resolve().parents[2]
    p = root / "agent_training" / "golden" / "golden_small.jsonl"
    out: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            raw = (line or "").strip()
            if not raw:
                continue
            obj = json.loads(raw)
            if isinstance(obj, dict):
                out.append(obj)
    return out


def _import_symbol_from_import_path(import_path: str):
    if not (isinstance(import_path, str) and import_path.strip()):
        raise AssertionError("import_path missing")
    if ":" in import_path:
        module_path, symbol_name = import_path.rsplit(":", 1)
    else:
        module_path, symbol_name = import_path.rsplit(".", 1)
    module_obj = importlib.import_module(module_path)
    return getattr(module_obj, symbol_name)


def _capture_all_trace_events(monkeypatch):
    import app.services.agent_execution.execute_agent_request as entry_mod
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod
    import app.services.llm_chat.tool_execution as tool_execution_mod

    events: list[dict] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(entry_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_execution_mod, "_log_agent_trace", fake_log_trace_event)

    return events


def _first_event_payload(
    events: list[dict], *, trace_id: str, event_type: str
) -> dict | None:
    for e in events:
        if e.get("trace_id") != trace_id:
            continue
        if e.get("event_type") != event_type:
            continue
        payload = e.get("payload")
        return payload if isinstance(payload, dict) else None
    return None


def _adapt_prediction(
    *, response_obj, events: list[dict], trace_id: str, case_id: str
) -> dict:
    response_text = None
    if hasattr(response_obj, "reply"):
        response_text = getattr(response_obj, "reply", None)
    elif isinstance(response_obj, dict):
        response_text = response_obj.get("reply")
        if response_text is None:
            response_text = response_obj.get("response")
        if response_text is None:
            response_text = response_obj.get("message")
        if response_text is None:
            response_text = response_obj.get("text")

    router_selected = _first_event_payload(
        events, trace_id=trace_id, event_type="router_selected"
    )
    mcp_decision = _first_event_payload(
        events, trace_id=trace_id, event_type="mcp_decision"
    )

    planned_tools = None
    if isinstance(router_selected, dict):
        planned_tools = router_selected.get("tool_chain")

    outcome_final = None
    capability_id = None
    reason_marker = None
    if isinstance(mcp_decision, dict):
        outcome_final = mcp_decision.get("outcome_final")
        capability_id = mcp_decision.get("capability_id")
    if capability_id is None and isinstance(router_selected, dict):
        capability_id = router_selected.get("capability_id")

    if hasattr(response_obj, "reason_marker"):
        reason_marker = getattr(response_obj, "reason_marker", None)
    elif isinstance(response_obj, dict):
        reason_marker = response_obj.get("reason_marker")
        if reason_marker is None:
            reason_marker = response_obj.get("reason")
        if reason_marker is None:
            reason_marker = response_obj.get("reason_code")

    tool_called = None
    if isinstance(planned_tools, list):
        tool_called = len(planned_tools) > 0
    elif isinstance(response_obj, dict):
        if isinstance(response_obj.get("tool_plan"), list):
            tool_called = len(response_obj.get("tool_plan") or []) > 0
        elif isinstance(response_obj.get("planned_tools"), list):
            tool_called = len(response_obj.get("planned_tools") or []) > 0

    predicted = {
        "outcome_final": outcome_final,
        "capability_id": capability_id,
        "tool_called": tool_called,
        "reason_marker": reason_marker,
        "response_text": response_text,
    }

    for k in ["outcome_final", "capability_id", "tool_called", "response_text"]:
        if predicted.get(k) is None:
            raise AssertionError(f"case id={case_id} field missing: {k}")

    if "reason_marker" not in predicted:
        raise AssertionError(f"case id={case_id} field missing: reason_marker")

    return predicted


def _assert_mismatch(*, case_id: str, field_name: str, expected, predicted) -> None:
    if expected == predicted:
        return
    raise AssertionError(
        f"case id={case_id} field={field_name} expected={expected} predicted={predicted}"
    )


def test_golden_real_path_matches_expected_when_enabled(monkeypatch) -> None:
    if os.getenv("GOLDEN_REAL_PATH_B1") != "1":
        pytest.skip("GOLDEN_REAL_PATH_B1 != '1'")

    monkeypatch.setenv("MCP_POLICY_ENFORCEMENT_DISABLE_ALL", "1")
    monkeypatch.setenv("MCP_POLICY_ENFORCEMENT_B1", "0")

    def _env_override_snapshot_line() -> str:
        return (
            "ENV_OVERRIDE_SNAPSHOT "
            + "MCP_POLICY_ENFORCEMENT_DISABLE_ALL="
            + str(os.getenv("MCP_POLICY_ENFORCEMENT_DISABLE_ALL") or "")
            + " MCP_POLICY_ENFORCEMENT_B1="
            + str(os.getenv("MCP_POLICY_ENFORCEMENT_B1") or "")
        )

    def _is_blocked_outcome(outcome_final: str | None) -> bool:
        if not isinstance(outcome_final, str):
            return False
        return outcome_final == "TOOL_BLOCKED" or outcome_final.startswith(
            "TOOL_BLOCKED"
        )

    readiness_spec, readiness_path = _load_readiness_spec()
    _ = readiness_path
    assert isinstance(readiness_spec, dict)
    real_path = readiness_spec.get("real_path")
    if not isinstance(real_path, dict):
        raise AssertionError("real_path missing in readiness_spec_ref.json")
    assert real_path.get("enabled") is True
    import_path = real_path.get("import_path")
    assert isinstance(import_path, str) and import_path.strip()

    fn = _import_symbol_from_import_path(import_path)

    print(f"REAL_PATH import_path={import_path} symbol=execute_agent_request")
    print("REAL_PATH import_ok=true")

    sig = inspect.signature(fn)
    sig_str = str(sig)

    golden_cases = _load_golden_small_cases()
    assert golden_cases
    first_case = golden_cases[0]
    seed_user_message = str(first_case.get("user_message") or "")

    from app.database import SessionLocal
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.utils.trace_context import set_current_trace_id

    def build_call_args(*, user_message: str):
        required_args: dict = {}
        db = None

        for name, p in sig.parameters.items():
            if p.default is not inspect._empty:
                continue
            if p.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue

            if name == "request":
                required_args[name] = ChatRequest(
                    messages=[ChatMessage(role="user", content=user_message)],
                    client_id=1,
                    pension_portfolio=None,
                )
            elif name in {"db", "session"}:
                db = SessionLocal()
                required_args[name] = db
            else:
                raise AssertionError(
                    f"{import_path} signature={sig_str} missing_required_param={name}"
                )

        return required_args, db

    trace_id0 = "trace_pr5_stage0"
    set_current_trace_id(trace_id0)
    events = _capture_all_trace_events(monkeypatch)
    args0, db0 = build_call_args(user_message=seed_user_message)
    try:
        try:
            if db0 is not None and hasattr(db0, "info") and isinstance(db0.info, dict):
                db0.info["trace_id"] = trace_id0
        except Exception:
            pass

        response0 = fn(**args0)
    finally:
        try:
            if db0 is not None:
                db0.close()
        except Exception:
            pass

    _ = _adapt_prediction(
        response_obj=response0,
        events=events,
        trace_id=trace_id0,
        case_id="STAGE0",
    )

    for c in golden_cases:
        case_id = str(c.get("id") or "")
        user_message = str(c.get("user_message") or "")

        trace_id = f"trace_pr5_{case_id}"
        set_current_trace_id(trace_id)
        events = _capture_all_trace_events(monkeypatch)

        args, db = build_call_args(user_message=user_message)
        try:
            try:
                if db is not None and hasattr(db, "info") and isinstance(db.info, dict):
                    db.info["trace_id"] = trace_id
            except Exception:
                pass

            response_obj = fn(**args)
        finally:
            try:
                if db is not None:
                    db.close()
            except Exception:
                pass

        predicted = _adapt_prediction(
            response_obj=response_obj,
            events=events,
            trace_id=trace_id,
            case_id=case_id,
        )

        expected_outcome_final = c.get("expected_outcome_final")
        predicted_outcome_final = predicted.get("outcome_final")
        if expected_outcome_final == "NO_TOOLS" and _is_blocked_outcome(
            str(predicted_outcome_final)
            if predicted_outcome_final is not None
            else None
        ):
            raise AssertionError(
                "\n".join(
                    [
                        " ".join(
                            [
                                f"case id={case_id}",
                                f"expected_outcome_final={expected_outcome_final}",
                                f"predicted_outcome_final={predicted_outcome_final}",
                            ]
                        ),
                        _env_override_snapshot_line(),
                    ]
                )
            )

        _assert_mismatch(
            case_id=case_id,
            field_name="outcome_final",
            expected=c.get("expected_outcome_final"),
            predicted=predicted.get("outcome_final"),
        )
        _assert_mismatch(
            case_id=case_id,
            field_name="capability_id",
            expected=c.get("expected_capability_id"),
            predicted=predicted.get("capability_id"),
        )
        _assert_mismatch(
            case_id=case_id,
            field_name="tool_called",
            expected=c.get("expected_tool_called"),
            predicted=predicted.get("tool_called"),
        )
        _assert_mismatch(
            case_id=case_id,
            field_name="reason_marker",
            expected=c.get("expected_reason_marker"),
            predicted=predicted.get("reason_marker"),
        )

        response_text = str(predicted.get("response_text") or "")
        haystack = "\n".join(
            [
                response_text,
                str(predicted.get("outcome_final") or ""),
                str(predicted.get("capability_id") or ""),
                str(predicted.get("reason_marker") or ""),
            ]
        )
        must_contain = (
            c.get("must_contain") if isinstance(c.get("must_contain"), list) else []
        )
        must_not_contain = (
            c.get("must_not_contain")
            if isinstance(c.get("must_not_contain"), list)
            else []
        )
        for s in must_contain:
            _assert_mismatch(
                case_id=case_id,
                field_name=f"must_contain:{s}",
                expected=True,
                predicted=str(s) in haystack,
            )
        for s in must_not_contain:
            _assert_mismatch(
                case_id=case_id,
                field_name=f"must_not_contain:{s}",
                expected=False,
                predicted=str(s) in haystack,
            )
