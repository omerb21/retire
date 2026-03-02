"""
LLM Agent Tools Service
שירות כלים לסוכן ה-LLM - מאפשר לסוכן להפעיל לוגיקות מערכת

כל כלי מחזיר מבנה אחיד:
{
    "success": bool,
    "tool_name": str,
    "result": dict,  # תוצאות הכלי
    "explanation": str,  # הסבר קצר לסוכן
}
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.services.llm_agent_tools import (
    CommutationToolsMixin,
    DataCompletenessToolsMixin,
    GrossWithdrawalToolsMixin,
    RetirementCashflowToolsMixin,
    TaxParamsToolsMixin,
    TaxProjectionToolsMixin,
    tool_adapters,
)
from app.services.llm_agent_tools.fixation_tools import FixationToolsMixin
from app.services.llm_agent_tools.portfolio_tools import PortfolioToolsMixin
from app.services.llm_agent_tools.scenarios_tools import ScenariosToolsMixin
from app.services.llm_agent_tools.tax_tools import TaxToolsMixin
from app.services.llm_agent_tools.utils import _to_jsonable

logger = logging.getLogger("app.llm_agent_tools")


class AgentToolsService(
    TaxToolsMixin,
    PortfolioToolsMixin,
    ScenariosToolsMixin,
    FixationToolsMixin,
    RetirementCashflowToolsMixin,
    CommutationToolsMixin,
    DataCompletenessToolsMixin,
    TaxProjectionToolsMixin,
    GrossWithdrawalToolsMixin,
    TaxParamsToolsMixin,
):
    """שירות כלים לסוכן ה-LLM"""

    def __init__(
        self,
        db: Session,
        client_id: int,
        client_object: Optional[Client] = None,
        pension_portfolio_data: Optional[List[Any]] = None,
    ):
        self.db = db
        self.client_id = client_id
        self._client: Optional[Client] = client_object
        self.pension_portfolio_data = pension_portfolio_data

    @property
    def client(self) -> Optional[Client]:
        if self._client is None:
            self._client = (
                self.db.query(Client).filter(Client.id == self.client_id).first()
            )
        return self._client

    def find_optimal_scenario_for_target(
        self,
        target_monthly_pension: float,
        min_retirement_age: Optional[int] = None,
        max_retirement_age: Optional[int] = None,
    ) -> Dict[str, Any]:
        return tool_adapters.find_optimal_scenario_for_target(
            self,
            target_monthly_pension=target_monthly_pension,
            min_retirement_age=min_retirement_age,
            max_retirement_age=max_retirement_age,
        )

    def _get_pension_sources_from_portfolio(
        self,
        pension_portfolio: List[Dict[str, Any]],
        client: Client,
        retirement_age: int,
        retirement_date: date,
        retirement_year: int,
    ) -> List[Dict[str, Any]]:
        return tool_adapters._get_pension_sources_from_portfolio(
            self,
            pension_portfolio=pension_portfolio,
            client=client,
            retirement_age=retirement_age,
            retirement_date=retirement_date,
            retirement_year=retirement_year,
        )

    def _build_sources_from_pension_portfolio(
        self,
        pension_portfolio: List[Dict[str, Any]],
        client: Client,
        retirement_age: int,
        retirement_date: date,
        retirement_year: int,
    ) -> List[Dict[str, Any]]:
        return tool_adapters._build_sources_from_pension_portfolio(
            self,
            pension_portfolio=pension_portfolio,
            client=client,
            retirement_age=retirement_age,
            retirement_date=retirement_date,
            retirement_year=retirement_year,
        )

    def build_target_pension_plan(
        self,
        target_monthly_pension: float,
        retirement_age: Optional[int] = None,
        target_is_net: bool = True,
        ignore_blocked_balances: bool = True,
    ) -> Dict[str, Any]:
        return tool_adapters.build_target_pension_plan(
            self,
            target_monthly_pension=target_monthly_pension,
            retirement_age=retirement_age,
            target_is_net=target_is_net,
            ignore_blocked_balances=ignore_blocked_balances,
        )

    def calculate_capital_withdrawal_tax(
        self,
        withdrawal_amount_gross: float,
        withdrawal_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        return tool_adapters.calculate_capital_withdrawal_tax(
            self,
            withdrawal_amount_gross=withdrawal_amount_gross,
            withdrawal_year=withdrawal_year,
        )
