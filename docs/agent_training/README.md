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

## בדיקות נדרשות

- pytest -q tests/agent_training/test_user_visible_path_parity.py
- pytest -q
- git diff --name-only
- git diff --name-status
