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
    Source of truth: app.services.agent_execution.tool_contracts._CONTRACTS keys.
    """

    known: set[str] = set()

    # Source of truth: tool contracts registry keys.
    try:
        from app.services.agent_execution import \
            tool_contracts as tool_contracts_mod

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


def validate_capability_map(
    *, raw: dict[str, Any], output_schemas: dict[str, Any]
) -> CapabilityMapModel:
    """Strict validation + cross references.

    Raises pydantic.ValidationError for shape issues, ValueError for cross-ref issues.
    """

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

    for cap in model.capabilities:
        if cap.mode not in {"QA", "ACTION"}:
            raise ValueError(f"invalid_mode:{cap.capability_id}:{cap.mode}")

        if cap.output_schema_id not in schema_ids:
            raise ValueError(
                f"unknown_output_schema_id:{cap.capability_id}:{cap.output_schema_id}"
            )

        for tool_id in cap.tool_chain:
            if tool_id not in known_tools:
                raise ValueError(f"unknown_tool_in_chain:{cap.capability_id}:{tool_id}")

    return model
