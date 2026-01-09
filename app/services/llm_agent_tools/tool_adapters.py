import logging

from app.services.llm_agent_tools.adapters.capital_tax import calculate_capital_withdrawal_tax
from app.services.llm_agent_tools.adapters.pension_sources import (
    _build_sources_from_pension_portfolio,
    _get_pension_sources_from_portfolio,
)
from app.services.llm_agent_tools.adapters.scenario_optimizer import find_optimal_scenario_for_target
from app.services.llm_agent_tools.adapters.target_plan import build_target_pension_plan

logger = logging.getLogger("app.llm_agent_tools")


__all__ = [
    "find_optimal_scenario_for_target",
    "_get_pension_sources_from_portfolio",
    "_build_sources_from_pension_portfolio",
    "build_target_pension_plan",
    "calculate_capital_withdrawal_tax",
]
