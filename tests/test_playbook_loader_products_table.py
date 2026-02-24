from app.utils.playbook_loader import get_relevant_example


def test_get_relevant_example_selects_products_table_example_by_excel_keyword() -> None:
    example = get_relevant_example(
        "תעשה לי סדר בתיק לפי האקסל. אני רוצה לדעת כמה הון וכמה קצבה"
    )
    assert example is not None
    assert "## דוגמה 14" in example


def test_get_relevant_example_selects_products_table_example_by_capital_and_pension_keywords() -> (
    None
):
    example = get_relevant_example("כמה הון וכמה קצבה יש לי בתיק?")
    assert example is not None
    assert "## דוגמה 14" in example
