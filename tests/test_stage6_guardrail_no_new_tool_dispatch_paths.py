from __future__ import annotations

from pathlib import Path


def test_stage6_guardrail_no_new_tool_dispatch_paths() -> None:
    """Guardrail: ensure tool dispatch SSOT wasn't bypassed.

    We allow importing/calling the raw tool execution implementation only from
    the SSOT wrapper (agent_execution/tool_executor.py). No other module should
    import `execute_tool_call` from `app.services.llm_chat.tool_execution`.

    This is a refactor safety net to prevent accidental new dispatch paths.
    """

    repo_root = Path(__file__).resolve().parents[1]

    allowed_file = repo_root / "app" / "services" / "agent_execution" / "tool_executor.py"
    assert allowed_file.exists()

    offenders: list[str] = []

    for py_file in (repo_root / "app").rglob("*.py"):
        if py_file == allowed_file:
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if "app.services.llm_chat.tool_execution import execute_tool_call" in text:
            offenders.append(str(py_file.relative_to(repo_root)))
            continue

        if "tool_execution.execute_tool_call" in text:
            offenders.append(str(py_file.relative_to(repo_root)))
            continue

    assert offenders == [], f"Found forbidden tool dispatch import/usage outside SSOT: {offenders}"
