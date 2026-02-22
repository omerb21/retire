# Router Phase 1 Probe Report

## 1) Orchestrate entrypoint שנבחר

- Path: `app/services/llm_chat/orchestration_core/orchestrate.py`
- Function signature: `def orchestrate(input: OrchestrationInput, deps: OrchestrationDeps) -> tuple[OrchestrationDecision, list[TraceEventSpec]]:`

Quoted source (around definition):

```py
def orchestrate(
    input: OrchestrationInput,
    deps: OrchestrationDeps,
) -> tuple[OrchestrationDecision, list[TraceEventSpec]]:
    trace_id = getattr(input, "trace_id", None)

    def _maybe_emit_core_final_response(
        decision: OrchestrationDecision,
        trace_specs: list[TraceEventSpec],
    ) -> None:
        if decision.decision_code not in {
            DecisionCode.RESPOND_ONLY,
            DecisionCode.BLOCKED,
            DecisionCode.NEED_APPROVAL,
            DecisionCode.NEED_USER_TARGET,
        }:
            return
```

## 2) הוכחת שרשרת קריאות לשני מסלולים (stream + non-stream) דרך אותו orchestrate

Non-stream call chain (HTTP -> execute_agent_request -> orchestrate):

1. `app/routers/llm_chat.py:pension_chat()` calls `execute_agent_request()`

```py
@router.post("/pension-chat", response_model=ChatResponse)
async def pension_chat(...):
    ...
    return execute_agent_request(effective_request, db)
```

2. `app/services/agent_execution/execute_agent_request.py:execute_agent_request` imports and calls the same `orchestrate`:

```py
from app.services.llm_chat.orchestration_core.orchestrate import orchestrate
...
_core_decision, _core_trace_specs = orchestrate(_core_input, _core_deps)
```

Stream call chain (HTTP -> execute_agent_request_stream -> orchestrate):

1. `app/routers/llm_chat.py:pension_chat_stream()` calls `execute_agent_request_stream()`

```py
@router.post("/pension-chat-stream")
async def pension_chat_stream(...):
    ...
    return execute_agent_request_stream(effective_request, db)
```

2. `app/services/agent_execution/execute_agent_request.py:execute_agent_request_stream` calls the *same* imported `orchestrate` in its core loop as well:

```py
_core_decision, _core_trace_specs = orchestrate(_core_input, _core_deps)
...
if getattr(_core_decision, "decision_code", None) != DecisionCode.TOOL_CALL:
    break
```

Conclusion: both endpoints (`/pension-chat` and `/pension-chat-stream`) route into `app/services/agent_execution/execute_agent_request.py`, and both call the same `app/services/llm_chat/orchestration_core/orchestrate.py:orchestrate`.

## 3) Tool dispatch point

- Dispatch point file: `app/services/agent_execution/tool_executor.py`
- Dispatch point function: `execute_with_guard(...)`
- Location relative to tool execution loop: this function is invoked from the tool-execution loops (core loop in `execute_agent_request.py`) and is the wrapper that performs guard/contract checks; the **actual dispatch happens immediately before tool execution** when it calls `app.services.llm_chat.tool_execution.execute_tool_call`.

Quoted source (dispatch call):

```py
from app.services.llm_chat.tool_execution import execute_tool_call as _execute_tool_call_impl
...
_exec_kwargs = {
    "tool_name": tool_name,
    "args": tool_args if isinstance(tool_args, dict) else {},
    "client_id": int(request.client_id) if request.client_id is not None else 0,
    "db": db,
    "pension_portfolio": pension_portfolio,
    "force_max_exemption": force_max_exemption,
    "agent_reply": agent_reply,
    "user_approved": user_approved,
}
...
tool_result = _execute_tool_call_impl(**_exec_kwargs)
```
