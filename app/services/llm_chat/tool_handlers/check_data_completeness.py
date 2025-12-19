import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_check_data_completeness(*, agent_tools: AgentToolsService) -> str:
    result = agent_tools.check_data_completeness()
    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"
    return json.dumps(result.get("result"), ensure_ascii=False)
