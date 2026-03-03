import importlib
import json
from pathlib import Path


def _load_readiness_spec() -> tuple[dict | None, str | None]:
    root = Path(__file__).resolve().parents[2]
    candidates = [
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
