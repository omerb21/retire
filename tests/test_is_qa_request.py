from app.services.llm_chat.orchestration_utils import is_qa_request


def test_is_qa_request_detects_hebrew_qa() -> None:
    assert is_qa_request("אנא בצע בדיקת מערכת מקיפה (QA) ללקוח") is True


def test_is_qa_request_does_not_trigger_on_generic_pass() -> None:
    assert is_qa_request("please pass me the link") is False
