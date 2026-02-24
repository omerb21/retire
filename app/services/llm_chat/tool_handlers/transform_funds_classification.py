def classify_product_type(
    product_type_str: str, default_conversion_type: str = "pension"
) -> str:
    """Classify product type to determine conversion destination."""
    if not product_type_str:
        return default_conversion_type

    pt = (product_type_str or "").strip().lower()

    if any(token in pt for token in ("education_fund", "klal_stud")):
        return "capital_asset"

    if any(token in pt for token in ("provident_fund", "savings_policy")):
        return "capital_asset"

    if "גמל להשקעה" in pt:
        return "capital_asset"

    if "השתלמות" in pt:
        return "capital_asset"

    if "פוליסת חיסכון" in pt and "טהור" in pt:
        return "capital_asset"

    if "ביטוח" in pt:
        return "pension"

    if "קרן פנסיה" in pt or "פנסיה" in pt:
        return "pension"

    # 'קופת גמל' can be either annuity-oriented or capital-oriented. We only classify
    # as pension when annuity intent is explicit.
    if "קופת גמל" in pt and ("לקצבה" in pt or "קצבה" in pt):
        return "pension"
    if "קופת גמל" in pt:
        return "pension"

    if "חיסכון" in pt:
        return "capital_asset"

    return default_conversion_type
