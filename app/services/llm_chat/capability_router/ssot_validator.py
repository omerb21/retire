from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TriggersModel(BaseModel):
    trigger_terms: list[str]
    trigger_regex: list[str]
    negative_triggers: list[str]

    model_config = ConfigDict(extra="forbid")


class CapabilityModel(BaseModel):
    capability_id: str
    mode: str

    intent_tier: str = ""
    intent_type: str = ""
    side_effect_class: str = ""

    priority: int
    triggers: TriggersModel
    tool_chain: list[str]
    output_schema_id: str

    required_inputs: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    missing_prompt_template: str = ""

    data_presence_rule_id: str = ""
    data_presence_rule_params: dict[str, Any] = Field(default_factory=dict)

    min_core_version: str = "0.0.0"

    model_config = ConfigDict(extra="forbid")


class CapabilityMapModel(BaseModel):
    capability_map_version: str
    published_at: str
    router_normalization_version: str
    hash_version: str
    capabilities: list[CapabilityModel]

    model_config = ConfigDict(extra="forbid")


class OutputSchemasModel(BaseModel):
    schema_set_version: str
    published_at: str
    schemas: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


@lru_cache(maxsize=1)
def get_known_tool_ids() -> set[str]:
    """Deterministic known tool ids registry.

    Hardening target: validate SSOT tool_chain entries refer to known tools.
    Source of truth: app.services.agent_execution.tool_contracts._CONTRACTS
    keys.
    """

    known: set[str] = set()

    # Source of truth: tool contracts registry keys.
    try:
        from app.services.agent_execution import tool_contracts as tool_contracts_mod

        contracts = getattr(tool_contracts_mod, "_CONTRACTS", None)
        if isinstance(contracts, dict):
            for k in contracts.keys():
                if isinstance(k, str) and k.strip():
                    known.add(k.strip())
    except Exception:
        pass

    # Internal pseudo-tools that can appear in orchestration decisions.
    known.update(
        {
            "EXECUTION_ONLY",
            "TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY",
        }
    )

    # Legacy IDs used in older fixtures.
    known.update({"tool.client_snapshot_v1"})

    return known


def validate_output_schemas(raw: dict[str, Any]) -> OutputSchemasModel:
    """Strict validation: unknown fields forbidden."""

    return OutputSchemasModel.model_validate(raw)


def validate_ssot_policy(ssot: dict[str, Any]) -> None:
    if not isinstance(ssot, dict):
        raise ValueError("INVALID_SSOT_DECISION_POLICY:SSOT:ssot_not_dict")

    allowed_intent_type_raw = ssot.get("allowed_intent_type")
    allowed_intent_type = (
        [str(x).strip() for x in allowed_intent_type_raw if isinstance(x, str) and x]
        if isinstance(allowed_intent_type_raw, list)
        else []
    )

    precedence_raw = ssot.get("intent_type_precedence")
    precedence = (
        [str(x).strip() for x in precedence_raw if isinstance(x, str) and x]
        if isinstance(precedence_raw, list)
        else []
    )

    if len(set(precedence)) != len(precedence):
        raise ValueError("INVALID_SSOT_DECISION_POLICY:SSOT:precedence_has_duplicates")

    if set(precedence) != set(allowed_intent_type) or len(precedence) != len(
        allowed_intent_type
    ):
        raise ValueError(
            "INVALID_SSOT_DECISION_POLICY:SSOT:"
            "precedence_not_permutation_of_allowed_intent_type"
        )

    multi_intent_policy = ssot.get("multi_intent_policy")
    if multi_intent_policy != "PRECEDENCE":
        raise ValueError(
            "INVALID_SSOT_DECISION_POLICY:SSOT:" "multi_intent_policy_not_precedence"
        )

    allowed_intent_tier_raw = ssot.get("allowed_intent_tier")
    allowed_intent_tier = (
        [str(x).strip() for x in allowed_intent_tier_raw if isinstance(x, str) and x]
        if isinstance(allowed_intent_tier_raw, list)
        else []
    )

    tier_allowed = ssot.get("tier_allowed_intent_types")
    if not isinstance(tier_allowed, dict):
        raise ValueError(
            "INVALID_SSOT_DECISION_POLICY:SSOT:" "tier_allowed_intent_types_not_dict"
        )

    allowed_set = set(allowed_intent_type)
    for tier in allowed_intent_tier:
        raw_allowed = tier_allowed.get(tier)
        if not isinstance(raw_allowed, list):
            msg = (
                "INVALID_SSOT_DECISION_POLICY:SSOT:"
                "tier_allowed_missing_or_not_list:" + str(tier)
            )
            raise ValueError(msg)
        tier_set = {
            str(x).strip() for x in raw_allowed if isinstance(x, str) and x.strip()
        }
        if not tier_set.issubset(allowed_set):
            msg = "INVALID_SSOT_DECISION_POLICY:SSOT:" "tier_allowed_not_subset:" + str(
                tier
            )
            raise ValueError(msg)


def validate_capability_map(
    *,
    raw: dict[str, Any],
    output_schemas: dict[str, Any],
    ssot: dict[str, Any],
) -> CapabilityMapModel:
    """Strict validation + cross references.

    Raises pydantic.ValidationError for shape issues, ValueError for
    cross-ref issues.
    """

    allowed_failure_modes = (
        ssot.get("allowed_failure_modes") if isinstance(ssot, dict) else None
    )
    if not isinstance(allowed_failure_modes, list) or not any(
        isinstance(x, str) and x.strip() for x in allowed_failure_modes
    ):
        raise ValueError("SSOT_ALLOWED_FAILURE_MODES_EMPTY")

    allowed_modes_raw = ssot.get("allowed_modes") if isinstance(ssot, dict) else None
    if not isinstance(allowed_modes_raw, list) or not allowed_modes_raw:
        raise ValueError("SSOT_ALLOWED_MODES_EMPTY")

    allowed_modes = {
        str(x).strip() for x in allowed_modes_raw if isinstance(x, str) and x.strip()
    }
    if not allowed_modes:
        raise ValueError("SSOT_ALLOWED_MODES_EMPTY")

    report_policy = ssot.get("report_policy") if isinstance(ssot, dict) else None
    if report_policy != "UI_ACTION_ONLY":
        raise ValueError("SSOT_REPORT_POLICY_INVALID")

    validate_ssot_policy(ssot)

    allowed_intent_tier_raw = (
        ssot.get("allowed_intent_tier") if isinstance(ssot, dict) else None
    )
    allowed_intent_tier = (
        {
            str(x).strip()
            for x in allowed_intent_tier_raw
            if isinstance(x, str) and x.strip()
        }
        if isinstance(allowed_intent_tier_raw, list)
        else set()
    )

    allowed_intent_type_raw = (
        ssot.get("allowed_intent_type") if isinstance(ssot, dict) else None
    )
    allowed_intent_type = (
        {
            str(x).strip()
            for x in allowed_intent_type_raw
            if isinstance(x, str) and x.strip()
        }
        if isinstance(allowed_intent_type_raw, list)
        else set()
    )

    allowed_side_effect_class_raw = (
        ssot.get("allowed_side_effect_class") if isinstance(ssot, dict) else None
    )
    allowed_side_effect_class = (
        {
            str(x).strip()
            for x in allowed_side_effect_class_raw
            if isinstance(x, str) and x.strip()
        }
        if isinstance(allowed_side_effect_class_raw, list)
        else set()
    )

    model = CapabilityMapModel.model_validate(raw)

    schema_ids = set()
    try:
        os_model = validate_output_schemas(output_schemas)
        schema_ids = set(str(k) for k in os_model.schemas.keys())
    except Exception:
        schema_ids = set()

    if not schema_ids:
        raise ValueError("output_schemas_missing_or_invalid")

    known_tools = get_known_tool_ids()

    tier_allowed_intent_types_raw = (
        ssot.get("tier_allowed_intent_types") if isinstance(ssot, dict) else None
    )
    tier_allowed_intent_types: dict[str, set[str]] = {}
    if isinstance(tier_allowed_intent_types_raw, dict):
        for k, v in tier_allowed_intent_types_raw.items():
            if not (isinstance(k, str) and k.strip()):
                continue
            if not isinstance(v, list):
                continue
            tier_allowed_intent_types[k.strip()] = {
                str(x).strip() for x in v if isinstance(x, str) and x.strip()
            }

    catch_all_caps: list[str] = []

    for cap in model.capabilities:
        if cap.mode not in allowed_modes:
            raise ValueError(f"invalid_mode:{cap.capability_id}:{cap.mode}")

        intent_tier = (
            str(cap.intent_tier).strip() if cap.intent_tier is not None else ""
        )
        if not intent_tier:
            raise ValueError(f"MISSING_INTENT_TIER:{cap.capability_id}")
        if intent_tier not in allowed_intent_tier:
            raise ValueError(f"INVALID_INTENT_TIER:{cap.capability_id}:{intent_tier}")

        intent_type = (
            str(cap.intent_type).strip() if cap.intent_type is not None else ""
        )
        if not intent_type:
            raise ValueError(f"MISSING_INTENT_TYPE:{cap.capability_id}")
        if intent_type not in allowed_intent_type:
            raise ValueError(f"INVALID_INTENT_TYPE:{cap.capability_id}:{intent_type}")

        side_effect_class = (
            str(cap.side_effect_class).strip()
            if cap.side_effect_class is not None
            else ""
        )
        if not side_effect_class:
            raise ValueError(f"MISSING_SIDE_EFFECT_CLASS:{cap.capability_id}")
        if side_effect_class not in allowed_side_effect_class:
            msg = (
                "INVALID_SIDE_EFFECT_CLASS:"
                + str(cap.capability_id)
                + ":"
                + str(side_effect_class)
            )
            raise ValueError(msg)

        allowed_types_for_tier = tier_allowed_intent_types.get(intent_tier, set())
        if allowed_types_for_tier and intent_type not in allowed_types_for_tier:
            msg = (
                "TYPE_TIER_MISMATCH:"
                + str(cap.capability_id)
                + ":"
                + str(intent_tier)
                + ":"
                + str(intent_type)
            )
            raise ValueError(msg)

        if cap.mode == "ACTION" and intent_tier != "REPORT":
            raise ValueError(f"MODE_TIER_MISMATCH:{cap.capability_id}")
        if cap.mode == "QA" and intent_tier not in {"NO_TOOLS", "ANALYSIS"}:
            raise ValueError(f"MODE_TIER_MISMATCH:{cap.capability_id}")

        if side_effect_class == "IRREVERSIBLE" and intent_type not in {
            "EXECUTE",
            "APPROVE",
        }:
            raise ValueError(f"SIDE_EFFECT_INTENT_MISMATCH:{cap.capability_id}")
        if side_effect_class == "STATE_CHANGE" and intent_type not in {
            "PLAN",
            "EXECUTE",
            "APPROVE",
        }:
            raise ValueError(f"SIDE_EFFECT_INTENT_MISMATCH:{cap.capability_id}")

        if cap.mode == "ACTION" and cap.tool_chain:
            raise ValueError(f"REPORT_POLICY_VIOLATION:{cap.capability_id}")

        if cap.triggers.trigger_regex == [".*"]:
            catch_all_caps.append(str(cap.capability_id))

        if cap.output_schema_id not in schema_ids:
            msg = (
                "unknown_output_schema_id:"
                + str(cap.capability_id)
                + ":"
                + str(cap.output_schema_id)
            )
            raise ValueError(msg)

        for tool_id in cap.tool_chain:
            if tool_id not in known_tools:
                raise ValueError(f"unknown_tool_in_chain:{cap.capability_id}:{tool_id}")

    if not catch_all_caps:
        raise ValueError("CATCH_ALL_MISSING")
    if len(catch_all_caps) != 1:
        joined = ",".join([str(x) for x in catch_all_caps])
        raise ValueError(f"CATCH_ALL_MULTIPLE:{joined}")

    last_capability_id = ""
    try:
        last_capability_id = str(model.capabilities[-1].capability_id)
    except Exception:
        last_capability_id = ""

    if catch_all_caps[0] != last_capability_id:
        raise ValueError(f"CATCH_ALL_NOT_LAST:{catch_all_caps[0]}")

    return model
