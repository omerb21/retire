# Release Gates

## Commands (Golden, Overlap, Determinism)

Golden suites:

```bash
python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py
```

Overlap regression:

```bash
python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_overlap_regression_set.py
```

Determinism report test:

```bash
python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_determinism_report.py
```

## Determinism artifact (path + creation)

Artifact directory: `artifacts/determinism-report/`

Artifact file: `artifacts/determinism-report/determinism-report.json`

Bash (one-liner):

```bash
python -c "import json, os; from app.services.llm_chat.capability_router.determinism_report import run_determinism_report; data=run_determinism_report(); p='artifacts/determinism-report/determinism-report.json'; os.makedirs(os.path.dirname(p), exist_ok=True); f=open(p,'w',encoding='utf-8'); json.dump(data, f, ensure_ascii=False, indent=2, default=str); f.close()"
```

## CI wiring expectations (release_gates job + artifact name)

GitHub Actions artifact name: `determinism-report`

## PASS criteria

PASS WHEN:

- The CI workflow has a separate `release_gates` job that runs only the three commands listed above.
- The job uploads the artifact named `determinism-report`.
- The artifact contains `artifacts/determinism-report/determinism-report.json`.
