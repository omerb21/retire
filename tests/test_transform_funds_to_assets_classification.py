from app.services.llm_chat.tool_handlers.transform_funds_to_assets import (
    classify_product_type,
)


def test_classify_gemel_defaults_to_pension() -> None:
    assert (
        classify_product_type(
            product_type_str="קופת גמל", default_conversion_type="pension"
        )
        == "pension"
    )


def test_classify_investment_gemel_is_capital_asset() -> None:
    assert (
        classify_product_type(
            product_type_str="קופת גמל להשקעה", default_conversion_type="pension"
        )
        == "capital_asset"
    )


def test_classify_study_fund_is_capital_asset() -> None:
    assert (
        classify_product_type(
            product_type_str="קרן השתלמות", default_conversion_type="pension"
        )
        == "capital_asset"
    )


def test_classify_insurance_is_pension() -> None:
    assert (
        classify_product_type(
            product_type_str="ביטוח מנהלים", default_conversion_type="capital_asset"
        )
        == "pension"
    )
