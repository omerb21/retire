import json
from unittest.mock import MagicMock, patch

from app.services.llm_chat.tool_handlers.monthly_pension_summary import (
    handle_monthly_pension_summary,
)


def test_monthly_pension_summary_tool_returns_emission_ready_payload_and_marker():
    computed = {"foo": "bar"}

    with patch(
        "app.services.pension_chat_compute.compute_monthly_pension_summary",
        return_value=computed,
    ):
        raw = handle_monthly_pension_summary(args={}, client_id=123, db=MagicMock())

    parsed = json.loads(raw)

    assert parsed["reply"] == "Monthly pension summary computed. See computed_data for details."
    assert parsed["computed_data"] == computed

    marker = parsed["computed_data_marker"]
    assert marker.startswith("###COMPUTED_DATA###")
    assert marker.endswith("###END_COMPUTED_DATA###\n")

    inner = marker[len("###COMPUTED_DATA###") : -len("###END_COMPUTED_DATA###\n")]
    inner_obj = json.loads(inner)
    assert inner_obj == {"type": "computed_data", "data": computed}
