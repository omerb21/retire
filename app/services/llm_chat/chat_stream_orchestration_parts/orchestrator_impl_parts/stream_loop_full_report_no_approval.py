from fastapi.responses import StreamingResponse


def _maybe_handle_full_report_no_approval(
    *,
    request,
    db,
    original_user_msg: str,
    lowered_user_msg: str,
    resolved_intent,
    ChatIntentClass,
    is_doc_request: bool,
    is_tax_doc_request: bool,
    is_qa_mode: bool,
    no_tools_requested: bool,
    conceptual_tools_disabled: bool,
    ui_action_short_circuit_allowed: bool,
    latest_snapshot_operation_type,
    stream_execute_tool_no_approval,
    computed_data,
    effective_portfolio,
    force_max_exemption: bool,
    stream_request_id: str,
    is_portfolio_analysis: bool,
):
    if not (
        request.client_id is not None
        and is_doc_request
        and (not is_tax_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
        and (not conceptual_tools_disabled)
        and ui_action_short_circuit_allowed
        and (resolved_intent != ChatIntentClass.REPORT)
    ):
        return None

    latest_op = latest_snapshot_operation_type()
    if latest_op is not None and latest_op != "TRANSFORM_FUNDS_TO_ASSETS":
        return StreamingResponse(
            iter(
                [
                    "כדי להפיק דוח חייבים קודם לבצע המרה (TRANSFORM) כך שהנתונים יהיו במצב יציב."
                ]
            ),
            media_type="text/plain",
        )

    wants_pdf = "pdf" in lowered_user_msg
    return stream_execute_tool_no_approval(
        "GENERATE_FULL_REPORT",
        {
            "output_format": "pdf" if wants_pdf else "html",
            "report_type": "full",
            "ensure_analysis": False,
        },
        computed_data=computed_data,
        client_id=request.client_id,
        db=db,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
    )
