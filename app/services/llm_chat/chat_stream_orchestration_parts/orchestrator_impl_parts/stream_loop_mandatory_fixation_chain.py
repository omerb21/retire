from .stream_loop_forced_fixation_chain import (
    _stream_run_forced_fixation_chain_if_needed,
)


def _stream_maybe_run_mandatory_fixation_chain(
    *,
    forced_fixation_chain_done: bool,
    request,
    db,
    tool_db,
    req_id: str,
    tool_name: str,
    current_pension_portfolio,
    force_max_exemption_val,
    history_messages,
):
    if False and (
        (not forced_fixation_chain_done)
        and tool_name in {"TRANSFORM_FUNDS_TO_ASSETS", "PROCESS_TERMINATION"}
    ):
        forced_fixation_chain_done = (
            yield from _stream_run_forced_fixation_chain_if_needed(
                request=request,
                db=db,
                tool_db=tool_db,
                req_id=req_id,
                tool_name=tool_name,
                current_pension_portfolio=current_pension_portfolio,
                force_max_exemption_val=force_max_exemption_val,
                history_messages=history_messages,
            )
        )

    return forced_fixation_chain_done
