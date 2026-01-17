from app.guards.advisor_behavior_guard import STANDARD_BLOCK_MESSAGE, enforce_behavioral_limits


def test_allow_form_id_161d_not_blocked() -> None:
    allowed, out = enforce_behavioral_limits(
        "בהקשר של קיבוע זכויות, טופס 161ד הוא חלק מהשיח המקצועי (תשובה מושגית בלבד)."
    )
    assert allowed is True
    assert out != STANDARD_BLOCK_MESSAGE


def test_percent_is_blocked() -> None:
    allowed, out = enforce_behavioral_limits("זה כולל גם 57.5% במקרה מסוים")
    assert allowed is False
    assert out == STANDARD_BLOCK_MESSAGE


def test_money_with_thousands_is_blocked() -> None:
    allowed, out = enforce_behavioral_limits("זה יוצא 34,493 ₪ במקרה מסוים")
    assert allowed is False
    assert out == STANDARD_BLOCK_MESSAGE
