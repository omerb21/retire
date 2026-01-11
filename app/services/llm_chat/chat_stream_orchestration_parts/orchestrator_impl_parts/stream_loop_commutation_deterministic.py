from datetime import date

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatRequest

from ..chat_helpers import (
    _digits_only,
    _extract_commutation_account_number,
    _item_to_dict,
    _user_wants_full_balance,
)
from ..stream_commutation_generators import (
    generate_commutation_missing,
    generate_commutation_need_amount,
    generate_commutation_need_amount_existing,
)
from ..stream_streaming_helpers import _stream_request_approval


def _maybe_handle_commutation_deterministic(
    *,
    commutation_intent,
    request: ChatRequest,
    is_doc_request,
    is_qa_mode,
    original_user_msg,
    db: Session,
    effective_portfolio,
    computed_data,
) -> StreamingResponse | None:
    # Early deterministic handling for pension commutation requests.
    # Only run this path when the user provided a specific account identifier.
    # If the request is vague (no account number), fall back to the LLM flow.
    if commutation_intent and request.client_id is not None and (not is_doc_request) and (not is_qa_mode):
        account_number = _extract_commutation_account_number(original_user_msg)
        if account_number:
            fund = None
            try:
                from app.models.pension_fund import PensionFund

                fund = (
                    db.query(PensionFund)
                    .filter(PensionFund.client_id == request.client_id)
                    .filter(PensionFund.deduction_file == account_number)
                    .first()
                )
            except Exception:
                fund = None

            if fund is not None:
                # Deterministic execution requires an explicit amount (or 'כל היתרה').
                comm_amount = None
                try:
                    if _user_wants_full_balance(original_user_msg):
                        comm_amount = float(getattr(fund, "balance", 0) or 0)
                except Exception:
                    comm_amount = None

                if not comm_amount or comm_amount <= 0:
                    return StreamingResponse(
                        generate_commutation_need_amount_existing(computed_data=computed_data),
                        media_type="text/plain; charset=utf-8",
                    )

                tax_type = "exempt" if "פטור" in (original_user_msg or "") else "taxable"
                exec_args = {
                    "pension_fund_id": int(getattr(fund, "id")),
                    "commutation_amount": float(comm_amount),
                    "commutation_date": date.today().isoformat(),
                    "commutation_type": tax_type,
                    "confirmed": True,
                }
                return _stream_request_approval(
                    "EXECUTE_PENSION_COMMUTATION",
                    exec_args,
                    reason="נדרש אישור לפני ביצוע היוון קצבה במערכת.",
                    computed_data=computed_data,
                    client_id=request.client_id,
                    db=db,
                )

            target_digits = _digits_only(account_number)
            matched: dict | None = None
            for acc in (effective_portfolio or []):
                data = _item_to_dict(acc)
                acc_num = str(data.get("מספר_חשבון") or data.get("account_number") or "").strip()
                if not acc_num:
                    continue
                if acc_num == account_number:
                    matched = data
                    break
                if target_digits and _digits_only(acc_num) == target_digits:
                    matched = data
                    break

            if matched is not None:
                fund = None

            if fund is None:
                return StreamingResponse(
                    generate_commutation_missing(computed_data=computed_data, account_number=account_number),
                    media_type="text/plain; charset=utf-8",
                )

            comm_amount = None
            try:
                if _user_wants_full_balance(original_user_msg):
                    comm_amount = float(getattr(fund, "balance", 0) or 0)
            except Exception:
                comm_amount = None
            if not comm_amount or comm_amount <= 0:
                return StreamingResponse(
                    generate_commutation_need_amount(computed_data=computed_data),
                    media_type="text/plain; charset=utf-8",
                )

            tax_type = "exempt" if "פטור" in (original_user_msg or "") else "taxable"
            exec_args = {
                "pension_fund_id": int(getattr(fund, "id")),
                "commutation_amount": float(comm_amount),
                "commutation_date": date.today().isoformat(),
                "commutation_type": tax_type,
                "confirmed": True,
            }
            return _stream_request_approval(
                "EXECUTE_PENSION_COMMUTATION",
                exec_args,
                reason="נדרש אישור לפני ביצוע היוון קצבה במערכת.",
                computed_data=computed_data,
                client_id=request.client_id,
                db=db,
            )

    return None
