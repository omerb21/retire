from enum import Enum


class AdviceDomain(str, Enum):
    COMPENSATION = "compensation"
    COMMUTATION = "commutation"
    FIXATION = "fixation"
    INVESTMENT_RISK = "investment_risk"
    TAX_OPTIMIZATION = "tax_optimization"
    UNKNOWN = "unknown"
