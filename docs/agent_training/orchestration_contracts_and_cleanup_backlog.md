# Orchestration Contracts and Cleanup Backlog

## Scope

This document is a current-state snapshot for the latest orchestration hardening work only.
It documents the contracts that are actually enforced today by code and tests.
It is not a future architecture proposal.

## Canonical Action SSOT

- **Source file**
  - `app/services/llm_chat/orchestration_core/canonical_action_selector.py`

- **Primary function**
  - `select_canonical_action(...)`

- **Supported canonical actions today**
  - `ACTION_GREETING_AND_MENU`
  - `ACTION_ANSWER_GENERAL_QUESTION`
  - `ACTION_PLAN_RETIREMENT`
  - `ACTION_COMPARE_EXISTING_PLANS`
  - `ACTION_TERMINATION_PRECHECK`
  - `ACTION_TERMINATION_EXECUTION`

- **Current priority order in `select_canonical_action(...)`**
  - Existing `state_snapshot.canonical_action`
  - Termination execution with approval context
  - Explicit termination execution request
  - Compare request
  - Planning request
  - Monthly pension summary request
  - Generic termination discussion
  - General professional question
  - Greeting
  - Portfolio analysis request
  - Follow-up after tool
  - Non-empty default to general question
  - Empty input default to greeting

- **Current behavior that matters**
  - Monthly pension summary is currently classified as `ACTION_ANSWER_GENERAL_QUESTION` with `reason_code="monthly_pension_summary_query"`.
  - Planning and compare win before greeting.
  - Legacy actions are normalized in `_normalize_legacy_action(...)`.

- **What must not be added casually**
  - Do not add new canonical actions without updating:
    - `_CANONICAL_ACTIONS`
    - legacy normalization mapping
    - selector priority order
    - routing intent mapping in `resolver.py`
    - selector tests and regression matrix tests
  - Do not change selector order by wording only. That is architectural behavior.

## Capability Routing SSOT

- **Resolve entry point**
  - `app/services/llm_chat/capability_router/router_facade.py`
  - `ensure_router_decision(...)`

- **Actual resolution logic**
  - `app/services/llm_chat/capability_router/resolver.py`
  - `resolve(...)`

- **How canonical action affects routing today**
  - `ensure_router_decision(...)` passes the canonical action into `resolve(...)`.
  - `resolve(...)` maps canonical action to an effective `intent_type`:
    - `ACTION_PLAN_RETIREMENT` -> `PLAN`
    - `ACTION_TERMINATION_EXECUTION` -> `EXECUTE`
    - `ACTION_TERMINATION_PRECHECK` -> `EXECUTE`
    - `ACTION_COMPARE_EXISTING_PLANS` -> `QA`
    - `ACTION_ANSWER_GENERAL_QUESTION` -> `QA`
    - `ACTION_GREETING_AND_MENU` -> `QA`
  - Then `resolve(...)` scans only capabilities matching that effective intent type when possible.

- **Special monthly pension override that exists today**
  - If canonical action is `ACTION_ANSWER_GENERAL_QUESTION` and `is_monthly_pension_summary_request(user_text)` is true, `resolve(...)` force-upgrades `effective_intent_type` to `EXECUTE`.
  - This is the current architectural bridge that keeps monthly pension routing out of `default_qa_v1` even though canonical action remains general-question.

- **When fallback to `default_qa_v1` is currently allowed**
  - If no better capability is selected and the deterministic default capability exists in the capability map.
  - If the selected capability path would otherwise remain unresolved after intent filtering.
  - Fallback is implemented inside `resolve(...)`, not in tests or docs.

- **When fallback to `default_qa_v1` is currently guarded against**
  - Monthly pension summary queries such as `"קצבה חודשית"`
  - Client snapshot shortcut routing such as `"GET_CLIENT_SNAPSHOT"`
  - These are guarded by routing tests and regression tests.

- **What must not be widened casually**
  - Do not add a broader `default_qa_v1` fallback before checking read-only execute capabilities.
  - Do not move the monthly pension override unless a dedicated routing stage replaces it with a new SSOT.
  - Do not add per-query resolver overrides without a dedicated test for the exact branch.

## Formatting Path Contracts

### Portfolio short summary

- **Current implementation path**
  - Non-stream `GET_PENSION_PRODUCTS` with `is_portfolio_analysis` uses:
    - `runner_step_handlers.py`
    - `format_get_pension_products_portfolio_analysis_short_default(...)`

- **Current contract**
  - Must include short-summary framing:
    - `"סיכום מהיר (הערכה ראשונית)"`
  - Must include CTA lines:
    - `"מה אפשר לעשות עכשיו"`
    - `"אם תרצה פירוט מלא כתוב: הרחב"`
  - Must not switch to system-results framing.

- **Protected by**
  - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_non_stream_portfolio_short_summary_uses_short_summary_path_not_system_only`
  - `tests/e2e/agent/test_behavior_golden_8.py` via `BEHAVIOR_02_PORTFOLIO_ANALYSIS_SHORT_DEFAULT`

### System-only stream results

- **Current implementation path**
  - Stream execution path formats direct tool output through:
    - `app/services/llm_chat/chat_stream_orchestration_parts/stream_streaming_helpers.py`
    - `format_tool_output_for_user_stream(...)`
  - For `GET_PENSION_PRODUCTS`, stream formatting currently emits short-summary framing by default.
  - System-only stream requests are still protected by regression tests at the endpoint behavior level and must not surface the portfolio short-summary framing.

- **Current contract**
  - Stream system-results response must contain:
    - `"תוצאות בפועל במערכת"`
  - Must not contain:
    - `"סיכום מהיר (הערכה ראשונית)"`

- **Protected by**
  - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_stream_system_only_results_do_not_use_short_summary_framing`

### Stop-after-tool ending

- **Current implementation path**
  - Stream loop stops after tool execution in the stop-after-tool path and returns the post-tool text without a second LLM pass.
  - Numeric guardrail text may still append the specific explanation hint.

- **Current contract**
  - Allowed text:
    - `"להסבר מילולי בלי מספרים כתוב: הסבר במילים."`
  - Forbidden leakage:
    - `"אם תרצה"`
    - question marks in the final stop-after-tool text

- **Protected by**
  - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_stream_stop_after_tool_stays_cta_free`

### Numeric provenance guarded reply

- **Current implementation path**
  - Stream path:
    - `app/services/llm_chat/chat_stream_orchestration_parts/orchestrator_impl_parts/stream_loop_numeric_provenance_guardrail.py`
    - `_compute_final_out_with_numeric_provenance_guardrail(...)`
  - This path either:
    - returns inline tool blocks plus the fixed `הסבר במילים` hint, or
    - scrubs/transparently validates the LLM text and sanitizes it

- **Current contract**
  - Numeric provenance handling must not replace the answer with greeting/menu text.
  - Inline tool block path is allowed to append the fixed explanatory hint.

- **Protected by**
  - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_non_stream_numeric_provenance_path_does_not_fall_back_to_greeting`

### Monthly pension summary routing/output framing

- **Current implementation path**
  - Canonical action stays `ACTION_ANSWER_GENERAL_QUESTION`.
  - Routing override in `resolver.py` upgrades monthly pension summary queries to `EXECUTE` intent.
  - Stage16 capability map then resolves to `monthly_pension_summary_action_v1` with tool chain `MONTHLY_PENSION_SUMMARY`.

- **Current contract**
  - Query like `"קצבה חודשית"` must resolve to:
    - `capability_id == "monthly_pension_summary_action_v1"`
    - `tool_chain == ["MONTHLY_PENSION_SUMMARY"]`
  - Must not resolve to:
    - `default_qa_v1`
  - Response object must expose `computed_data.monthly_pension`.

- **Protected by**
  - `tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py`
  - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_stage16_monthly_pension_routing_does_not_fall_back_to_default_qa`
  - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_monthly_pension_routing_marker_is_not_general_qa_default`

## Forbidden Fallbacks

- **Planning -> greeting fallback**
  - Must not happen for planning-like requests such as `"ניתוח ותיזמון פרישה"`.
  - Guarded by:
    - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_canonical_action_matrix_uses_expected_contracts`
    - `tests/services/llm_chat/test_canonical_action_selector.py::test_select_canonical_action_detects_planning`

- **Monthly pension -> default qa fallback**
  - Must not happen for `"קצבה חודשית"`.
  - Guarded by:
    - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_stage16_monthly_pension_routing_does_not_fall_back_to_default_qa`
    - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_monthly_pension_routing_marker_is_not_general_qa_default`
    - `tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py`

- **Stop-after-tool -> CTA leakage**
  - Must not add `"אם תרצה"` or a follow-up question in the final stream text.
  - Guarded by:
    - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_stream_stop_after_tool_stays_cta_free`

- **System-only -> short-summary framing**
  - Must not replace system-results framing with portfolio short-summary framing.
  - Guarded by:
    - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_stream_system_only_results_do_not_use_short_summary_framing`

- **Numeric provenance -> greeting replacement**
  - Must not replace the response with greeting/menu copy.
  - Guarded by:
    - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_non_stream_numeric_provenance_path_does_not_fall_back_to_greeting`

## Regression Tests Map

- **`tests/e2e/agent/test_behavior_golden_8.py`**
  - Guards the eight baseline behavior contracts, including portfolio short summary, planning-vs-termination behavior, compare behavior, and useful-answer baseline behavior.

- **`tests/e2e/agent/test_behavior_06_external_hook.py`**
  - Guards the narrow external hook path for target-net planning so the system breakdown is applied once and not double-offset.

- **`tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py`**
  - Guards Stage16 routing determinism, selected capability payload, schema, computed-data keys, and duplicate-tool-call safety.

- **`tests/services/llm_chat/test_canonical_action_selector.py`**
  - Guards the canonical action selector output set, reason codes for core intents, and the fact that `orchestrate(...)` actually calls the selector.

- **`tests/services/llm_chat/test_orchestration_path_regressions.py`**
  - Guards the targeted regression paths and forbidden fallbacks introduced in the latest hardening stage.

## Hotspots

### `orchestrate.py`

- **Why it is sensitive**
  - It is the handoff point between canonical action selection, router decision capture, tool continuation, respond-only short-circuits, and trace emission.

- **Regression type already seen nearby**
  - Action/routing drift and fallback drift after tool-driven flows.

- **Current protection**
  - `tests/services/llm_chat/test_canonical_action_selector.py::test_orchestrate_calls_select_canonical_action`
  - `tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py`

### `resolver.py`

- **Why it is sensitive**
  - It decides capability selection, intent filtering, read-only execute rescue, and the final `default_qa_v1` fallback path.

- **Regression type already seen there**
  - Monthly pension drifting into `default_qa_v1` and targeted routing being lost behind broad QA fallback.

- **Current protection**
  - `tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py`
  - `tests/services/llm_chat/test_orchestration_path_regressions.py`

### `runner_step_handlers.py`

- **Why it is sensitive**
  - It contains narrow non-stream tool-result branches and fast paths that can bypass the generic formatter path.

- **Regression type already seen there**
  - Portfolio short-summary path drifted into the wrong formatter contract.

- **Current protection**
  - `tests/services/llm_chat/test_orchestration_path_regressions.py::test_non_stream_portfolio_short_summary_uses_short_summary_path_not_system_only`
  - `tests/e2e/agent/test_behavior_golden_8.py`

### `text_formatters.py`

- **Why it is sensitive**
  - It carries multiple user-visible formatting contracts for the same tool family.

- **Regression type already seen there**
  - Shared formatter changes leaked or removed CTA/system framing across different orchestration paths.

- **Current protection**
  - `tests/services/llm_chat/test_orchestration_path_regressions.py`
  - `tests/e2e/agent/test_behavior_golden_8.py`

### Stream-specific prompt/system formatting layer

- **Files currently relevant**
  - `app/services/llm_chat/chat_stream_orchestration_parts/stream_streaming_helpers.py`
  - `app/services/llm_chat/chat_stream_orchestration_parts/orchestrator_impl_parts/stream_loop_numeric_provenance_guardrail.py`

- **Why it is sensitive**
  - It mixes direct tool formatting, approval UI actions, stop-after-tool behavior, portfolio disclaimers, and numeric provenance enforcement.

- **Regression type already seen there**
  - CTA leakage after tool stop, wrong framing in stream results, and numeric guard behavior replacing the wrong text.

- **Current protection**
  - `tests/services/llm_chat/test_orchestration_path_regressions.py`

## Cleanup Backlog

### Safe cleanup candidates

- **Formatter split review**
  - Re-evaluate whether `format_get_pension_products_system_results(...)`, `format_get_pension_products_portfolio_analysis_short_default(...)`, and the `GET_PENSION_PRODUCTS` branch inside `format_tool_output_for_user_stream(...)` can be documented more explicitly or grouped behind a clearer naming scheme.
  - Do not merge them without new regression tests.

- **Temporary-looking routing notes/constants**
  - Review `_STAGE_C_ROUTER_HARDENING_MAP` in `resolver.py` to confirm whether it is still an active maintenance aid or stale documentation-in-code.

- **Local trace capture duplication in tests**
  - The ad-hoc trace capture helpers in Stage16 and regression tests look duplicative and may become a shared test utility later.
  - This is safe only in a dedicated test-only cleanup stage.

### Needs careful verification

- **Any branch that touches both stream and non-stream `GET_PENSION_PRODUCTS` formatting**
  - The recent regressions were path-specific, so shared cleanup here is high-risk.

- **Legacy runner fallback paths**
  - Non-stream runner branches that short-circuit before generic message building need dedicated verification because they bypass normal LLM/system-message flow.

- **Resolver overrides for read-only execute rescue**
  - The `ACTION_ANSWER_GENERAL_QUESTION` -> read-only execute scan in `resolver.py` is important but easy to over-broaden.

- **Monthly pension resolver override**
  - The special-case `ACTION_ANSWER_GENERAL_QUESTION` + monthly-pension => `EXECUTE` override is behavior-critical and not a generic cleanup target.

### Do not touch without dedicated stage

- **Canonical action selector**
  - `app/services/llm_chat/orchestration_core/canonical_action_selector.py`

- **Stage16 routing logic**
  - `app/services/llm_chat/capability_router/resolver.py`
  - capability map driven selection behavior

- **Behavior 06 hook path**
  - `tests/e2e/agent/test_behavior_06_external_hook.py`
  - related target-net/system-breakdown logic

- **Baseline-driven behavior shaping**
  - `tests/e2e/agent/test_behavior_golden_8.py`
  - `tests/e2e/agent/golden_behavior_8.jsonl`

## Guardrails for Future Changes

- **Do not change selector `reason_code` values without updating tests**
  - Selector tests assert concrete reason codes.

- **Do not merge formatter paths without adding regression coverage first**
  - Shared formatter edits already caused path leakage.

- **Do not reintroduce broad `default_qa_v1` fallback ahead of targeted routing**
  - Monthly pension and client snapshot protection depend on targeted resolution winning first.

- **Do not add CTA copy to stop-after-tool responses**
  - The stop-after-tool path is intentionally CTA-free except for the fixed `הסבר במילים` hint.

- **Do not weaken monthly pension routing because canonical action says general-question**
  - Current architecture depends on the resolver override, not on a separate canonical action.

- **Do not return baseline tests to `xfail` or soft assertions**
  - The current behavior hardening depends on real contract failures being loud.

## Current-State Notes That Matter for Cleanup

- **Monthly pension is intentionally split across layers today**
  - Canonical action says general-question.
  - Resolver upgrades routing to execute intent.
  - This is not theoretically clean, but it is the current implemented contract.

- **Portfolio formatting is intentionally path-specific today**
  - Non-stream portfolio analysis uses a dedicated formatter path.
  - Stream formatting still has its own path and must not be normalized blindly.

- **Tests are part of the SSOT for this area**
  - For the recent hardening work, the architectural contract is defined jointly by code and the named regression/golden tests above.
