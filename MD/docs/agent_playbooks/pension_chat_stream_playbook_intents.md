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

## Production smoke (manual)

Use fixed `X-Trace-Id` values and verify response bodies.

### REPORT only
```bash
curl -sS -X POST "https://<YOUR_PROD_HOST>/api/v1/llm/pension-chat-stream" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: train-report-001" \
  -d '{"client_id": 1, "messages": [{"role": "user", "content": "שלח דוח מסכם"}]}'
```

Expected:
- Exactly one `###UI_ACTION###...###END_UI_ACTION###` block
- No `🔧` and no tool output text

### REPORT QA
```bash
curl -sS -X POST "https://<YOUR_PROD_HOST>/api/v1/llm/pension-chat-stream" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: train-report-qa-001" \
  -d '{"client_id": 1, "messages": [{"role": "user", "content": "אנא הפק דוח מלא (QA)"}]}'
```

Expected:
- Exactly one `###UI_ACTION###...###END_UI_ACTION###` block
- Then only this exact line:

PASS - סיכום QA סופי לאחר יצירת הדוח

### NO_TOOLS
```bash
curl -sS -X POST "https://<YOUR_PROD_HOST>/api/v1/llm/pension-chat-stream" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: train-no-tools-001" \
  -d '{"client_id": 1, "messages": [{"role": "user", "content": "ענה רק במילים בלבד בלי כלים ובלי מספרים"}]}'
```

Expected:
- Verbal Hebrew response
- No tools, no `###TOOL_CALL###`, no numbers

## Smoke commands (PowerShell)

Set the local vars:

$BASE="https://retire-production.up.railway.app"
$PW="Benzvi5090"

### NO_TOOLS

$json='{"messages":[{"role":"user","content":"אל תפעיל כלים. ענה רק במילים."}],"client_id":36,"pension_portfolio":[]}'
Set-Content -Encoding UTF8 -Value $json .\smoke_no_tools_020.json
curl.exe -sS -N --http1.1 --tlsv1.2 --connect-timeout 10 --max-time 60 `
  -H "X-System-Password: $PW" `
  -H "Content-Type: application/json; charset=utf-8" `
  -H "Accept: text/event-stream" `
  -H "X-Trace-Id: smoke-no-tools-020" `
  --data-binary "@smoke_no_tools_020.json" `
  "$BASE/api/v1/llm/pension-chat-stream"

Success criteria: no `?` and none of: "האם" "תרצה" "בחר".

### ANALYSIS

$json='{"messages":[{"role":"user","content":"ניתוח ותיזמון פרישה"}],"client_id":36,"pension_portfolio":[]}'
Set-Content -Encoding UTF8 -Value $json .\smoke_analysis_020.json
curl.exe -sS -N --http1.1 --tlsv1.2 --connect-timeout 10 --max-time 180 `
  -H "X-System-Password: $PW" `
  -H "Content-Type: application/json; charset=utf-8" `
  -H "Accept: text/event-stream" `
  -H "X-Trace-Id: smoke-analysis-020" `
  --data-binary "@smoke_analysis_020.json" `
  "$BASE/api/v1/llm/pension-chat-stream"

Success criteria: after tool output the new fixed ending sentence appears, and there is no "אם תרצה" and no "האם" and no `?`.

### Smoke hardening helper (PowerShell)

If the response file contains NUL bytes and cannot be viewed normally, capture as binary and decode UTF-8 with a nul-strip.

```powershell
$outFile = ".\\smoke_response.bin"
curl.exe -sS --http1.1 --tlsv1.2 --connect-timeout 10 --max-time 60 `
  -H "X-System-Password: $PW" `
  -H "Content-Type: application/json; charset=utf-8" `
  -H "Accept: text/event-stream" `
  -H "X-Trace-Id: <TRACE_ID>" `
  --data-binary "@<JSON_FILE>.json" `
  --output $outFile `
  "$BASE/api/v1/llm/pension-chat-stream"

$exit = $LASTEXITCODE
if ($exit -ne 0) { throw "curl failed: exit=$exit" }

$bytes = Get-Content -Encoding Byte -Raw $outFile
$body = [System.Text.Encoding]::UTF8.GetString($bytes) -replace "`0", ""
```
