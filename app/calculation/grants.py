from app.schemas.tax import TaxParameters

def calc_grant_components(gross: float, params: TaxParameters) -> tuple[float,float,float]:
    """מחזיר (exempt, taxable, tax) לפי תקרת פטור ומדרגות פשוטות."""
    if gross < 0:
        raise ValueError("סכום מענק שלילי אינו חוקי")
    exempt = min(gross, params.grant_exemption_cap)
    taxable = max(0.0, gross - exempt)
    tax = 0.0
    remaining = taxable
    for b in params.grant_tax_brackets:
        if remaining <= 0: break
        chunk = remaining if b.up_to is None else min(remaining, b.up_to)
        tax += chunk * b.rate
        remaining -= chunk
    tax = round(tax, 2)
    return round(exempt,2), round(taxable,2), tax
