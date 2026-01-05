import logging

logger = logging.getLogger("app.llm_agent_tools")


class TaxParamsToolsMixin:
    def get_tax_params(self, tax_year: int | None = None) -> dict:
        from datetime import date

        from app.providers.tax_params import InMemoryTaxParamsProvider
        from app.services.llm_agent_tools.utils import _to_jsonable

        if tax_year is None:
            tax_year = date.today().year

        provider = InMemoryTaxParamsProvider()
        params = provider.get_params()

        return {
            "success": True,
            "tool_name": "GET_TAX_PARAMS",
            "result": {
                "tax_year": tax_year,
                "params": _to_jsonable(params),
                "source": "InMemoryTaxParamsProvider",
            },
            "explanation": "פרמטרי מס לשימוש בחישובי מס והצגה.",
        }
