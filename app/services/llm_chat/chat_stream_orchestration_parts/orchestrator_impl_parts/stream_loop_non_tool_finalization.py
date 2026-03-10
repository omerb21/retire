from app.schemas.llm_chat import ChatMessage
from app.services.llm_chat.chat_orchestration_parts.orchestrator_impl_parts.steps_parts.runner_step_handlers import (  # noqa: E501
    _build_local_no_tool_reply,
    _format_portfolio_style_reply,
    _resolve_local_trace_id,
    is_portfolio_like_reply_candidate,
)
from app.services.llm_chat.intent_classifier import ChatIntent
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    is_simple_greeting_request,
)


def _stream_finalize_non_tool_response(
    *,
    logger,
    req_id: str,
    stream_request_id: str,
    request,
    db,
    history_messages: list[ChatMessage],
    full_response: str,
    resolved_intent,
    tools_disabled_reason: str | None,
    no_tools_requested: bool,
    conceptual_tools_disabled: bool,
    exec_only_active: bool,
    original_user_msg: str,
    is_comparison_request: bool,
    is_portfolio_analysis: bool,
    build_allowed_sources_for_numeric_provenance,
    compute_final_out_with_numeric_provenance_guardrail,
    postprocess_no_tools_user_visible_text,
    validate_execution_only_output,
    build_exec_only_rewrite_prompt,
    get_llm_service,
    build_execution_only_fallback,
    enforce_behavioral_limits,
    sanitize_words_only_output,
    sanitize_words_only_conceptual,
):
    def _log_stream_trace_event(event_type: str, payload: dict[str, object]) -> None:
        try:
            from app.services.agent_trace_logger import log_trace_event

            log_trace_event(
                trace_id=_resolve_local_trace_id(
                    request=request,
                    db=db,
                    request_id=stream_request_id,
                ),
                event_type=event_type,
                payload=payload,
            )
        except Exception:
            pass

    def _count_visible_lines(text: str | None) -> int:
        return len([line for line in str(text or "").splitlines() if line.strip()])

    allowed_sources = build_allowed_sources_for_numeric_provenance(
        request=request,
        history_messages=history_messages,
    )
    if no_tools_requested or (
        tools_disabled_reason in {"conceptual", "conceptual_form"}
    ):
        final_out = full_response
    else:
        final_out = compute_final_out_with_numeric_provenance_guardrail(
            req_id=req_id,
            request=request,
            full_response=full_response,
            allowed_sources=allowed_sources,
            is_portfolio_analysis=is_portfolio_analysis,
        )

    advisory_override_used = False
    local_reply_allowed = (not exec_only_active) and (
        resolved_intent == ChatIntent.NO_TOOLS
        or is_simple_greeting_request(original_user_msg)
    )
    if local_reply_allowed:
        advisory_local_reply = _build_local_no_tool_reply(
            request=request,
            db=db,
            request_id=stream_request_id,
            original_user_msg=original_user_msg,
            is_comparison_request=bool(is_comparison_request),
            has_tool_results=False,
            raw_reply=final_out,
        )
        if isinstance(advisory_local_reply, str) and advisory_local_reply.strip():
            final_out = advisory_local_reply.strip()
            advisory_override_used = True
        elif tools_disabled_reason not in {"conceptual", "conceptual_form"}:
            final_out = postprocess_no_tools_user_visible_text(final_out)

    if exec_only_active and resolved_intent != ChatIntent.REPORT:
        try:
            validate_execution_only_output(final_out)
        except Exception as e:
            try:
                rewrite_prompt = build_exec_only_rewrite_prompt(
                    bad_text=final_out,
                    user_request_text=original_user_msg or "",
                )
                rewrite_messages = [
                    ChatMessage(role=m["role"], content=m["content"])
                    for m in rewrite_prompt
                ]
                _buf: list[str] = []
                llm_service = get_llm_service()
                for _chunk in llm_service.chat_stream(
                    rewrite_messages, request.client_id
                ):
                    if _chunk:
                        _buf.append(str(_chunk))
                rewritten = "".join(_buf)
                validate_execution_only_output(rewritten)
                final_out = rewritten
            except Exception as e2:
                reason = getattr(e2, "reason", getattr(e, "reason", "policy_violation"))
                logger.warning(
                    "EXECUTION_ONLY BLOCKED endpoint=stream trace_id=%s reason=%s",
                    stream_request_id,
                    reason,
                )
                yield build_execution_only_fallback(original_user_msg or "")
                return True

    if (
        (not exec_only_active)
        and (not conceptual_tools_disabled)
        and (not no_tools_requested)
        and (
            "###UI_ACTION###" not in (final_out or "")
            and "###END_UI_ACTION###" not in (final_out or "")
        )
    ):
        _allowed, final_out = enforce_behavioral_limits(final_out)

    if no_tools_requested:
        final_out = sanitize_words_only_output(final_out)

    try:
        if (not advisory_override_used) and (
            (not exec_only_active)
            and (tools_disabled_reason in {"conceptual", "conceptual_form"})
            and ("###UI_ACTION###" not in (final_out or ""))
            and ("###END_UI_ACTION###" not in (final_out or ""))
        ):
            final_out = sanitize_words_only_conceptual(
                final_out, original_user_msg or ""
            )
    except Exception:
        pass

    if (
        (not exec_only_active)
        and ("###UI_ACTION###" not in (final_out or ""))
        and ("###END_UI_ACTION###" not in (final_out or ""))
        and is_portfolio_like_reply_candidate(final_out)
    ):
        line_count_before = _count_visible_lines(final_out)
        _log_stream_trace_event(
            "portfolio_reply_detected_for_formatting",
            {
                "formatting_candidate": True,
                "line_count_before": line_count_before,
            },
        )
        formatted_out = _format_portfolio_style_reply(final_out)
        if isinstance(formatted_out, str) and formatted_out.strip():
            final_out = formatted_out.strip()
            _log_stream_trace_event(
                "portfolio_reply_formatted",
                {
                    "formatted": True,
                    "line_count_before": line_count_before,
                    "line_count_after": _count_visible_lines(final_out),
                },
            )

    yield final_out
    return False
