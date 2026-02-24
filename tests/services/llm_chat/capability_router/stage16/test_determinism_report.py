from __future__ import annotations

from typing import Any

import yaml


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded if isinstance(loaded, dict) else {}


def test_stage16_determinism_report(monkeypatch) -> None:
    from app.services.llm_chat.capability_router.determinism_report import (
        run_determinism_report,
    )
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()

    action = _load_yaml("tests/fixtures/stage16/golden_action_cases.yaml")
    overlap = _load_yaml("tests/fixtures/stage16/overlap_inputs.yaml")
    qa = _load_yaml("tests/fixtures/stage16/golden_qa_questions.yaml")

    cases: list[dict[str, Any]] = []

    for c in action.get("cases") or []:
        if isinstance(c, dict):
            cases.append(
                {
                    "case_id": f"action::{c.get('case_id')}",
                    "user_text": str(c.get("user_text") or ""),
                }
            )

    for i in overlap.get("inputs") or []:
        if isinstance(i, dict):
            cases.append(
                {
                    "case_id": f"overlap::{i.get('input_id')}",
                    "user_text": str(i.get("user_text") or ""),
                }
            )

    for q in qa.get("questions") or []:
        if isinstance(q, dict):
            cases.append(
                {
                    "case_id": f"qa::{q.get('question_id')}",
                    "user_text": str(q.get("question_text") or ""),
                }
            )

    report = run_determinism_report(cases=cases, runs=3)
    assert report.get("mismatches") == []
