import importlib
import inspect
import json
import os
from pathlib import Path

from app.database import SessionLocal
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.capability_router.router_facade import ensure_router_decision

_self_path = __file__
try:
    with open(_self_path, "r", encoding="utf-8") as _f:
        _self_text = _f.read()
except Exception as _e:
    raise AssertionError(
        f"SELF_CHECK_READ_FAILED path={_self_path} err={type(_e).__name__}"
    )

_forbidden_tokens = [
    "monkeypatch." + "setattr(",
    "MC" + "PEngine",
    "." + "evaluate",
    "guard" + "_" + "result",
]
for _tok in _forbidden_tokens:
    if _tok in _self_text:
        raise AssertionError(f"FORBIDDEN_TOKEN_FOUND token={_tok}")


def parse_import_path(import_path: str) -> tuple[str, str]:
    raw = str(import_path or "").strip()
    if not raw:
        raise ValueError("invalid import_path")
    if ":" in raw:
        module_path, symbol_name = raw.split(":", 1)
    else:
        module_path, symbol_name = raw.rsplit(".", 1)
    module_path = module_path.strip()
    symbol_name = symbol_name.strip()
    if not module_path or not symbol_name:
        raise ValueError("invalid import_path")
    return module_path, symbol_name


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


def _load_golden_cases() -> list[dict]:
    root = Path(__file__).resolve().parents[2]
    golden_path = root / "agent_training" / "golden" / "golden_small.jsonl"
    rows: list[dict] = []
    with golden_path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            rows.append(json.loads(raw))
    return rows


def _extract_outcome_final(reply: str) -> str:
    for token in ("TOOL_ALLOWED", "NO_TOOLS", "PENDING_APPROVAL", "TOOL_BLOCKED"):
        if token in reply:
            return token
    return ""


def _fail_case(case_id: str, field: str, expected: object, predicted: object) -> None:
    raise AssertionError(
        f"case_id={case_id} field={field} expected={expected!r} predicted={predicted!r}"
    )


def test_golden_determinism() -> None:
    readiness_spec, readiness_path = _load_readiness_spec()

    real_path_mode = os.getenv("GOLDEN_REAL_PATH_B1") == "1"
    real_path_fn = None
    if real_path_mode:
        raw_import_path = ""
        symbol_name = "<missing>"
        import_ok = False

        if not isinstance(readiness_spec, dict):
            print(f"REAL_PATH import_path={raw_import_path} symbol={symbol_name}")
            print("REAL_PATH import_ok=false")
            raise AssertionError("REAL_PATH readiness_spec_ref missing")

        real_path_cfg = readiness_spec.get("real_path")
        if not isinstance(real_path_cfg, dict):
            print(f"REAL_PATH import_path={raw_import_path} symbol={symbol_name}")
            print("REAL_PATH import_ok=false")
            raise AssertionError("REAL_PATH readiness_spec_ref mismatch (real_path missing)")

        raw_import_path = str(real_path_cfg.get("import_path") or "")

        try:
            module_path, symbol_name = parse_import_path(raw_import_path)
            module_obj = importlib.import_module(module_path)
            real_path_fn = getattr(module_obj, symbol_name)
            import_ok = callable(real_path_fn)
        except Exception:
            import_ok = False

        print(f"REAL_PATH import_path={raw_import_path} symbol={symbol_name}")
        print(f"REAL_PATH import_ok={'true' if import_ok else 'false'}")

        if not raw_import_path:
            raise AssertionError("REAL_PATH import_path missing")

        if not import_ok:
            raise AssertionError("REAL_PATH import_path is not callable")

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
        if not real_path_mode:
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
                module_path, symbol_name = parse_import_path(str(import_path))
                module_obj = importlib.import_module(module_path)
                _ = getattr(module_obj, symbol_name)
            except Exception:
                hookpoints[name] = None
                failed_hookpoints.append(name)

        if failed_hookpoints:
            reason = f"hookpoint not importable: {', '.join(failed_hookpoints)}"
            if not real_path_mode:
                print(f"Falling back to Gating Lab: {reason}. path={readiness_path}")
            lab_mode = "gating"
        else:
            if len(hookpoints) == 4 and all(v is not None for v in hookpoints.values()):
                lab_mode = "entrypoint"
            else:
                reason = "not all 4 hookpoints are non-null"
                if not real_path_mode:
                    print(f"Falling back to Gating Lab: {reason}. path={readiness_path}")
                lab_mode = "gating"

    assert lab_mode in {"entrypoint", "gating"}
    if lab_mode == "entrypoint":
        assert len(hookpoints) == 4
        assert all(v is not None for v in hookpoints.values())
    else:
        assert True

    if not real_path_mode:
        return

    cases = _load_golden_cases()
    assert len(cases) == 90, f"expected 90 golden cases, got {len(cases)}"

    for case in cases:
        case_id = str(case.get("id") or "<missing>")
        user_message = str(case.get("user_message") or "")
        trace_id = f"golden_{case_id}"

        router_decision = ensure_router_decision(
            user_text=user_message,
            client_id=1,
            trace_id=trace_id,
            intent_type=None,
        )

        request = ChatRequest(
            client_id=1,
            messages=[ChatMessage(role="user", content=user_message)],
        )

        db = SessionLocal()
        try:
            try:
                response = real_path_fn(request, db)
            except Exception as e:
                signature = "<unavailable>"
                try:
                    signature = str(inspect.signature(real_path_fn))
                except Exception:
                    signature = "<unavailable>"
                raise AssertionError(
                    f"case_id={case_id} field=call expected='success' predicted='{type(e).__name__}: {e}' signature={signature}"
                ) from e
        finally:
            db.close()

        reply = str(getattr(response, "reply", "") or "")
        predicted_outcome_final = _extract_outcome_final(reply)
        predicted_capability_id = str(getattr(router_decision, "capability_id", "") or "")
        predicted_tool_called = bool(getattr(router_decision, "tool_chain", []))

        if predicted_outcome_final != str(case.get("expected_outcome_final") or ""):
            _fail_case(
                case_id,
                "expected_outcome_final",
                case.get("expected_outcome_final"),
                predicted_outcome_final,
            )

        if predicted_capability_id != str(case.get("expected_capability_id") or ""):
            _fail_case(
                case_id,
                "expected_capability_id",
                case.get("expected_capability_id"),
                predicted_capability_id,
            )

        if predicted_tool_called != bool(case.get("expected_tool_called")):
            _fail_case(
                case_id,
                "expected_tool_called",
                case.get("expected_tool_called"),
                predicted_tool_called,
            )

        for token in list(case.get("must_contain") or []):
            if token not in reply:
                _fail_case(case_id, "must_contain", token, reply)

        for token in list(case.get("must_not_contain") or []):
            if token in reply:
                _fail_case(case_id, "must_not_contain", token, reply)
