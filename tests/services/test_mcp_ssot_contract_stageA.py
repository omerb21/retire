from __future__ import annotations


def _reset_ssot_loader(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITY_MAP_PATH", raising=False)
    monkeypatch.delenv("CAPABILITY_ROUTER_CANARY_MODE", raising=False)

    from app.services.llm_chat.capability_router import ssot_loader

    ssot_loader.load_capability_map.cache_clear()
    ssot_loader.load_output_schemas.cache_clear()
    ssot_loader.load_ssot_v1.cache_clear()


def test_stageA_capability_side_effect_class_present_and_valid(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map

    cap_map = load_capability_map()
    caps = cap_map.get("capabilities") if isinstance(cap_map, dict) else None
    assert isinstance(caps, list) and caps

    allowed = {"READ_ONLY", "STATE_CHANGE", "IRREVERSIBLE"}

    for cap in caps:
        assert isinstance(cap, dict)
        sec = cap.get("side_effect_class")
        assert isinstance(sec, str) and sec.strip()
        assert sec.strip() in allowed


def test_stageA_policy_matrix_present_and_versions_consistent(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from app.services.llm_chat.capability_router.ssot_loader import (
        load_capability_map,
        load_mcp_policy_matrix,
    )

    cap_map = load_capability_map()
    matrix = load_mcp_policy_matrix()

    assert isinstance(cap_map, dict)
    assert isinstance(matrix, dict)

    assert matrix.get("policy_matrix_version") == cap_map.get("capability_map_version")

    entries = matrix.get("entries")
    assert isinstance(entries, list) and entries


def test_stageA_report_is_always_no_tools_for_all_capabilities(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from app.services.llm_chat.capability_router.ssot_loader import (
        load_capability_map,
        load_mcp_policy_matrix,
    )

    cap_map = load_capability_map()
    matrix = load_mcp_policy_matrix()

    assert isinstance(cap_map, dict)
    assert isinstance(matrix, dict)

    caps = cap_map.get("capabilities")
    assert isinstance(caps, list) and caps

    capability_ids = []
    for cap in caps:
        assert isinstance(cap, dict)
        cid = cap.get("capability_id")
        assert isinstance(cid, str) and cid.strip()
        capability_ids.append(cid.strip())

    entries = matrix.get("entries")
    assert isinstance(entries, list) and entries

    report_entries_by_cap: dict[str, list[dict]] = {cid: [] for cid in capability_ids}

    for e in entries:
        assert isinstance(e, dict)
        if e.get("intent_tier") != "REPORT":
            continue
        cid = e.get("capability_id")
        assert isinstance(cid, str) and cid.strip()
        if cid.strip() in report_entries_by_cap:
            report_entries_by_cap[cid.strip()].append(e)

        allowed_modes = e.get("allowed_execution_modes")
        assert allowed_modes == ["NO_TOOLS"], "REPORT tier must always be NO_TOOLS"

    for cid, cap_entries in report_entries_by_cap.items():
        assert cap_entries, f"Missing REPORT policy matrix entries for capability_id={cid}"


def test_stageA_mcp_engine_decision_has_policy_matrix_metadata(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.engine import MCPEngine

    engine = MCPEngine()

    decision = engine.evaluate(
        intent_tier="ANALYSIS",
        intent_type="QA",
        router_decision=SimpleNamespace(capability_id="default_qa_v1", tool_chain=[]),
        guard_result={"tools_enabled": True},
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.policy_matrix_present is True
    assert isinstance(decision.policy_matrix_version, str) and decision.policy_matrix_version.strip()
