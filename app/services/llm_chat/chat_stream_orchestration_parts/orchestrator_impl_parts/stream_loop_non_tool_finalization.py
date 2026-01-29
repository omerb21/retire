from app.schemas.llm_chat import ChatMessage
from app.services.llm_chat.intent_classifier import ChatIntent


def _stream_finalize_non_tool_response(
    *,
    logger,
    req_id: str,
    stream_request_id: str,
    request,
    history_messages: list[ChatMessage],
    full_response: str,
    resolved_intent,
    tools_disabled_reason: str | None,
    no_tools_requested: bool,
    conceptual_tools_disabled: bool,
    exec_only_active: bool,
    original_user_msg: str,
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
    allowed_sources = build_allowed_sources_for_numeric_provenance(
        request=request,
        history_messages=history_messages,
    )
    if no_tools_requested or (tools_disabled_reason in {"conceptual", "conceptual_form"}):
        final_out = full_response
    else:
        final_out = compute_final_out_with_numeric_provenance_guardrail(
            req_id=req_id,
            request=request,
            full_response=full_response,
            allowed_sources=allowed_sources,
            is_portfolio_analysis=is_portfolio_analysis,
        )

    if (
        resolved_intent == ChatIntent.NO_TOOLS
        and (not exec_only_active)
        and (tools_disabled_reason not in {"conceptual", "conceptual_form"})
    ):
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
                    ChatMessage(role=m["role"], content=m["content"]) for m in rewrite_prompt
                ]
                _buf: list[str] = []
                llm_service = get_llm_service()
                for _chunk in llm_service.chat_stream(rewrite_messages, request.client_id):
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
        if (
            (not exec_only_active)
            and (tools_disabled_reason in {"conceptual", "conceptual_form"})
            and ("###UI_ACTION###" not in (final_out or ""))
            and ("###END_UI_ACTION###" not in (final_out or ""))
        ):
            final_out = sanitize_words_only_conceptual(final_out, original_user_msg or "")
    except Exception:
        pass

    yield final_out
    return False
