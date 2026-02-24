$ErrorActionPreference = "Stop"

$REPO_ROOT = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $REPO_ROOT

python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_overlap_regression_set.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_determinism_report.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -c "import json, os, sys; sys.path.insert(0, os.getcwd()); from app.services.llm_chat.capability_router.determinism_report import run_determinism_report; from tests.services.llm_chat.capability_router.stage16.test_determinism_report import build_cases; cases=build_cases(); data=run_determinism_report(cases=cases, runs=3); p='artifacts/determinism-report/determinism-report.json'; os.makedirs(os.path.dirname(p), exist_ok=True); f=open(p,'w',encoding='utf-8'); json.dump(data, f, ensure_ascii=False, indent=2, default=str); f.close()"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
