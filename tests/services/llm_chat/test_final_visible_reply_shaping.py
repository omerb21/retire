from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_non_tool_finalization import (
    _shape_final_visible_reply,
)


def test_shape_final_visible_reply_strips_known_wrapper_prefix_line() -> None:
    shaped, meta = _shape_final_visible_reply(
        "תשובה מקומית לאחר הרצת כלי\nניתן לבדוק שתי אפשרויות עיקריות."
    )

    assert shaped == "ניתן לבדוק שתי אפשרויות עיקריות."
    assert meta == {
        "had_boilerplate": True,
        "line_dedup_applied": False,
    }


def test_shape_final_visible_reply_strips_known_inline_prefix_and_preserves_line() -> (
    None
):
    shaped, meta = _shape_final_visible_reply("assistant: ניתן לבדוק שתי אפשרויות")

    assert shaped == "ניתן לבדוק שתי אפשרויות"
    assert meta == {
        "had_boilerplate": True,
        "line_dedup_applied": False,
    }


def test_shape_final_visible_reply_dedups_exact_adjacent_lines_only() -> None:
    shaped, meta = _shape_final_visible_reply(
        "ניתן לבדוק שתי אפשרויות.\n"
        "ניתן לבדוק שתי אפשרויות.\n"
        "השלב הבא הוא לבדוק את המשמעות המס."
    )

    assert shaped == ("ניתן לבדוק שתי אפשרויות.\n" "השלב הבא הוא לבדוק את המשמעות המס.")
    assert meta == {
        "had_boilerplate": False,
        "line_dedup_applied": True,
    }


def test_shape_final_visible_reply_does_not_remove_similar_lines() -> None:
    raw = "ניתן לבדוק שתי אפשרויות.\nניתן לבדוק שלוש אפשרויות."

    shaped, meta = _shape_final_visible_reply(raw)

    assert shaped == raw
    assert meta == {
        "had_boilerplate": False,
        "line_dedup_applied": False,
    }


def test_shape_final_visible_reply_spacing_only_counts_as_applied() -> None:
    shaped, meta = _shape_final_visible_reply(
        "\nאפשר לבדוק קודם את הקצבה הצפויה.\n\n\nואז להחליט אם יש צורך בעדכון תכנית.\n"
    )

    assert shaped == (
        "אפשר לבדוק קודם את הקצבה הצפויה.\n\n" "ואז להחליט אם יש צורך בעדכון תכנית."
    )
    assert meta == {
        "had_boilerplate": False,
        "line_dedup_applied": False,
    }


def test_shape_final_visible_reply_skips_clean_reply() -> None:
    raw = "אפשר לבדוק קודם את הקצבה הצפויה, ואז להחליט אם יש צורך בעדכון תכנית."

    shaped, meta = _shape_final_visible_reply(raw)

    assert shaped == raw
    assert meta == {
        "had_boilerplate": False,
        "line_dedup_applied": False,
    }


def test_shape_final_visible_reply_preserves_numbers_and_facts() -> None:
    raw = "היעד שנשמר הוא 30000 נטו לגיל 76."

    shaped, meta = _shape_final_visible_reply(raw)

    assert shaped == raw
    assert "30000" in shaped
    assert "76" in shaped
    assert meta == {
        "had_boilerplate": False,
        "line_dedup_applied": False,
    }
