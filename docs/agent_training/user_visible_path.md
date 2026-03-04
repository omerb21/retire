# User visible default path SSOT
route: /api/v1/llm/pension-chat
router_file: app/routers/llm_chat.py
handler: pension_chat
import_path: app.services.agent_execution.execute_agent_request:execute_agent_request
source: router trace
scope: importability only (prove-callability happens in PR-5)
