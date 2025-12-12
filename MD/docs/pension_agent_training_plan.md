# Pension Advisor LLM Agent – Technical Training and Execution Plan

## 1. Purpose and Scope

This document defines a structured, technical execution plan for training and operating the **Pension Advisor LLM Agent** in this system.

The agent should:
- Act as a **retirement advisor** for end clients (Hebrew dialogue),
- Use the existing backend tools and services (for example:
  - `RUN_RETIREMENT_CASHFLOW_ANALYSIS` via `AgentToolsService.run_retirement_cashflow_analysis`,
  - tax calculation tools (e.g. `GET_TAX_PROJECTION`),
  - rights fixation and exemption logic),
- Produce **clear, combined answers** (gross, tax, net, exemption impact) without exposing raw JSON or internal structures.

This plan focuses on:
- How the agent should use tools,
- How prompts and system messages should be structured,
- What internal documentation ("agent knowledge") is needed,
- How to define and implement conversational playbooks,
- How to evaluate and iteratively improve the agent.

---

## 2. Current Architecture – High-Level Integration Points

### 2.1. Main Components

- **LLM Router / Chat Endpoint**
  - File: `app/routers/llm_chat.py`
  - Key responsibilities:
    - Handle incoming chat requests (`pension_chat`, `pension_chat_stream`).
    - Manage conversation history and system messages.
    - Route tool calls through `_execute_tool_call`.
    - Detect special intents (e.g. net pension request, max exemption / rights fixation).

- **Agent Tools Service**
  - File: `app/services/llm_agent_tools_service.py`
  - Provides the concrete operations the agent can call, including for example:
    - `run_retirement_cashflow_analysis` (exposed to the agent as `RUN_RETIREMENT_CASHFLOW_ANALYSIS`).
    - Tax-related tools (e.g. `GET_TAX_PROJECTION`) that calculate taxes and exemptions.
    - Logic that integrates **rights fixation** and **maximum pension exemption** (קיבוע זכויות, apply_max_exemption).

- **Tax and Rights Fixation Services**
  - Files (non-exhaustive):
    - `app/schemas/tax_schemas.py` – tax input and validation (e.g. `TaxCalculationInput`).
    - `app/services/rights_fixation/core.py` – core rights fixation logic.
    - `app/services/rights_fixation/grant_impact.py` – grant impact computation.
    - `app/services/rights_fixation/exemption_caps.py` – exemption caps and percentages.

These components already support:
- Maximum rights fixation exemption for pension income (`apply_max_exemption`),
- Combined cashflow + tax analysis,
- Structured tool outputs that can be summarized for end clients.

---

## 3. Training Goals and Non-Goals

### 3.1. Goals

1. **Tool Mastery** – The agent reliably chooses and executes the correct backend tools for:
   - Retirement cashflow scenarios by year.
   - Net pension and effective tax calculations.
   - Rights fixation (קיבוע זכויות) and maximum pension exemption.

2. **Answer Quality** – For each relevant query, the agent:
   - Combines outputs from multiple tools (e.g. cashflow + tax),
   - Returns a **single, coherent summary** for the client (Hebrew, simple, clear),
   - Highlights: gross income, taxes (by type), net income, effect of exemptions.

3. **System Knowledge** – The agent can answer questions *about the system itself*:
   - What specific tools do,
   - What assumptions or limitations exist (e.g. allowed tax years),
   - Which scenarios are supported.

4. **Robustness and Safety** –
   - No raw JSON or low-level structures are exposed to end clients.
   - No hallucinated tools or parameters: only documented tools are used.
   - Consistent treatment of “max exemption” / “rights fixation” triggers.

### 3.2. Non-Goals (for this plan)

- Building a new training dataset from scratch or fine-tuning the base LLM.
- Designing a separate UI layer – the focus is on the backend agent behavior.
- Redesigning the entire domain model – we work with the existing services and schemas.

---

## 4. Execution Phases – Overview

The plan is divided into phases. Each phase defines:
- **Objective** – What we want to achieve.
- **Artifacts** – Files or documents to create/update.
- **Concrete Tasks** – Steps to implement in code and documentation.

### Phase 0 – Baseline Mapping and Invariants

Objective:
- Map existing tools and capabilities available to the agent.
- Define global invariants for agent behavior (e.g. never return raw JSON, always separate gross/tax/net).

Artifacts:
- `MD/docs/pension_agent_training_plan.md` (this file).
- `MD/docs/agent_tools_catalog.md` (tool catalog – to be created).

Concrete tasks:
1. Scan `app/services/llm_agent_tools_service.py` and related modules.
2. For each tool exposed to the LLM (e.g. `RUN_RETIREMENT_CASHFLOW_ANALYSIS`, `GET_TAX_PROJECTION`):
   - Document:
     - Tool name (as seen by the LLM).
     - Underlying service function.
     - Input parameters (required/optional) and meaning.
     - Output structure (key fields that matter to the agent and client).
3. Summarize **global agent invariants**, e.g.:
   - Never expose raw tool JSON or stack traces.
   - Always explain net vs gross vs tax.
   - When user mentions “פטור מקסימלי” or “קיבוע זכויות”, always enforce `apply_max_exemption=True`.

### Phase 1 – System Messages and Tool-Use Policy

Objective:
- Formalize and centralize all instructions that control the agent’s behavior at the prompt level.

Artifacts:
- Updates to `app/routers/llm_chat.py` system messages and tool-result messages.
- Section in this document summarizing the final system messages (for reference).

Concrete tasks:
1. Consolidate existing system prompts and helper messages in `llm_chat.py` for:
   - Regular chat (`pension_chat`).
   - Streaming chat (`pension_chat_stream`).
2. Encode explicit policy for:
   - When to call tools vs. when to answer from general knowledge.
   - How to chain tools (e.g. run cashflow → extract gross income → run tax projection → combine).
   - How to treat specific triggers (e.g. "נטו", "פטור מקסימלי", "קיבוע זכויות").
3. Ensure:
   - All tool-result messages instruct the LLM to **merge** multiple tool outputs into one coherent answer.
   - The LLM is instructed to **avoid raw JSON**, instead summarize and explain in user-friendly language.
4. Verify no code-level business logic creeps into entry points: they should only orchestrate tools and prompts.

### Phase 2 – Agent Knowledge Documentation

Objective:
- Provide the agent with concise, high-quality documentation about the system, available as reference.

Artifacts:
- `MD/docs/agent_tools_catalog.md` (detailed tool descriptions).
- Optionally: `MD/docs/agent_knowledge_index.md` – links to existing domain docs the agent may rely on.

Concrete tasks:
1. Build `agent_tools_catalog.md` based on Phase 0 mapping.
2. Identify existing docs that are relevant to the agent, e.g.:
   - `MD/docs/TAX_CALCULATION_FIX.md`,
   - `MD/docs/TAX_SPREAD_LOGIC.md`,
   - `MD/docs/pension_calculation_features.md`,
   - `MD/docs/SYSTEM_INTEGRITY_GUIDE.md`,
   - and other related files in `MD/docs/`.
3. Create `agent_knowledge_index.md` (optional) that:
   - Lists relevant documents.
   - Gives a short description of each.
   - Specifies how the agent should use them conceptually (e.g. for internal reasoning, not to copy verbatim to the client).

### Phase 3 – Conversational Playbooks

Objective:
- Define standard conversational flows for key business use-cases.

Artifacts:
- `MD/docs/agent_playbooks.md`.

Concrete tasks:
1. Select high-value scenarios, for example:
   - Single-year net pension question for a specific target year.
   - Multi-year comparison of retirement dates (e.g. 2028 vs. 2029).
   - Explanation-only questions about rights fixation, exemptions, or tax rules.
2. For each scenario, define a **playbook**:
   - How to interpret the user’s intent.
   - Which tools to call (and in what order).
   - How to aggregate and present the results (structure of the final explanation).
   - When to ask clarifying questions.
3. Encode those playbooks either:
   - As written documentation for the LLM (few-shot examples and instructions), and/or
   - As structured data that can be embedded into system messages.

### Phase 4 – Few-Shot Examples and Regression Questions

Objective:
- Provide concrete conversational examples to steer the LLM.
- Create a reusable regression set to test behavior after code or prompt changes.

Artifacts:
- `MD/docs/agent_conversation_examples.md` – example conversations (few-shot).
- `MD/docs/agent_regression_questions.md` – fixed list of questions and expected behaviors.

Concrete tasks:
1. Create example conversations that demonstrate:
   - Correct tool usage for net pension and maximum exemption.
   - Correct explanation style for end clients.
   - Handling of missing information (asking for clarifications).
2. Define a list of regression questions covering:
   - Core scenarios (single-year, multi-year, with/without exemption).
   - Edge cases (invalid years, unsupported scenarios, missing data).
3. Use these as a checklist whenever we modify prompts or tool logic.

### Phase 5 – Logging, Evaluation, and Iterative Improvement

Objective:
- Use real (or test) conversations and tool logs to continuously improve the agent.

Artifacts:
- Guidelines or scripts (as needed) for analyzing logs.
- Updates to previous artifacts based on findings.

Concrete tasks:
1. Ensure logs include:
   - User messages,
   - Agent responses,
   - Tool calls and results.
2. Periodically review logs to identify:
   - Incorrect tool choices.
   - Missing tool calls where they were needed.
   - Confusing explanations for clients.
3. Translate findings into improvements:
   - Update system messages and playbooks.
   - Add or refine few-shot examples.
   - Document new patterns or edge cases in `agent_tools_catalog.md` or related docs.

---

## 5. Concrete Step-by-Step Execution Roadmap

This section describes the practical order of implementation.

### Step 0 – Establish Plan (current step)

- Create `MD/docs/pension_agent_training_plan.md` (this file).
- Decide that this file is the **single source of truth** for the agent training roadmap.

Status: **Completed**.

### Step 1 – Tool Mapping and Agent Invariants (Phase 0)

1. Read `app/services/llm_agent_tools_service.py` and identify all methods that are exposed to the LLM as tools.
2. For each tool:
   - Record its name, parameters, and outputs in `MD/docs/agent_tools_catalog.md`.
3. In this plan file, add a short subsection summarizing **agent invariants** and reference them from prompts.
4. Validate that the implementation already respects:
   - Max exemption flag handling in `RUN_RETIREMENT_CASHFLOW_ANALYSIS`.
   - Year validation in `TaxCalculationInput` (`tax_schemas.py`).

### Step 2 – System Messages and Tool Policies (Phase 1)

1. Review system and helper messages in `app/routers/llm_chat.py` for:
   - `pension_chat`.
   - `pension_chat_stream`.
2. Adjust messages so that they:
   - Clearly instruct the LLM when and how to use tools.
   - Explicitly require combining outputs from multiple tools into a single coherent answer.
   - Enforce “no raw JSON” and “explain net vs gross vs tax vs exemptions”.
3. Where needed, refactor small pieces for clarity (without moving business logic into entry points).
4. Re-run basic manual tests or small scripts to ensure there are no syntax errors and that behavior aligns with expectations.

### Step 3 – Agent Knowledge Docs (Phase 2)

1. Create `MD/docs/agent_tools_catalog.md` (if not yet created in Step 1) and complete its core content.
2. Create `MD/docs/agent_knowledge_index.md`:
   - List and briefly describe each existing domain doc relevant to the agent.
3. Ensure the agent’s system messages (or retrieval configuration, if used) point conceptually to these knowledge sources.

### Step 4 – Playbooks for Key Use-Cases (Phase 3)

1. Create `MD/docs/agent_playbooks.md`.
2. Define at least 3–5 main playbooks:
   - Single-year net pension with/without max exemption.
   - Multi-year retirement date comparison.
   - Explanation-only flows.
3. Align prompts and tool policies with these playbooks.

### Step 5 – Conversation Examples and Regression Set (Phase 4)

1. Create `MD/docs/agent_conversation_examples.md` with carefully curated example dialogues.
2. Create `MD/docs/agent_regression_questions.md` with a set of questions and desired high-level responses or behaviors.
3. Use these as part of your manual regression when changing prompts or tool behavior.

### Step 6 – Logging-Based Iteration (Phase 5)

1. Confirm log structure and retention (implementation details depend on the existing logging setup).
2. Periodically review conversation and tool logs.
3. Feed insights back into:
   - System messages and prompt policies.
   - Playbooks and examples.
   - Tool catalog and knowledge docs.

---

## 6. Maintenance

- This plan should be updated whenever:
  - New tools are added to `AgentToolsService` and exposed to the LLM.
  - Major changes are made to tax, rights fixation, or retirement logic.
  - Significant new business use-cases are added.
- Changes should be reflected both:
  - In this roadmap file, and
  - In the concrete artifacts (catalog, playbooks, examples).
