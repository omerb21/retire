# Agent Training

## Diff gate (PR-0)

Allowlist (PR-0):

- docs/agent_training/*
- tests/agent_training/test_user_visible_path_parity.py

Rule:

- Any status (including M, D, R, C) outside allowlist = reject.

### Self-check enforcement

- כל שינוי במבנה _skip שלא עומד ב-self-check יגרום ל-FAIL של הטסט ולא ניתן יהיה לעקוף זאת באותו PR.
- הבדיקה היא טקסטואלית בלבד.
- אין שימוש ב-AST ואין שימוש ב-regex מתקדם.
- חיפוש השורה שמתחילה ב-def נעשה החל מהתו שאחרי ה-newline הראשון שמופיע אחרי start.
- מנגנון ה self-check ממומש בתוך `tests/agent_training/test_user_visible_path_parity.py` ואינו מופרד למודול חיצוני, hook, conftest, או pytest plugin.

## PR-1

### Allowlist (PR-1)

- agent_training/
- tests/agent_training/
- docs/agent_training/README.md

- Any status (M, D, R, C) outside allowlist = reject.

### How to validate

- להריץ git diff --name-status --cached
- הפלט חייב להכיל רק קבצים שבתוך allowlist

## PR-2

### סעיף 1.2 – איסורים

* אסור `importlib` 
* אסור `__import__` 
* אסור `pkgutil` 
* אסור `exec` או `eval` לצורך import
* אסור חיפוש טקסטואלי כדי לגלות `module_path` 

### סעיף 1.3 – self-check

בדיקה על היעדר של:

* "importlib" 
* "__import__" 
* "pkgutil" 
* "exec(" 
* "eval(" 

## PR-3

- `golden_small.jsonl is a historical filename; it now contains the expanded golden set.`

### Allowlist (PR-3)

- docs/agent_training/README.md
- agent_training/golden/golden_small.jsonl

- Any status (M, D, R, C) outside allowlist = reject.

### How to validate

- git diff --name-status --cached
- python -c "<validator one-liner מהסעיף 5.2>"
- pytest -q tests/agent_training/test_golden_determinism.py

## PR-4

### Allowlist (PR-4)

- docs/agent_training/README.md
- tests/agent_training/test_golden_determinism.py
- agent_training/runner/readiness_spec_ref.json

- Any status (M, D, R, C) outside allowlist = reject.

### How to validate

- git diff --name-status --cached
- pytest -q tests/agent_training/test_golden_determinism.py

When `GOLDEN_REAL_PATH_B1=1`, the PR-4 real-path golden validation must fail (never skip) if real-path is not eligible.

OutcomeFinal SSOT is identified via runtime probe introspection only (no code search).
PR-4 implemented Real Path gate; real_path eligibility is controlled by readiness_spec_ref.json.
Rule: do not declare a PR "closed" if the primary goal is not met, unless it is explicitly split and deferred to the next PR.

## בדיקות נדרשות

## PR-5.1

### Allowlist (PR-5.1)

- docs/agent_training/README.md
- docs/agent_training/user_visible_path.md

- Any status (M, D, R, C) outside allowlist = reject.

### How to validate

- git diff --name-status --cached
- python -c "from app.services.agent_execution.execute_agent_request import execute_agent_request; print('OK')"

## PR-5

שלב 0 (חובה): prove-callability + prove-shape לפני ריצה על 90.
הוכחת stdout: הטסט חייב להדפיס שתי שורות בלבד עם prefix REAL_PATH, ויתכנו warnings של תלויות שאינם חלק מההוכחה.
הגדרת tool_called: בשלב PR-5 tool_called משמעו tool plan exists (ולא tool executed).

### Allowlist (PR-5)

- docs/agent_training/README.md
- tests/agent_training/test_golden_determinism.py
- agent_training/runner/readiness_spec_ref.json

- Any status (M, D, R, C) outside allowlist = reject.

### How to validate

- git diff --name-status --cached
- pytest -q tests/agent_training/test_golden_determinism.py

### DoD

- When GOLDEN_REAL_PATH_B1=1, first failure must be case mismatch or explicit signature-fail, not enabled-fail.
- With GOLDEN_REAL_PATH_B1=1, the first failure must be case-level (not eligibility), and real_path.enabled must remain true in readiness_spec_ref.json.
- Empty predicted fields in real_path mode must fail as missing fields, not as empty-string mismatches.

- pytest -q tests/agent_training/test_user_visible_path_parity.py
- pytest -q
- git diff --name-only
- git diff --name-status

## PR-6

PR-6 is environment alignment only: no heuristics, no rewriting predictions, no injecting text into responses; allowlist is exactly two files (tests/agent_training/test_golden_determinism.py + docs/agent_training/README.md).

## PR-7

PR-7 is enforcement-only and does not include real_path execution; real_path test returns in PR-8.

### Allowlist (PR-7)

- docs/agent_training/README.md
- tests/agent_training/test_golden_determinism.py
- agent_training/runner/readiness_spec_ref.json

- Any status (M, D, R, C) outside allowlist = reject.

### How to validate

- git diff --name-status --cached
- pytest -q tests/agent_training/test_golden_determinism.py

If agent_training/runner/readiness_spec_ref.json is not staged, it must not be changed; gate: git diff -- agent_training/runner/readiness_spec_ref.json must be empty.
