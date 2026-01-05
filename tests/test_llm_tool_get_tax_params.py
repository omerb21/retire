import json
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.services.llm_chat.tool_execution import execute_tool_call


def _make_db_stub() -> Session:
    db = MagicMock(spec=Session)
    query = MagicMock()
    db.query.return_value = query
    query.filter.return_value = query
    query.first.return_value = None
    return db


def test_get_tax_params_tool_execution_returns_json_payload() -> None:
    db = _make_db_stub()

    raw = execute_tool_call(
        "GET_TAX_PARAMS",
        {},
        client_id=1,
        db=db,
    )

    payload = json.loads(raw)

    assert payload.get("tool_name") == "GET_TAX_PARAMS"
    assert payload.get("success") is True

    result = payload.get("result")
    assert isinstance(result, dict)
    assert "tax_year" in result
    assert "params" in result

    assert isinstance(result.get("params"), (dict, list))

    json.dumps(payload, ensure_ascii=False)


def test_get_tax_params_tool_execution_accepts_tax_year_argument() -> None:
    db = _make_db_stub()

    raw = execute_tool_call(
        "GET_TAX_PARAMS",
        {"tax_year": 2025},
        client_id=1,
        db=db,
    )

    payload = json.loads(raw)

    assert payload.get("success") is True
    assert payload.get("tool_name") == "GET_TAX_PARAMS"

    result = payload.get("result")
    assert isinstance(result, dict)
    assert result.get("tax_year") == 2025
    assert isinstance(result.get("params"), (dict, list))
