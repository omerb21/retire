from fastapi.responses import StreamingResponse

from app.schemas.llm_chat import ChatRequest

from ..stream_streaming_helpers import _stream_execute_tool_no_approval


def _maybe_handle_fixation_documents_deterministic(
    *,
    request: ChatRequest,
    db,
    wants_fixation_documents: bool,
    is_qa_mode: bool,
    no_tools_requested: bool,
    computed_data,
    effective_portfolio,
    force_max_exemption: bool,
    stream_request_id: str,
    is_portfolio_analysis: bool,
):
    if (
        request.client_id is not None
        and wants_fixation_documents
        and (not is_qa_mode)
        and (not no_tools_requested)
    ):
        return _stream_execute_tool_no_approval(
            "GENERATE_TAX_DEDUCTION_DOCUMENTS",
            {"document_type": "fixation_package"},
            computed_data=computed_data,
            client_id=request.client_id,
            db=db,
            effective_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
            is_portfolio_analysis=is_portfolio_analysis,
        )

    return None
