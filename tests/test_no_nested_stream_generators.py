import re
from pathlib import Path


def test_orchestrator_has_no_nested_generate_defs():
    target = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "llm_chat"
        / "chat_stream_orchestration_parts"
        / "orchestrator.py"
    )
    text = target.read_text(encoding="utf-8")

    pattern = re.compile(r"^[ \t]+def[ \t]+generate_", re.MULTILINE)
    matches = pattern.findall(text)

    if matches:
        lines = text.splitlines()
        matched_lines = [line for line in lines if pattern.match(line)]
        preview = "\n".join(matched_lines[:20])
        assert (
            not matches
        ), f"Found nested generate_ defs in orchestrator.py (first 20):\n{preview}"

    assert not matches
