import os

import pytest


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/routers/llm_chat.py",
        "app/routers/agent_trace_debug.py",
    ],
)
def test_routers_do_not_reference_execute_tool_call(relative_path: str) -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    abs_path = os.path.join(repo_root, *relative_path.split("/"))

    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "execute_tool_call" not in content
