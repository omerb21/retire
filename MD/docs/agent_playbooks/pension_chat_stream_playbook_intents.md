# Pension Chat Stream - Intent Playbook (Deterministic)

This playbook applies ONLY to `/api/v1/llm/pension-chat-stream`.

## Core rule
The stream must run in exactly one of these intents (no mixing):

### NO_TOOLS
- Do not emit `###TOOL_CALL###`.
- Do not execute tools.
- Answer in Hebrew, short, words-only.
- No numbers.

### REPORT
- Do not write a report in the response.
- Do not ask follow-up questions.
- Do not emit `###TOOL_CALL###`.
- The system will generate the report deterministically via tools.
- Output MUST include exactly one `###UI_ACTION###...###END_UI_ACTION###` block.

**Exception C (QA / בדיקת מערכת):**
After the `###UI_ACTION###...###END_UI_ACTION###` block, it is allowed to add ONLY this single exact line:

PASS - סיכום QA סופי לאחר יצירת הדוח

No numbers.

### ANALYSIS
- Tool usage is allowed.
- If a tool was executed and the stream included a tool output section like: `🔧 **פלט כלי ...**`,
  the stream must end immediately after that with a short Hebrew sentence without numbers (stop-after-tool).
