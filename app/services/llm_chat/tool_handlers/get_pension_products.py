import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_get_pension_products(*, agent_tools: AgentToolsService) -> str:
    result = agent_tools.get_pension_products()
    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"
    return json.dumps(result.get("result"), ensure_ascii=False)
