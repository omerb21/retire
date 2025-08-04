from datetime import date
from abc import ABC, abstractmethod
from app.schemas.tax import TaxParameters, TaxBracket

class TaxParamsProvider(ABC):
    @abstractmethod
    def get_params(self) -> TaxParameters: ...

class InMemoryTaxParamsProvider(TaxParamsProvider):
    def __init__(self):
        # ערכים דטרמיניסטיים לטסטים
        self._params = TaxParameters(
            cpi_series={
                date(2023,1,1): 100.0,
                date(2024,1,1): 103.0,
                date(2025,1,1): 106.0,
            },
            grant_exemption_cap=60000.0,
            grant_tax_brackets=[
                TaxBracket(up_to=40000.0, rate=0.10),
                TaxBracket(up_to=None, rate=0.20),
            ],
            annuity_factor=200.0,
        )
    def get_params(self) -> TaxParameters:
        return self._params
