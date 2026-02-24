from sqlalchemy.orm import Session

from app.models.client import Client
from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.orchestration_utils import (
    normalize_retirement_date_if_jan1_placeholder,
)


def _maybe_normalize_cashflow_retirement_date(
    *,
    tool_name,
    tool_args,
    request: ChatRequest,
    db: Session,
    original_user_msg,
) -> None:
    if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        date_str = tool_args.get("retirement_date")
        if (
            isinstance(date_str, str)
            and date_str.strip()
            and request.client_id is not None
        ):
            client = db.query(Client).filter(Client.id == request.client_id).first()
            birth_date = getattr(client, "birth_date", None) if client else None
            if birth_date is not None:
                before_val = date_str.strip()
                tool_args["retirement_date"] = (
                    normalize_retirement_date_if_jan1_placeholder(
                        retirement_date=before_val,
                        birth_date=birth_date,
                        user_message=original_user_msg,
                    )
                )
                after_val = tool_args["retirement_date"]
                if before_val != after_val:
                    try:
                        from app.services.agent_trace_logger import log_trace_event

                        log_trace_event(
                            event_type="args_normalized",
                            payload={
                                "normalizer_name": "normalize_retirement_date_if_jan1_placeholder",
                                "before": {"retirement_date": before_val},
                                "after": {"retirement_date": after_val},
                            },
                            client_id=request.client_id,
                        )
                    except Exception:
                        pass
