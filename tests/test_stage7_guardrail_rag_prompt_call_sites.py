from __future__ import annotations

from pathlib import Path


def test_stage7_guardrail_rag_prompt_called_only_from_message_preparation() -> None:
    """Guardrail: keep a single SSOT injection point for RAG.

    Stage 7 requires a single conditional gate at the existing injection point.
    This test ensures we don't introduce any new call sites to
    `build_rag_system_message` beyond `app/services/llm_chat/message_preparation.py`.

    Deterministic: static scan only.
    """

    repo_root = Path(__file__).resolve().parents[1]
    allowed = repo_root / "app" / "services" / "llm_chat" / "message_preparation.py"
    assert allowed.exists()

    offenders: list[str] = []

    for py_file in (repo_root / "app").rglob("*.py"):
        if py_file == allowed:
            continue

        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if (
            "build_rag_system_message(" in text
            and "def build_rag_system_message" not in text
        ):
            offenders.append(str(py_file.relative_to(repo_root)))

    assert (
        offenders == []
    ), f"Unexpected build_rag_system_message call sites: {offenders}"
