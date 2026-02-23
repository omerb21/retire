$ErrorActionPreference = "Stop"

python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_golden_action_e2e.py
python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_overlap_regression_set.py
python -m pytest -q tests/services/llm_chat/capability_router/stage16/test_determinism_report.py
