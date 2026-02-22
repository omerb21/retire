# AGENT_INVENTORY

## 1. Endpoints
- GET / (non-stream) -> handler: read_root() -> file: app\main.py
- GET /api/v1/_edge_probe (non-stream) -> handler: edge_probe() -> file: app\main.py
- GET /api/v1/_ping (non-stream) -> handler: ping_v1() -> file: app\main.py
- GET /api/v1/agent-eyes/traces (non-stream) -> handler: list_traces() -> file: app\routers\agent_eyes_debug.py
- DELETE /api/v1/agent-eyes/traces/{trace_id} (non-stream) -> handler: delete_trace() -> file: app\routers\agent_eyes_debug.py
- GET /api/v1/agent-eyes/traces/{trace_id} (non-stream) -> handler: get_trace_events() -> file: app\routers\agent_eyes_debug.py
- POST /api/v1/annuity-coefficient/calculate (non-stream) -> handler: calculate_annuity_coefficient() -> file: app\routers\annuity_coefficient.py
- GET /api/v1/annuity-coefficient/tables/status (non-stream) -> handler: get_tables_status() -> file: app\routers\annuity_coefficient.py
- POST /api/v1/calculation/run (non-stream) -> handler: run_calculation() -> file: app\routers\calculation.py
- GET /api/v1/clients (non-stream) -> handler: list_clients() -> file: app\routers\clients.py
- POST /api/v1/clients (non-stream) -> handler: create_client() -> file: app\routers\clients.py
- DELETE /api/v1/clients/{client_id} (non-stream) -> handler: delete_client() -> file: app\routers\clients.py
- GET /api/v1/clients/{client_id} (non-stream) -> handler: get_client() -> file: app\routers\clients.py
- PATCH /api/v1/clients/{client_id} (non-stream) -> handler: patch_client() -> file: app\routers\clients.py
- PUT /api/v1/clients/{client_id} (non-stream) -> handler: update_client() -> file: app\routers\clients.py
- GET /api/v1/clients/{client_id}/additional-incomes (non-stream) -> handler: get_additional_incomes() -> file: app\routers\additional_income.py
- POST /api/v1/clients/{client_id}/additional-incomes (non-stream) -> handler: create_additional_income() -> file: app\routers\additional_income.py
- GET /api/v1/clients/{client_id}/additional-incomes/ (non-stream) -> handler: get_additional_incomes() -> file: app\routers\additional_income.py
- POST /api/v1/clients/{client_id}/additional-incomes/ (non-stream) -> handler: create_additional_income() -> file: app\routers\additional_income.py
- DELETE /api/v1/clients/{client_id}/additional-incomes/{income_id} (non-stream) -> handler: delete_additional_income() -> file: app\routers\additional_income.py
- GET /api/v1/clients/{client_id}/additional-incomes/{income_id} (non-stream) -> handler: get_additional_income() -> file: app\routers\additional_income.py
- PUT /api/v1/clients/{client_id}/additional-incomes/{income_id} (non-stream) -> handler: update_additional_income() -> file: app\routers\additional_income.py
- GET /api/v1/clients/{client_id}/capital-assets (non-stream) -> handler: get_capital_assets() -> file: app\routers\capital_asset.py
- POST /api/v1/clients/{client_id}/capital-assets (non-stream) -> handler: create_capital_asset() -> file: app\routers\capital_asset.py
- GET /api/v1/clients/{client_id}/capital-assets/ (non-stream) -> handler: get_capital_assets() -> file: app\routers\capital_asset.py
- POST /api/v1/clients/{client_id}/capital-assets/ (non-stream) -> handler: create_capital_asset() -> file: app\routers\capital_asset.py
- DELETE /api/v1/clients/{client_id}/capital-assets/{asset_id} (non-stream) -> handler: delete_capital_asset() -> file: app\routers\capital_asset.py
- GET /api/v1/clients/{client_id}/capital-assets/{asset_id} (non-stream) -> handler: get_capital_asset() -> file: app\routers\capital_asset.py
- PUT /api/v1/clients/{client_id}/capital-assets/{asset_id} (non-stream) -> handler: update_capital_asset() -> file: app\routers\capital_asset.py
- GET /api/v1/clients/{client_id}/case/detect (non-stream) -> handler: detect_client_case_get() -> file: app\routers\case_detection.py
- POST /api/v1/clients/{client_id}/case/detect (non-stream) -> handler: detect_case_post() -> file: app\routers\case_detection.py
- POST /api/v1/clients/{client_id}/cashflow/integrate-all (non-stream) -> handler: integrate_all_with_cashflow() -> file: app\routers\income_integration.py
- POST /api/v1/clients/{client_id}/cashflow/integrate-assets (non-stream) -> handler: integrate_assets_with_cashflow() -> file: app\routers\income_integration.py
- POST /api/v1/clients/{client_id}/cashflow/integrate-incomes (non-stream) -> handler: integrate_incomes_with_cashflow() -> file: app\routers\income_integration.py
- GET /api/v1/clients/{client_id}/current-employer (non-stream) -> handler: get_current_employer() -> file: app\routers\employment\employer.py
- GET /api/v1/clients/{client_id}/current-employer (non-stream) -> handler: get_current_employer_for_client() -> file: app\routers\clients.py
- POST /api/v1/clients/{client_id}/current-employer (non-stream) -> handler: create_current_employer() -> file: app\routers\clients.py
- POST /api/v1/clients/{client_id}/current-employer (non-stream) -> handler: create_or_update_current_employer() -> file: app\routers\employment\employer.py
- POST /api/v1/clients/{client_id}/current-employer/grants (non-stream) -> handler: add_grant_to_current_employer() -> file: app\routers\employment\grants.py
- POST /api/v1/clients/{client_id}/current-employer/termination (non-stream) -> handler: process_termination_decision() -> file: app\routers\employment\termination.py
- DELETE /api/v1/clients/{client_id}/current-employer/{employer_id:int} (non-stream) -> handler: delete_current_employer() -> file: app\routers\clients.py
- GET /api/v1/clients/{client_id}/current-employer/{employer_id:int} (non-stream) -> handler: get_current_employer() -> file: app\routers\clients.py
- PUT /api/v1/clients/{client_id}/current-employer/{employer_id:int} (non-stream) -> handler: update_current_employer() -> file: app\routers\clients.py
- DELETE /api/v1/clients/{client_id}/delete-termination (non-stream) -> handler: delete_termination_decision() -> file: app\routers\employment\termination.py
- POST /api/v1/clients/{client_id}/employment/current (non-stream) -> handler: set_current_employment() -> file: app\routers\employment\employer.py
- POST /api/v1/clients/{client_id}/employment/termination/confirm (non-stream) -> handler: confirm_termination() -> file: app\routers\employment_api.py
- PATCH /api/v1/clients/{client_id}/employment/termination/plan (non-stream) -> handler: plan_termination() -> file: app\routers\employment_api.py
- GET /api/v1/clients/{client_id}/fixation (non-stream) -> handler: get_client_fixation() -> file: app\routers\clients.py
- GET /api/v1/clients/{client_id}/fixation (non-stream) -> handler: get_fixation() -> file: app\routers\fixation.py
- GET /api/v1/clients/{client_id}/grants (non-stream) -> handler: get_client_grants() -> file: app\routers\grant.py
- POST /api/v1/clients/{client_id}/grants (non-stream) -> handler: create_grant() -> file: app\routers\grant.py
- DELETE /api/v1/clients/{client_id}/grants/{grant_id} (non-stream) -> handler: delete_grant() -> file: app\routers\grant.py
- GET /api/v1/clients/{client_id}/grants/{grant_id} (non-stream) -> handler: get_grant() -> file: app\routers\grant.py
- GET /api/v1/clients/{client_id}/pension-funds (non-stream) -> handler: get_client_pension_funds() -> file: app\routers\pension_fund.py
- POST /api/v1/clients/{client_id}/pension-funds (non-stream) -> handler: create_pension_fund() -> file: app\routers\pension_fund.py
- GET /api/v1/clients/{client_id}/pension-funds/ (non-stream) -> handler: get_client_pension_funds() -> file: app\routers\pension_fund.py
- POST /api/v1/clients/{client_id}/pension-funds/ (non-stream) -> handler: create_pension_fund() -> file: app\routers\pension_fund.py
- POST /api/v1/clients/{client_id}/pension-funds/compute-all (non-stream) -> handler: compute_all_client_pension_funds() -> file: app\routers\pension_fund.py
- POST /api/v1/clients/{client_id}/pension-funds/compute-all/ (non-stream) -> handler: compute_all_client_pension_funds() -> file: app\routers\pension_fund.py
- DELETE /api/v1/clients/{client_id}/pension-funds/{fund_id} (non-stream) -> handler: delete_client_pension_fund() -> file: app\routers\pension_fund.py
- DELETE /api/v1/clients/{client_id}/pension-funds/{fund_id}/ (non-stream) -> handler: delete_client_pension_fund() -> file: app\routers\pension_fund.py
- POST /api/v1/clients/{client_id}/pension-funds/{fund_id}/compute (non-stream) -> handler: compute_client_pension_fund() -> file: app\routers\pension_fund.py
- POST /api/v1/clients/{client_id}/pension-funds/{fund_id}/compute/ (non-stream) -> handler: compute_client_pension_fund() -> file: app\routers\pension_fund.py
- GET /api/v1/clients/{client_id}/pension-portfolio/ (non-stream) -> handler: get_pension_portfolio() -> file: app\routers\pension_portfolio.py
- POST /api/v1/clients/{client_id}/pension-portfolio/convert (non-stream) -> handler: convert_pension_accounts() -> file: app\routers\pension_portfolio.py
- POST /api/v1/clients/{client_id}/pension-portfolio/process-directory (non-stream) -> handler: process_pension_directory() -> file: app\routers\pension_portfolio.py
- POST /api/v1/clients/{client_id}/pension-portfolio/process-xml (non-stream) -> handler: process_pension_xml_files() -> file: app\routers\pension_portfolio.py
- POST /api/v1/clients/{client_id}/pension-portfolio/restore (non-stream) -> handler: restore_pension_amounts() -> file: app\routers\pension_portfolio.py
- POST /api/v1/clients/{client_id}/pension-portfolio/save (non-stream) -> handler: save_pension_portfolio() -> file: app\routers\pension_portfolio.py
- POST /api/v1/clients/{client_id}/reports/generate (non-stream) -> handler: generate_report() -> file: app\routers\reports.py
- POST /api/v1/clients/{client_id}/reports/pdf (non-stream) -> handler: generate_simple_pdf_report() -> file: app\routers\reports.py
- GET /api/v1/clients/{client_id}/reports/preview (non-stream) -> handler: preview_report_data() -> file: app\routers\reports.py
- GET /api/v1/clients/{client_id}/retirement-scenarios (non-stream) -> handler: get_saved_retirement_scenarios() -> file: app\routers\scenarios\retirement\router.py
- POST /api/v1/clients/{client_id}/retirement-scenarios (non-stream) -> handler: generate_retirement_scenarios() -> file: app\routers\scenarios\retirement\router.py
- POST /api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/execute (non-stream) -> handler: execute_retirement_scenario() -> file: app\routers\scenarios\retirement\router.py
- GET /api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/preview (non-stream) -> handler: preview_retirement_scenario_route() -> file: app\routers\scenarios\retirement\router.py
- GET /api/v1/clients/{client_id}/scenarios (non-stream) -> handler: get_client_scenarios() -> file: app\routers\scenarios\router.py
- POST /api/v1/clients/{client_id}/scenarios (non-stream) -> handler: create_scenario() -> file: app\routers\scenarios\router.py
- POST /api/v1/clients/{client_id}/scenarios/compare (non-stream) -> handler: compare_scenarios_endpoint() -> file: app\routers\scenario_compare.py
- DELETE /api/v1/clients/{client_id}/scenarios/{scenario_id} (non-stream) -> handler: delete_scenario() -> file: app\routers\scenarios\router.py
- GET /api/v1/clients/{client_id}/scenarios/{scenario_id} (non-stream) -> handler: get_scenario() -> file: app\routers\scenarios\router.py
- PUT /api/v1/clients/{client_id}/scenarios/{scenario_id} (non-stream) -> handler: update_scenario() -> file: app\routers\scenarios\router.py
- GET /api/v1/clients/{client_id}/scenarios/{scenario_id}/cashflow (non-stream) -> handler: get_cashflow() -> file: app\routers\scenarios\router.py
- GET /api/v1/clients/{client_id}/snapshot/info (non-stream) -> handler: get_snapshot_info() -> file: app\routers\snapshot.py
- POST /api/v1/clients/{client_id}/snapshot/restore (non-stream) -> handler: restore_system_snapshot() -> file: app\routers\snapshot.py
- POST /api/v1/clients/{client_id}/snapshot/save (non-stream) -> handler: save_system_snapshot() -> file: app\routers\snapshot.py
- POST /api/v1/current-employer/calculate-severance (non-stream) -> handler: calculate_severance() -> file: app\routers\employment\severance.py
- GET /api/v1/debug/current-employer/{client_id} (non-stream) -> handler: debug_current_employer() -> file: app\routers\debug_current_employer.py
- GET /api/v1/debug/latest-snapshot/{client_id} (non-stream) -> handler: debug_latest_snapshot() -> file: app\routers\debug_current_employer.py
- POST /api/v1/debug/trace-fixtures/run (non-stream) -> handler: run_trace_fixture() -> file: app\routers\agent_trace_debug.py
- GET /api/v1/debug/traces (non-stream) -> handler: list_traces() -> file: app\routers\agent_trace_debug.py
- GET /api/v1/debug/traces/{trace_id} (non-stream) -> handler: get_trace_events() -> file: app\routers\agent_trace_debug.py
- GET /api/v1/debug/traces/{trace_id}/events/{event_id}/payload-raw (non-stream) -> handler: get_trace_event_payload_raw() -> file: app\routers\agent_trace_debug.py
- GET /api/v1/documents/{doc_id}/download (non-stream) -> handler: download_document_by_id() -> file: app\routers\reports.py
- POST /api/v1/fixation/{client_id}/161d (non-stream) -> handler: fixation_161d_stub() -> file: app\routers\fixation.py
- POST /api/v1/fixation/{client_id}/commutations-appendix (non-stream) -> handler: commutations_appendix() -> file: app\routers\fixation.py
- POST /api/v1/fixation/{client_id}/compute (non-stream) -> handler: compute_fixation() -> file: app\routers\fixation.py
- POST /api/v1/fixation/{client_id}/grants-appendix (non-stream) -> handler: grants_appendix() -> file: app\routers\fixation.py
- GET /api/v1/fixation/{client_id}/package (non-stream) -> handler: package() -> file: app\routers\fixation.py
- POST /api/v1/fixation/{client_id}/package (non-stream) -> handler: package() -> file: app\routers\fixation.py
- GET /api/v1/health (non-stream) -> handler: health_check_v1() -> file: app\main.py
- POST /api/v1/indexation/calculate-exact (non-stream) -> handler: calculate_exact_grant_value() -> file: app\routers\indexation.py
- GET /api/v1/indexation/indexation-factor (non-stream) -> handler: get_indexation_factor() -> file: app\routers\indexation.py
- GET /api/v1/indexation/work-ratio (non-stream) -> handler: get_work_ratio() -> file: app\routers\indexation.py
- POST /api/v1/llm/pension-chat (non-stream) -> handler: pension_chat() -> file: app\routers\llm_chat.py
- POST /api/v1/llm/pension-chat-stream (stream) -> handler: pension_chat_stream() -> file: app\routers\llm_chat.py
- POST /api/v1/llm/provider (non-stream) -> handler: update_llm_provider() -> file: app\routers\llm_chat.py
- GET /api/v1/llm/status (non-stream) -> handler: get_llm_status() -> file: app\routers\llm_chat.py
- DELETE /api/v1/pension-funds/{fund_id} (non-stream) -> handler: delete_pension_fund() -> file: app\routers\pension_fund.py
- GET /api/v1/pension-funds/{fund_id} (non-stream) -> handler: get_pension_fund() -> file: app\routers\pension_fund.py
- PUT /api/v1/pension-funds/{fund_id} (non-stream) -> handler: update_pension_fund() -> file: app\routers\pension_fund.py
- POST /api/v1/pension-funds/{fund_id}/compute (non-stream) -> handler: compute_pension_fund() -> file: app\routers\pension_fund.py
- DELETE /api/v1/public-chat/sessions/{session_key}/history (non-stream) -> handler: clear_public_chat_history() -> file: app\routers\public_chat.py
- GET /api/v1/public-chat/sessions/{session_key}/history (non-stream) -> handler: get_public_chat_history() -> file: app\routers\public_chat.py
- POST /api/v1/public-chat/sessions/{session_key}/messages (non-stream) -> handler: send_public_chat_message() -> file: app\routers\public_chat.py
- GET /api/v1/public-chat/sessions/{session_key}/status (non-stream) -> handler: get_public_chat_status() -> file: app\routers\public_chat.py
- POST /api/v1/public-chat/start (non-stream) -> handler: start_public_chat() -> file: app\routers\public_chat.py
- POST /api/v1/public-chat/topup (non-stream) -> handler: topup_public_chat() -> file: app\routers\public_chat.py
- GET /api/v1/reports/{report_id}/download (non-stream) -> handler: download_report_by_id() -> file: app\routers\reports.py
- POST /api/v1/retirement-age/calculate (non-stream) -> handler: calculate_retirement_age_endpoint() -> file: app\routers\retirement_age.py
- POST /api/v1/retirement-age/calculate-simple (non-stream) -> handler: calculate_retirement_age_simple_endpoint() -> file: app\routers\retirement_age.py
- GET /api/v1/retirement-age/settings (non-stream) -> handler: get_retirement_age_settings() -> file: app\routers\retirement_age.py
- POST /api/v1/retirement-age/settings (non-stream) -> handler: update_retirement_age_settings() -> file: app\routers\retirement_age.py
- POST /api/v1/rights-fixation/calculate (non-stream) -> handler: calculate_rights_fixation() -> file: app\routers\rights_fixation.py
- GET /api/v1/rights-fixation/caps/{year} (non-stream) -> handler: get_caps_for_year() -> file: app\routers\rights_fixation.py
- DELETE /api/v1/rights-fixation/client/{client_id} (non-stream) -> handler: delete_fixation() -> file: app\routers\rights_fixation.py
- GET /api/v1/rights-fixation/client/{client_id} (non-stream) -> handler: get_saved_fixation() -> file: app\routers\rights_fixation.py
- POST /api/v1/rights-fixation/eligibility-date (non-stream) -> handler: calculate_eligibility_date() -> file: app\routers\rights_fixation.py
- POST /api/v1/rights-fixation/exemption/summary (non-stream) -> handler: calculate_exemption_summary() -> file: app\routers\rights_fixation.py
- POST /api/v1/rights-fixation/grant/effect (non-stream) -> handler: calculate_grant_effect() -> file: app\routers\rights_fixation.py
- POST /api/v1/rights-fixation/save (non-stream) -> handler: save_rights_fixation() -> file: app\routers\rights_fixation.py
- GET /api/v1/rights-fixation/test (non-stream) -> handler: test_cbs_api() -> file: app\routers\rights_fixation.py
- POST /api/v1/scenarios/{scenario_id}/cashflow/generate (non-stream) -> handler: generate_cashflow_endpoint() -> file: app\routers\cashflow_generation.py
- POST /api/v1/scenarios/{scenario_id}/report/pdf (stream) -> handler: generate_pdf_report() -> file: app\routers\report_generation.py
- GET /api/v1/system/health (non-stream) -> handler: get_system_health() -> file: app\routers\system_health.py
- POST /api/v1/system/health/fix (non-stream) -> handler: auto_fix_system() -> file: app\routers\system_health.py
- GET /api/v1/system/health/report (non-stream) -> handler: get_validation_report() -> file: app\routers\system_health.py
- GET /api/v1/system/health/tables/{table_name} (non-stream) -> handler: get_table_info() -> file: app\routers\system_health.py
- GET /api/v1/tax-data/cpi (non-stream) -> handler: get_cpi_data() -> file: app\routers\tax_data.py
- GET /api/v1/tax-data/indexation-factor (non-stream) -> handler: get_indexation_factor() -> file: app\routers\tax_data.py
- GET /api/v1/tax-data/severance-cap (non-stream) -> handler: get_severance_cap() -> file: app\routers\tax_data.py
- GET /api/v1/tax-data/severance-caps (non-stream) -> handler: get_severance_caps() -> file: app\routers\tax_data.py
- POST /api/v1/tax-data/severance-caps (non-stream) -> handler: update_severance_caps() -> file: app\routers\tax_data.py
- GET /api/v1/tax-data/severance-exemption (non-stream) -> handler: calculate_severance_exemption() -> file: app\routers\tax_data.py
- GET /api/v1/tax-data/summary (non-stream) -> handler: get_tax_data_summary() -> file: app\routers\tax_data.py
- GET /api/v1/tax-data/tax-brackets (non-stream) -> handler: get_tax_brackets() -> file: app\routers\tax_data.py
- POST /api/v1/tax-data/update-cache (non-stream) -> handler: update_tax_data_cache() -> file: app\routers\tax_data.py
- POST /api/v1/tax/analyze (non-stream) -> handler: analyze_tax_comprehensive() -> file: app\routers\tax_calculation.py
- GET /api/v1/tax/brackets/{year} (non-stream) -> handler: get_tax_brackets() -> file: app\routers\tax_calculation.py
- POST /api/v1/tax/calculate (non-stream) -> handler: calculate_tax() -> file: app\routers\tax_calculation.py
- GET /api/v1/tax/credits/{year} (non-stream) -> handler: get_available_tax_credits() -> file: app\routers\tax_calculation.py
- GET /api/v1/tax/health (non-stream) -> handler: health_check() -> file: app\routers\tax_calculation.py
- POST /api/v1/tax/simulate (non-stream) -> handler: simulate_tax_scenarios() -> file: app\routers\tax_calculation.py
- GET /api/v1/version (non-stream) -> handler: version_v1() -> file: app\main.py
- GET /clients/{client_id}/current-employer (non-stream) -> handler: get_current_employer() -> file: app\routers\employment\employer.py
- POST /clients/{client_id}/current-employer (non-stream) -> handler: create_or_update_current_employer() -> file: app\routers\employment\employer.py
- POST /clients/{client_id}/current-employer/grants (non-stream) -> handler: add_grant_to_current_employer() -> file: app\routers\employment\grants.py
- POST /clients/{client_id}/current-employer/termination (non-stream) -> handler: process_termination_decision() -> file: app\routers\employment\termination.py
- DELETE /clients/{client_id}/delete-termination (non-stream) -> handler: delete_termination_decision() -> file: app\routers\employment\termination.py
- POST /clients/{client_id}/employment/current (non-stream) -> handler: set_current_employment() -> file: app\routers\employment\employer.py
- POST /current-employer/calculate-severance (non-stream) -> handler: calculate_severance() -> file: app\routers\employment\severance.py
- GET /debug/agent-trace (non-stream) -> handler: agent_trace_ui() -> file: app\main.py
- GET /health (non-stream) -> handler: health_check() -> file: app\main.py
- GET /ui (non-stream) -> handler: ui_redirect() -> file: app\main.py
- GET /{full_path:path} (non-stream) -> handler: spa_fallback() -> file: app\main.py

## 2. Tools
- Tool dispatch: `app/services/llm_chat/tool_execution.py:execute_tool_call`
- Tool guard + contract wrapper: `app/services/agent_execution/tool_executor.py:execute_with_guard`

- BUILD_TARGET_PENSION_PLAN
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי לתכנון מתווה משיכה אופטימלי מכל המקורות להשגת יעד קצבה חודשי נטו.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "target_monthly_pension": {
      "type": "integer",
      "description": "יעד הקצבה החודשי המבוקש בשקלים (למשל: 20000)"
    },
    "target_is_net": {
      "type": "boolean",
      "description": "האם היעד שניתן הוא נטו (אחרי מס הכנסה). true=נטו, false=ברוטו. אם המשתמש כתב במפורש 'נטו' חובה לשלוח true."
    },
    "retirement_age": {
      "type": "integer",
      "description": "אופציונלי: גיל פרישה לחישוב (50-80). אם לא סופק, הכלי ישתמש בגיל חוקי/נוכחי לפי הלקוח."
    }
  },
  "required": [
    "target_monthly_pension"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CALCULATE_CAPITAL_WITHDRAWAL_TAX
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי לחישוב מס על משיכת כספי הון (קופת גמל, קרן השתלמות, תגמולים נזילים). השתמש בכלי זה כאשר הלקוח שואל 'כמה מס אשלם אם אמשוך X שקל מהקופה', 'משיכה מקופת גמל', 'משיכה מקרן השתלמות', 'כמה נשאר לי נטו אחרי משיכה'. דוגמה: ###TOOL_CALL### {"name": "CALCULATE_CAPITAL_WITHDRAWAL_TAX", "arguments": {"withdrawal_amount_gross": 100000, "withdrawal_year": 2025}}
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "withdrawal_amount_gross": {
      "type": "number",
      "description": "סכום המשיכה ברוטו מכספי ההון."
    },
    "withdrawal_year": {
      "type": "integer",
      "description": "שנת המשיכה המתוכננת (לקביעת מדרגות המס). ברירת מחדל: 2025."
    }
  },
  "required": [
    "withdrawal_amount_gross"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CALCULATE_FIXATION_OF_RIGHTS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 📋 כלי תפעול לחישוב קיבוע זכויות (פטור על קצבה). מבצע את החישוב המלא של הפטור המגיע ללקוח על בסיס המענקים הפטורים שקיבל בעבר. טריגרים: 'חשב קיבוע זכויות', 'כמה פטור מגיע לי', 'חישוב פטור על קצבה'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "include_current_employer": {
      "type": "boolean",
      "description": "האם לכלול את המעסיק הנוכחי בחישוב. ברירת מחדל: false."
    },
    "save_result": {
      "type": "boolean",
      "description": "האם לשמור את תוצאת החישוב במערכת. ברירת מחדל: true."
    }
  },
  "required": []
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CALCULATE_PENSION_COMMUTATION
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי לחישוב היוון קצבה - המרת חלק מהקצבה החודשית לסכום חד-פעמי (Lump Sum). השתמש בכלי זה כאשר הלקוח שואל 'כמה כסף אקבל אם אוותר על X שקל מהקצבה', 'היוון קצבה', 'לקבל סכום חד-פעמי במקום קצבה'. דוגמה: ###TOOL_CALL### {"name": "CALCULATE_PENSION_COMMUTATION", "arguments": {"target_monthly_pension_reduction": 2000, "retirement_date": "2028-01-01"}}
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "target_monthly_pension_reduction": {
      "type": "number",
      "description": "הסכום החודשי שהלקוח מוכן להפחית מהקצבה העתידית (ברוטו) בתמורה לסכום חד-פעמי."
    },
    "retirement_date": {
      "type": "string",
      "description": "תאריך פרישה בפורמט YYYY-MM-DD."
    }
  },
  "required": [
    "target_monthly_pension_reduction",
    "retirement_date"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CALCULATE_TAX_EXEMPT_PENSION
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: Calculates the tax-exempt monthly pension benefit (קיבוע זכויות), including a simulation of how the client's current severance pay exemption impacts the final exempt pension.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "current_tax_exempt_grant_amount": {
      "type": "integer",
      "description": "The amount of tax-exempt grant (severance) the client considers taking now."
    }
  },
  "required": [
    "current_tax_exempt_grant_amount"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CALCULATE_TAX_SPREAD_BENEFIT
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי לחישוב הטבת המס בפריסה על מספר שנים. משווה בין משיכה מיידית (מס מלא) לבין פריסת מס. השתמש בכלי זה לאחר CALCULATE_CAPITAL_WITHDRAWAL_TAX כדי להציג ללקוח את האפשרות לחסוך במס באמצעות פריסה. דוגמה: ###TOOL_CALL### {"name": "CALCULATE_TAX_SPREAD_BENEFIT", "arguments": {"gross_amount": 735000, "spread_years": 6}}
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "gross_amount": {
      "type": "number",
      "description": "סכום ברוטו חייב במס (החלק החייב של הפיצויים)."
    },
    "spread_years": {
      "type": "integer",
      "description": "מספר שנות פריסה (1-6). מקסימום 6 שנים לפי החוק."
    }
  },
  "required": [
    "gross_amount",
    "spread_years"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CHECK_DATA_COMPLETENESS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: Checks whether the client has all required data for retirement planning (portfolio, scenarios, fixation results, employer details, and missing fields).
  - inputs:
    ```json
{
  "type": "object",
  "properties": {},
  "required": []
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CREATE_ADDITIONAL_INCOME
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 💰 כלי תפעול ליצירת הכנסה נוספת (שכירות, דיבידנדים, פנסיה מחו"ל וכו'). השתמש בכלי זה כאשר הלקוח מדווח על הכנסות נוספות מעבר לקצבה. טריגרים: 'יש לי הכנסה משכירות', 'מקבל דיבידנדים', 'הכנסה נוספת', 'פנסיה מחו"ל'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "source_type": {
      "type": "string",
      "enum": [
        "rental",
        "dividends",
        "interest",
        "foreign_pension",
        "social_security",
        "other"
      ],
      "description": "סוג מקור ההכנסה: rental (שכירות), dividends (דיבידנדים), interest (ריבית), foreign_pension (פנסיה מחו\"ל), social_security (ביטוח לאומי), other (אחר)."
    },
    "amount": {
      "type": "number",
      "description": "סכום ההכנסה."
    },
    "frequency": {
      "type": "string",
      "enum": [
        "monthly",
        "quarterly",
        "annual",
        "one_time"
      ],
      "description": "תדירות התשלום: monthly (חודשי), quarterly (רבעוני), annual (שנתי), one_time (חד פעמי)."
    },
    "start_date": {
      "type": "string",
      "description": "תאריך תחילת ההכנסה (YYYY-MM-DD)."
    },
    "end_date": {
      "type": "string",
      "description": "תאריך סיום ההכנסה (YYYY-MM-DD). אופציונלי - אם לא צוין, ההכנסה נחשבת כמתמשכת."
    },
    "tax_treatment": {
      "type": "string",
      "enum": [
        "taxable",
        "exempt",
        "fixed_rate"
      ],
      "description": "יחס מס: taxable (חייב במס שולי), exempt (פטור), fixed_rate (שיעור קבוע)."
    },
    "tax_rate": {
      "type": "number",
      "description": "שיעור מס קבוע (0-100). רלוונטי רק אם tax_treatment=fixed_rate."
    },
    "description": {
      "type": "string",
      "description": "תיאור ההכנסה (אופציונלי)."
    }
  },
  "required": [
    "source_type",
    "amount",
    "frequency",
    "start_date"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CREATE_INDIVIDUAL_ASSET
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🏦 כלי תפעול ליצירת נכס קצבה או הון באופן עצמאי (ללא המרה מהמסלקה). השתמש בכלי זה כאשר הלקוח רוצה להוסיף נכס ידנית. טריגרים: 'הוסף קרן פנסיה', 'יש לי ביטוח מנהלים', 'הוסף נכס הון', 'קופת גמל'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "asset_category": {
      "type": "string",
      "enum": [
        "pension",
        "capital"
      ],
      "description": "קטגוריית הנכס: pension (קצבה - קרן פנסיה/ביטוח מנהלים) או capital (הון - קופת גמל/חיסכון)."
    },
    "asset_name": {
      "type": "string",
      "description": "שם הנכס (למשל: 'מקפת אישית', 'הראל פנסיה')."
    },
    "asset_type": {
      "type": "string",
      "description": "סוג הנכס: לקצבה - 'קרן פנסיה', 'ביטוח מנהלים', 'קופת גמל'. להון - 'provident_fund', 'savings', 'severance'."
    },
    "balance": {
      "type": "number",
      "description": "יתרה/ערך נוכחי בשקלים."
    },
    "monthly_amount": {
      "type": "number",
      "description": "סכום חודשי (לקצבה) או הכנסה חודשית (להון). אופציונלי."
    },
    "start_date": {
      "type": "string",
      "description": "תאריך תחילה (YYYY-MM-DD)."
    },
    "tax_treatment": {
      "type": "string",
      "enum": [
        "taxable",
        "exempt",
        "capital_gains",
        "tax_spread"
      ],
      "description": "יחס מס: taxable (חייב), exempt (פטור), capital_gains (רווח הון), tax_spread (פריסת מס)."
    },
    "annuity_factor": {
      "type": "number",
      "description": "מקדם קצבה (רלוונטי לנכסי קצבה). אם לא צוין, יחושב אוטומטית."
    }
  },
  "required": [
    "asset_category",
    "asset_name",
    "balance",
    "start_date"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- CREATE_TAX_EXEMPT_GRANT
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🎁 כלי תפעול ליצירת מענק פטור ממס ממעסיק קודם. השתמש בכלי זה כאשר הלקוח מדווח על מענק פיצויים פטור שקיבל בעבר. טריגרים: 'קיבלתי פיצויים פטורים', 'מענק ממעסיק קודם', 'הוסף מענק פטור'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "employer_name": {
      "type": "string",
      "description": "שם המעסיק שממנו התקבל המענק."
    },
    "grant_amount": {
      "type": "number",
      "description": "סכום המענק בשקלים."
    },
    "work_start_date": {
      "type": "string",
      "description": "תאריך תחילת עבודה אצל המעסיק (YYYY-MM-DD)."
    },
    "work_end_date": {
      "type": "string",
      "description": "תאריך סיום עבודה אצל המעסיק (YYYY-MM-DD)."
    },
    "grant_date": {
      "type": "string",
      "description": "תאריך קבלת המענק (YYYY-MM-DD). אם לא צוין, ישמש תאריך סיום העבודה."
    }
  },
  "required": [
    "employer_name",
    "grant_amount",
    "work_start_date",
    "work_end_date"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- EXECUTE_PENSION_COMMUTATION
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🔴 כלי ביצוע (Execution Tool) - ביצוע היוון קצבה בפועל: יצירת נכס הון מסוג 'היוון' (asset_type=deposits) עם הערת COMMUTATION, והפחתת היתרה/קצבה במקור הקצבה (PensionFund). השתמש בכלי זה רק כאשר המשתמש מאשר לבצע היוון קיים במערכת, כולל בחירת קצבה ספציפית, סכום ותאריך. דוגמה: ###TOOL_CALL### {"name": "EXECUTE_PENSION_COMMUTATION", "arguments": {"pension_fund_id": 12, "commutation_amount": 50000, "commutation_date": "2025-01-01", "commutation_type": "exempt", "confirmed": true}}
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "pension_fund_id": {
      "type": "integer",
      "description": "מזהה מקור הקצבה (PensionFund) שממנו מבוצע ההיוון."
    },
    "commutation_amount": {
      "type": "number",
      "description": "סכום ההיוון (ברוטו) בשקלים."
    },
    "commutation_date": {
      "type": "string",
      "description": "תאריך ההיוון בפורמט YYYY-MM-DD."
    },
    "commutation_type": {
      "type": "string",
      "enum": [
        "exempt",
        "taxable"
      ],
      "description": "יחס מס לנכס ההיוון: exempt (פטור) או taxable (חייב). אם הקצבה פטורה ממס, ניתן לבחור רק exempt."
    },
    "confirmed": {
      "type": "boolean",
      "description": "האם המשתמש אישר את הביצוע. חובה להיות true."
    }
  },
  "required": [
    "pension_fund_id",
    "commutation_amount",
    "commutation_date",
    "commutation_type",
    "confirmed"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- EXECUTE_RETIREMENT_SCENARIO
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🔴 כלי ביצוע (Execution Tool) - מבצע בפועל תרחיש פרישה שמור לפי scenario_id. כולל ניקוי תוצאות ישנות, סימולציית עזיבת עבודה (אם מוגדר בתרחיש), וקיבוע זכויות אוטומטי.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "scenario_id": {
      "type": "integer",
      "description": "מזהה תרחיש שמור לביצוע."
    }
  },
  "required": [
    "scenario_id"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- EXECUTE_WORK_TERMINATION
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🚪 כלי תפעול לביצוע תהליך עזיבת עבודה בפועל. שונה מ-PROCESS_TERMINATION שמטפל בהחלטות פיצויים - כלי זה מבצע את הפעולה הטכנית של סיום העסקה במערכת. טריגרים: 'עזבתי את העבודה', 'פוטרתי', 'התפטרתי', 'סיימתי לעבוד'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "termination_date": {
      "type": "string",
      "description": "תאריך סיום העבודה (YYYY-MM-DD)."
    },
    "termination_reason": {
      "type": "string",
      "enum": [
        "resignation",
        "layoff",
        "retirement",
        "other"
      ],
      "description": "סיבת סיום: resignation (התפטרות), layoff (פיטורים), retirement (פרישה), other (אחר)."
    },
    "final_salary": {
      "type": "number",
      "description": "שכר אחרון (אם שונה מהשכר הרשום). אופציונלי."
    },
    "calculate_severance": {
      "type": "boolean",
      "description": "האם לחשב פיצויים אוטומטית. ברירת מחדל: true."
    }
  },
  "required": [
    "termination_date",
    "termination_reason"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- FIND_OPTIMAL_SCENARIO
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי שמריץ תרחישים למספר גילי פרישה ובוחר את התרחיש האופטימלי להשגת יעד קצבה. מחזיר גם ניתוח רגישות (קצבה לפי גיל פרישה).
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "target_monthly_pension": {
      "type": "number",
      "description": "יעד קצבה חודשי בשקלים."
    },
    "min_retirement_age": {
      "type": "integer",
      "description": "אופציונלי: גיל פרישה מינימלי לבדיקה."
    },
    "max_retirement_age": {
      "type": "integer",
      "description": "אופציונלי: גיל פרישה מקסימלי לבדיקה."
    }
  },
  "required": [
    "target_monthly_pension"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GENERATE_FULL_REPORT
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 📄 כלי להצגת דוח פרישה מלא בממשק. ברירת מחדל: פתיחת עמוד התוצאות (HTML) בדיוק כמו משתמש אנושי (/clients/:id/reports) והפעלת דוח ה-HTML. אופציונלי: ניתן לבקש גם הפקת PDF ע"י output_format=pdf.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "report_type": {
      "type": "string",
      "enum": [
        "retirement_plan",
        "tax_analysis",
        "cashflow",
        "full"
      ],
      "description": "סוג הדוח: retirement_plan (תכנית פרישה), tax_analysis (ניתוח מס), cashflow (תזרים), full (דוח מלא)."
    },
    "output_format": {
      "type": "string",
      "enum": [
        "html",
        "pdf"
      ],
      "description": "פלט: html (ברירת מחדל - פתיחת דוח HTML בממשק) או pdf (יצירת קובץ PDF להורדה)."
    },
    "include_charts": {
      "type": "boolean",
      "description": "האם לכלול גרפים בדוח. ברירת מחדל: true."
    },
    "retirement_date": {
      "type": "string",
      "description": "תאריך פרישה בפורמט YYYY-MM-DD לצורך הבטחת ניתוח עדכני לפני הפקת הדוח. אם לא נשלח, המערכת תנסה להשתמש בתאריך פרישה חוקי מתוך נתוני הלקוח."
    },
    "ensure_analysis": {
      "type": "boolean",
      "description": "האם לוודא שניתוח פרישה (RUN_RETIREMENT_CASHFLOW_ANALYSIS) בוצע לפני הפקת הדוח. ברירת מחדל: true."
    }
  },
  "required": [
    "report_type"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GENERATE_TAX_DEDUCTION_DOCUMENTS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 📄 כלי להפקת מסמכי קיבוע זכויות ואישורי מס בפורמט PDF. השתמש בכלי זה כאשר הלקוח מבקש מסמכי קיבוע זכויות, אישורי פטור, או טפסי מס. טריגרים: 'מסמכי קיבוע', 'אישור פטור', 'טופס 161', 'מסמכים לרשות המיסים'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "document_type": {
      "type": "string",
      "enum": [
        "kibua_zechuyot",
        "ptor_pitzuim",
        "form_161",
        "tax_spread"
      ],
      "description": "סוג המסמך: kibua_zechuyot (קיבוע זכויות), ptor_pitzuim (פטור פיצויים), form_161 (טופס 161), tax_spread (פריסת מס)."
    }
  },
  "required": [
    "document_type"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GET_ACCOUNT_DETAILS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: D11.1: כלי לשליפת פרטים מלאים על חשבון פנסיה ספציפי. השתמש בכלי זה כאשר הלקוח שואל על מוצר ספציפי, כגון 'מה הסטטוס של הראל', 'פרטים על מקפת', 'כמה יש לי במיטב'. מחזיר יתרה, סוג מוצר, שם חברה, פיצויים צבורים, ואם המוצר ברצף זכויות.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "search_term": {
      "type": "string",
      "description": "מחרוזת חיפוש - שם קרן, שם חברה, או חלק משם המוצר. לדוגמה: 'הראל', 'מקפת', 'מיטב', 'ביטוח מנהלים'."
    }
  },
  "required": [
    "search_term"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GET_CLIENT_SNAPSHOT
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: מחזיר snapshot info עבור הלקוח דרך /api/v1/clients/{client_id}/snapshot/info. מציג כמה קצבאות, נכסי הון, הכנסות נוספות, מענקים, האם יש מעסיק נוכחי, עזיבת עבודה, וקיבוע זכויות. השתמש בכלי זה כאשר הלקוח שואל 'מה יש לי במערכת', 'תראה לי סיכום', 'כמה מוצרים יש לי'. כאשר המשתמש מבקש 'רק JSON' או 'בלי הסברים' — החזר פלט JSON בלבד ללא טקסט נוסף.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {},
  "required": []
}
    ```
  - outputs:
    ```json
{
  "additionalProperties": true,
  "properties": {
    "success": {
      "title": "Success",
      "type": "boolean"
    },
    "tool_name": {
      "title": "Tool Name",
      "type": "string"
    },
    "total_items": {
      "title": "Total Items",
      "type": "integer"
    },
    "breakdown": {
      "title": "Breakdown",
      "type": "object"
    }
  },
  "required": [
    "success",
    "tool_name",
    "total_items",
    "breakdown"
  ],
  "title": "_GetClientSnapshotResult",
  "type": "object"
}
    ```
- GET_FIXATION_STATUS_SNAPSHOT
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: מחזיר סטטוס מכני (yes/no/unknown) של קיבוע זכויות והמסמכים/אירועים הנלווים כפי שהם קיימים בפועל במערכת (DB), כולל רשימת חוסרים. הכלי לא מבצע חישובים ולא מחזיר מספרים.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {},
  "required": []
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GET_PENSION_PRODUCTS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: Retrieves a detailed list of all pension products and capital assets in the client's portfolio, including balances and types.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {},
  "required": []
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GET_SYSTEM_NUMERIC_CONSTANTS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: מחזיר קבועים מספריים מאושרים מהמערכת (למשל MINIMUM_PENSION) לצורך שימוש בטקסט/הסבר בלי לבצע חישוב עצמאי ובלי להמציא מספרים.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {},
  "required": []
}
    ```
  - outputs:
    ```json
{
  "additionalProperties": true,
  "properties": {
    "success": {
      "title": "Success",
      "type": "boolean"
    },
    "tool_name": {
      "title": "Tool Name",
      "type": "string"
    },
    "result": {
      "title": "Result",
      "type": "object"
    }
  },
  "required": [
    "success",
    "tool_name",
    "result"
  ],
  "title": "_GetSystemNumericConstantsResult",
  "type": "object"
}
    ```
- GET_SYSTEM_STATE_SNAPSHOT
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: מחזיר snapshot מלא של כל הנתונים הקיימים בפועל במערכת עבור הלקוח (DB) כולל קצבאות, היוונים, הכנסות נוספות, נכסי הון, מענקים, מעסיק נוכחי/עזיבת עבודה, קיבוע זכויות, ותרחישים/תוצאות. חובה להשתמש בכלי זה כאשר המשתמש שואל 'מה יש במערכת' או מבקש פירוט מצב בפועל, במקום לנחש או להסתמך על טבלת מוצרים בלבד.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {},
  "required": []
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GET_TAX_PARAMS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: מחזיר פרמטרי מס (מדרגות, תקרות, CPI וכו') לשימוש בחישובי מס והצגה.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "tax_year": {
      "type": "integer",
      "description": "שנת מס (אופציונלי). אם לא סופק - השנה הנוכחית."
    }
  },
  "required": []
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- GET_TAX_PROJECTION
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי לחישוב הערכת מס מפורטת על קצבה חודשית ברוטו.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "gross_monthly_pension": {
      "type": "integer",
      "description": "סכום הקצבה החודשית ברוטו עליה יש לחשב מס"
    }
  },
  "required": [
    "gross_monthly_pension"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- PROCESS_TERMINATION
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🔴 כלי ביצוע (Execution Tool) - עזיבת עבודה/פיצויים בלבד. חוק: הסוכן שולח רק confirmed + exempt_choice + taxable_choice (ואופציונלי use_employer_completion=true). הסוכן לא שולח סכומים. השרת משלים את termination_date והסכומים ממסך המעסיק הנוכחי / חישוב פיצויים קיים. השתמש בכלי זה **רק** כאשר ההקשר הוא עזיבת עבודה והלקוח מאשר לבצע החלטה על פיצויים (משיכה / רצף קצבה / פיצול). אם ההקשר הוא קיבוע זכויות/היוון/פריסת מס/אישור פטור – השתמש ב-SUBMIT_TAX_COMMUTATION ולא בכלי זה.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "use_employer_completion": {
      "type": "boolean",
      "description": "האם תבוצע השלמת מעסיק (ברירת מחדל: true)."
    },
    "exempt_choice": {
      "type": "string",
      "enum": [
        "redeem_with_exemption",
        "redeem_no_exemption",
        "annuity"
      ],
      "description": "בחירה לחלק הפטור: redeem_with_exemption (משיכה עם פטור), redeem_no_exemption (משיכה ללא פטור), annuity (רצף קצבה)."
    },
    "taxable_choice": {
      "type": "string",
      "enum": [
        "redeem_no_exemption",
        "annuity",
        "split"
      ],
      "description": "בחירה לחלק החייב: redeem_no_exemption (משיכה עם פריסת מס), annuity (רצף קצבה), split (פיצול - השתמש ב-taxable_annuity_amount ו-taxable_capital_amount)."
    },
    "taxable_annuity_amount": {
      "type": "number",
      "description": "D4.1: סכום מדויק מתוך היתרה החייבת שיועבר לרצף קצבה. רלוונטי כאשר taxable_choice=split או כאשר רוצים לפצל את הסכום החייב."
    },
    "taxable_capital_amount": {
      "type": "number",
      "description": "D4.1: סכום מדויק מתוך היתרה החייבת שיועבר למענק הוני (כפוף למס/פריסה). רלוונטי כאשר taxable_choice=split או כאשר רוצים לפצל את הסכום החייב."
    },
    "tax_spread_years": {
      "type": "integer",
      "description": "מספר שנות פריסת מס (1-6). רלוונטי רק אם taxable_choice = redeem_no_exemption או אם יש taxable_capital_amount."
    },
    "confirmed": {
      "type": "boolean",
      "description": "האם הלקוח אישר את הפעולה. חובה להיות true לביצוע."
    },
    "plan_details": {
      "type": "string",
      "description": "JSON של פרטי התכניות הפנסיוניות שמהן נלקחים הפיצויים. כל תכנית כוללת: plan_name (שם התכנית), plan_start_date (תאריך התחלה), product_type (סוג מוצר: קרן פנסיה/ביטוח מנהלים/קופת גמל), amount (סכום). אם לא מועבר, המערכת תנסה לבנות אוטומטית מהפורטפוליו."
    }
  },
  "required": [
    "exempt_choice",
    "taxable_choice",
    "confirmed"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- PROJECT_TOTAL_ANNUITY
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: D10.1: כלי להקרנת קצבה חודשית כוללת מכל המוצרים בפורטפוליו. מחשב כמה קצבה חודשית הלקוח יקבל בפרישה מכל קרנות הפנסיה, ביטוחי המנהלים וקופות הגמל. השתמש בכלי זה כאשר הלקוח שואל 'כמה קצבה אקבל', 'מה הפנסיה שלי', 'כמה אקבל בפרישה'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "retirement_age": {
      "type": "integer",
      "description": "גיל פרישה (ברירת מחדל: 67). אם הלקוח ציין גיל אחר, השתמש בו."
    },
    "retirement_date": {
      "type": "string",
      "description": "תאריך פרישה בפורמט YYYY-MM-DD (אופציונלי). אם לא מסופק, יחושב לפי גיל הפרישה."
    }
  },
  "required": []
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- RUN_RETIREMENT_CASHFLOW_ANALYSIS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי מרכזי לניתוח תזרים פרישה. מחשב קצבה ברוטו, מס הכנסה, קצבה נטו, ופטור מקיבוע זכויות. השתמש בכלי זה כאשר הלקוח שואל 'כמה אקבל נטו', 'אחרי מס', 'פטור מקסימלי' או 'קיבוע זכויות'. דוגמה: ###TOOL_CALL### {"name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS", "arguments": {"retirement_date": "2028-01-01", "apply_max_exemption": true}}
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "retirement_date": {
      "type": "string",
      "description": "תאריך פרישה בפורמט YYYY-MM-DD. אם הלקוח נתן רק שנה (למשל 2028), השתמש ב-01-01 של אותה שנה."
    },
    "desired_monthly_income": {
      "type": "integer",
      "description": "יעד הכנסה חודשית נטו בשקלים (אופציונלי, ברירת מחדל: 70% מהשכר)."
    },
    "apply_max_exemption": {
      "type": "boolean",
      "description": "הפעל פטור מקסימלי מקיבוע זכויות. חובה להפעיל (true) כאשר הלקוח מבקש 'פטור מקסימלי' או 'קיבוע זכויות'."
    }
  },
  "required": [
    "retirement_date"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- RUN_RETIREMENT_SCENARIOS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי להרצת 3 תרחישי פרישה (מקסימום קצבה / מקסימום הון / מקסימום NPV) ולשמירתם במערכת. מחזיר מזהי תרחישים וסיכום (קצבה/הון/NPV) לכל תרחיש.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "retirement_age": {
      "type": "integer",
      "description": "גיל פרישה לחישוב (50-80)."
    },
    "include_current_employer_termination": {
      "type": "boolean",
      "description": "האם לכלול סימולציה של עזיבת עבודה (מעסיק נוכחי) כחלק מבניית התרחישים. ברירת מחדל: false."
    }
  },
  "required": [
    "retirement_age"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- SELECT_TARGET_PENSION_SCENARIO
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: כלי לבחירת תרחיש אופטימלי מבין תרחישים שמורים כדי להגיע ליעד קצבה. אם יש כמה שמגיעים ליעד - נבחר זה עם NPV הכי גבוה. אם אין שמגיעים - נבחר זה עם הקצבה הגבוהה ביותר.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "target_monthly_pension": {
      "type": "number",
      "description": "יעד קצבה חודשי בשקלים."
    },
    "retirement_age": {
      "type": "integer",
      "description": "אופציונלי: לסנן תרחישים לגיל פרישה מסוים."
    }
  },
  "required": [
    "target_monthly_pension"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- SET_CURRENT_EMPLOYER_DETAILS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 👔 כלי תפעול להזנת/עדכון פרטי המעסיק הנוכחי. השתמש בכלי זה כאשר הלקוח מספק פרטים על מקום עבודתו הנוכחי. טריגרים: 'אני עובד ב...', 'השכר שלי הוא...', 'התחלתי לעבוד ב...', 'עדכן פרטי מעסיק'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "employer_name": {
      "type": "string",
      "description": "שם המעסיק."
    },
    "start_date": {
      "type": "string",
      "description": "תאריך תחילת עבודה (YYYY-MM-DD)."
    },
    "last_salary": {
      "type": "number",
      "description": "שכר אחרון/נוכחי בשקלים."
    },
    "severance_accrued": {
      "type": "number",
      "description": "פיצויים שנצברו בשקלים. אופציונלי."
    },
    "expected_retirement_date": {
      "type": "string",
      "description": "תאריך פרישה צפוי (YYYY-MM-DD). אופציונלי."
    },
    "employer_id_number": {
      "type": "string",
      "description": "מספר ח.פ./עוסק של המעסיק. אופציונלי."
    }
  },
  "required": [
    "employer_name",
    "start_date",
    "last_salary"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- SUBMIT_TAX_COMMUTATION
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🔴 כלי ביצוע (Execution Tool) - קיבוע זכויות/היוון קצבה/פריסת מס/אישור פטור בלבד (לא עזיבת עבודה). מפעיל Workflow אוטומטי לביצוע סופי לאחר שהלקוח אישר תוצאות חישוב תיאורטי (מ-CALCULATE_PENSION_COMMUTATION, GET_TAX_PROJECTION, או CALCULATE_TAX_SPREAD_BENEFIT). טריגרים לדוגמה: 'בצע קיבוע', 'אשר את הפטור', 'הגש לרשות המיסים', 'סיים את התהליך', 'אני מאשר'. אם ההקשר הוא עזיבת עבודה/פיצויים (משיכה/רצף קצבה/פיצול) – השתמש ב-PROCESS_TERMINATION. שדה client_id הוא אופציונלי (נלקח מהבקשה/הקשר).
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "client_id": {
      "type": "integer",
      "description": "מזהה הלקוח במערכת."
    },
    "commutation_type": {
      "type": "string",
      "enum": [
        "היוון קצבה",
        "פטור על פיצויים",
        "פריסת מס",
        "קיבוע זכויות"
      ],
      "description": "סוג הקיבוע/אישור המס המבוצע."
    },
    "tax_projection_id": {
      "type": "string",
      "description": "מזהה ייחודי המקשר את הביצוע לתוצאת חישוב המס התיאורטי שבוצע קודם לכן."
    },
    "final_net_amount": {
      "type": "number",
      "description": "הסכום נטו הסופי שאושר ללקוח (לצורך תיעוד)."
    },
    "distribution_schedule": {
      "type": "string",
      "description": "אם סוג הקיבוע הוא פריסת מס, יש לציין את משך הפריסה (לדוגמה: '6 שנים'). אופציונלי."
    },
    "confirmed": {
      "type": "boolean",
      "description": "האם הלקוח אישר את הפעולה. חובה להיות true לביצוע."
    }
  },
  "required": [
    "commutation_type",
    "tax_projection_id",
    "final_net_amount",
    "confirmed"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)
- TRANSFORM_FUNDS_TO_ASSETS
  - source: app/services/llm_chat/tool_execution.py:execute_tool_call
  - description: 🔄 כלי תפעול להמרת כספים גלובליים (מטבלת מוצרים/מסלקה) לנכסי קצבה והון ספציפיים. השתמש בכלי זה כאשר הלקוח מבקש להמיר חשבונות פנסיוניים לנכסים במערכת. טריגרים: 'המר את הכספים', 'צור נכסים מהמסלקה', 'העבר לנכסים'.
  - inputs:
    ```json
{
  "type": "object",
  "properties": {
    "pension_start_date": {
      "type": "string",
      "description": "תאריך מימוש/תחילת קצבה בפורמט ISO (YYYY-MM-DD). אם מסופק ותאריך עתידי, המערכת תבצע projection ליתרות ותחשב מקדמים לפי הגיל בפועל בתאריך זה (כמו בכפתורי המערכת)."
    },
    "accounts": {
      "type": "array",
      "description": "רשימת חשבונות להמרה. מומלץ להעביר גם מזהים ותאריכים כדי לאפשר מניעת כפילויות וחישוב מקדמי קצבה מדויקים.",
      "items": {
        "type": "object",
        "properties": {
          "account_name": {
            "type": "string",
            "description": "שם התכנית/החשבון (למשל: 'כלל תמר')."
          },
          "balance": {
            "type": "number",
            "description": "יתרה נוכחית (₪)."
          },
          "product_type": {
            "type": "string",
            "description": "סוג מוצר (למשל: 'קופת גמל', 'קרן פנסיה', 'ביטוח מנהלים')."
          },
          "company": {
            "type": "string",
            "description": "חברה מנהלת (אם קיימת)."
          },
          "account_number": {
            "type": "string",
            "description": "מספר חשבון/תיק ניכויים לזיהוי חד-חד ערכי (מומלץ מאוד לאידמפוטנטיות)."
          },
          "start_date": {
            "type": "string",
            "description": "תאריך התחלת תכנית בפורמט ISO (YYYY-MM-DD). משמש לזיהוי דור פוליסה/מקדמים."
          },
          "pension_start_date": {
            "type": "string",
            "description": "תאריך מימוש/תחילת קצבה בפורמט ISO (YYYY-MM-DD). אם מסופק, יעקוף את pension_start_date הכללי עבור חשבון זה."
          },
          "conversion_type": {
            "type": "string",
            "enum": [
              "pension",
              "capital_asset"
            ],
            "description": "סוג המרה מפורש (pension/capital_asset). אם לא נשלח, המערכת תנסה לסווג אוטומטית."
          },
          "שם_תכנית": {
            "type": "string"
          },
          "יתרה": {
            "type": "number"
          },
          "סוג_מוצר": {
            "type": "string"
          },
          "חברה_מנהלת": {
            "type": "string"
          },
          "מספר_חשבון": {
            "type": "string"
          },
          "תאריך_התחלה": {
            "type": "string"
          },
          "תאריך_מימוש": {
            "type": "string"
          }
        },
        "required": [
          "balance"
        ]
      }
    },
    "default_conversion_type": {
      "type": "string",
      "enum": [
        "pension",
        "capital_asset"
      ],
      "description": "סוג המרה ברירת מחדל: pension (קצבה) או capital_asset (נכס הון). ברירת מחדל: pension."
    },
    "commute_pension_components": {
      "type": "boolean",
      "description": "כאשר ברירת המחדל היא המרה להון, האם לבצע היוון (COMMUTATION) לרכיבים קצבתיים שאינם ניתנים למשיכה כהון במקום להמיר אותם לנכס קצבה."
    },
    "ignore_blocked_balances": {
      "type": "boolean",
      "description": "האם להתעלם מיתרות חסומות (פיצויים שלא עברו התחשבנות / רצף זכויות / פיצויי מעסיק נוכחי) ולהמיר רק רכיבים שמותרים להמרה. ברירת מחדל: false."
    },
    "skip_non_convertible_accounts": {
      "type": "boolean",
      "description": "האם לדלג על חשבונות שלא ניתנים להמרה (למשל ללא פירוט רכיבים עבור נכס הון) במקום להחזיר שגיאת ולידציה. ברירת מחדל: false."
    }
  },
  "required": [
    "accounts"
  ]
}
    ```
  - outputs: `str` (tool results are returned as text; most tools return JSON text)

## 3. Orchestration Core
- Decision: `app/services/llm_chat/orchestration_core/core_types.py:OrchestrationDecision`
- Router: `app/services/llm_chat/orchestration_core/orchestrate.py:orchestrate`
- Executor (core loop, non-stream): `app/services/agent_execution/execute_agent_request.py:execute_agent_request`
- Executor (core loop, stream): `app/services/agent_execution/execute_agent_request.py:execute_agent_request_stream`
- Loop executor (legacy tool-loop): `app/services/llm_chat/orchestration_loop_core.py:run_orchestration_loop_core_sync`
- Loop guard (max iterations, core loop): `app/services/llm_chat/orchestration_core/max_iterations_guard.py:maybe_apply_max_iterations_guard`

## 4. Observability
- trace_id created at: `app/middleware/trace_id.py:TraceIdMiddleware`
- trace_id context storage: `app/utils/trace_context.py` (`get_current_trace_id` / `set_current_trace_id`)
- trace_id propagated (non-stream): `app/services/agent_execution/execute_agent_request.py:execute_agent_request` sets `request.trace_id` and `db.info[trace_id]`
- trace_id propagated (stream): `app/services/agent_execution/execute_agent_request.py:execute_agent_request_stream` wraps iterator and re-sets ContextVar during iteration
- tool_call_id stored at:
  - `app/services/llm_chat/chat_orchestration_parts/tool_calling.py:_execute_tool_call`
  - `app/services/agent_execution/execute_agent_request.py` (ToolResultEnvelope.tool_call_id)
- request_id / correlation id for JSONL logs: `app/utils/llm_chat_log.py` (`generate_request_id`, `set_current_request_id`, `log_llm_event`)
- trace persisted to DB at: `app/services/agent_trace_logger.py:log_trace_event` -> `app/models/agent_trace_event.py:AgentTraceEvent`
- stream extra correlation (if enabled): `app/middleware/stream_trace_logger.py:StreamTraceLoggerMiddleware` logs `x-railway-request-id`
