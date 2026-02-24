from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session


def handle_monthly_pension_summary(*, args: dict, client_id: int, db: Session) -> str:
    _ = args

    from app.services.pension_chat_compute import compute_monthly_pension_summary

    computed_data = compute_monthly_pension_summary(db, int(client_id), date.today())

    reply = "Monthly pension summary computed. See computed_data for details."
    if not isinstance(reply, str) or not reply.strip():
        reply = "Unable to produce monthly pension summary from system."

    computed_json = json.dumps(
        {"type": "computed_data", "data": computed_data},
        ensure_ascii=False,
    )
    computed_data_marker = (
        f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
    )

    return json.dumps(
        {
            "reply": reply,
            "computed_data": computed_data,
            "computed_data_marker": computed_data_marker,
        },
        ensure_ascii=False,
    )
