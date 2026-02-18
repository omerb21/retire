from __future__ import annotations

import inspect
from typing import Any, Callable, Generator


def _maybe_yield_from(res: Any) -> Any:
    if inspect.isgenerator(res):
        return (yield from res)
    return res


def run_orchestration_loop_core(
    *,
    max_steps: int,
    current_step: int,
    tool_call_marker: str,
    get_llm_reply: Callable[[int], Any],
    handle_tool_call: Callable[[str, int], Any],
    handle_non_tool_call: Callable[[str, int], Any],
    pre_dispatch: Callable[[str, int], Any] | None = None,
) -> Generator[Any, None, tuple[str, int]]:
    while current_step < max_steps:
        should_break, raw_reply, current_step = yield from _maybe_yield_from(
            get_llm_reply(current_step)
        )
        if should_break:
            return ("break", current_step)

        if pre_dispatch is not None:
            directive, current_step = yield from _maybe_yield_from(
                pre_dispatch(raw_reply, current_step)
            )
            if directive == "return":
                return ("return", current_step)
            if directive == "break":
                return ("break", current_step)
            if directive == "continue":
                continue

        if tool_call_marker in (raw_reply or ""):
            directive, current_step = yield from _maybe_yield_from(
                handle_tool_call(raw_reply, current_step)
            )
        else:
            directive, current_step = yield from _maybe_yield_from(
                handle_non_tool_call(raw_reply, current_step)
            )

        if directive == "return":
            return ("return", current_step)
        if directive == "break":
            return ("break", current_step)
        if directive == "continue":
            continue

    return ("break", current_step)


def run_orchestration_loop_core_sync(
    *,
    max_steps: int,
    current_step: int,
    tool_call_marker: str,
    get_llm_reply: Callable[[int], Any],
    handle_tool_call: Callable[[str, int], Any],
    handle_non_tool_call: Callable[[str, int], Any],
    pre_dispatch: Callable[[str, int], Any] | None = None,
) -> tuple[str, int]:
    gen = run_orchestration_loop_core(
        max_steps=max_steps,
        current_step=current_step,
        tool_call_marker=tool_call_marker,
        get_llm_reply=get_llm_reply,
        handle_tool_call=handle_tool_call,
        handle_non_tool_call=handle_non_tool_call,
        pre_dispatch=pre_dispatch,
    )
    try:
        while True:
            next(gen)
    except StopIteration as e:
        return e.value
