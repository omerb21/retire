def _maybe_handle_early_cutoffs(
    *,
    request,
    db,
    original_user_msg: str,
    maybe_handle_conceptual_no_execute_hard_stop,
    maybe_handle_undo_snapshot_approval_request,
 ):
    conceptual_no_execute_response = maybe_handle_conceptual_no_execute_hard_stop(
        request=request,
        original_user_msg=original_user_msg,
    )
    if conceptual_no_execute_response is not None:
        return conceptual_no_execute_response

    undo_snapshot_response = maybe_handle_undo_snapshot_approval_request(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
    )
    if undo_snapshot_response is not None:
        return undo_snapshot_response

    return None
