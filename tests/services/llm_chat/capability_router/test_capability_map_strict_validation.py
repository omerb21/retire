import textwrap

import pytest


def test_capability_map_invalid_unknown_field_fails_fast(tmp_path, monkeypatch) -> None:
    from app.services.llm_chat.capability_router.ssot_loader import \
        load_capability_map

    bad = textwrap.dedent("""
        capability_map_version: "x"
        published_at: "2026-02-24"
        router_normalization_version: "1.0"
        hash_version: "sha256/v1"
        capabilities:
          - capability_id: "default_qa_v1"
            mode: "QA"
            triggers:
              trigger_terms: []
              trigger_regex: [".*"]
              negative_triggers: []
            priority: 0
            tool_chain: []
            output_schema_id: "qa_answer_v1"
            unknown_field: "boom"
        """).strip()

    p = tmp_path / "cap.yaml"
    p.write_text(bad, encoding="utf-8")

    monkeypatch.setenv("CAPABILITY_MAP_PATH", str(p))
    load_capability_map.cache_clear()

    with pytest.raises(Exception):
        _ = load_capability_map()


def test_capability_map_invalid_unknown_tool_fails_fast(tmp_path, monkeypatch) -> None:
    from app.services.llm_chat.capability_router.ssot_loader import \
        load_capability_map

    bad = textwrap.dedent("""
        capability_map_version: "x"
        published_at: "2026-02-24"
        router_normalization_version: "1.0"
        hash_version: "sha256/v1"
        capabilities:
          - capability_id: "default_qa_v1"
            mode: "ACTION"
            triggers:
              trigger_terms: ["x"]
              trigger_regex: []
              negative_triggers: []
            priority: 1
            tool_chain: ["NON_EXISTING_TOOL"]
            output_schema_id: "action_ok_v1"
        """).strip()

    p = tmp_path / "cap.yaml"
    p.write_text(bad, encoding="utf-8")

    monkeypatch.setenv("CAPABILITY_MAP_PATH", str(p))
    load_capability_map.cache_clear()

    with pytest.raises(Exception):
        _ = load_capability_map()
