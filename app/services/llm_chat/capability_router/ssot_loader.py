from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger("app.capability_router.ssot")


_ALLOWED_SIDE_EFFECT_CLASS: set[str] = {"READ_ONLY", "STATE_CHANGE", "IRREVERSIBLE"}


def _default_capability_map_path() -> Path:
    return Path(__file__).with_name("capability_map.yaml")


def _canary_capability_map_path() -> Path:
    return Path(__file__).with_name("capability_map_canary.yaml")


def _get_core_version_source() -> Optional[str]:
    try:
        raw_version = os.environ.get("APP_VERSION") or os.environ.get(
            "SERVICE_VERSION"
        )  # noqa: E501
        if isinstance(raw_version, str) and raw_version.strip():
            return raw_version.strip()
    except Exception:
        return None
    return None


def _parse_version(version_str: str):
    try:
        from packaging.version import Version

        return Version(str(version_str or "").strip())
    except Exception:
        return None


def get_capability_map_path() -> Path:
    env = os.getenv("CAPABILITY_MAP_PATH")
    if isinstance(env, str) and env.strip():
        return Path(env.strip())

    mode = os.getenv("CAPABILITY_ROUTER_CANARY_MODE")
    mode = mode.strip() if isinstance(mode, str) else ""

    if mode in {"canary", "map_only"}:
        return _canary_capability_map_path()

    if mode == "core_and_map":
        core_version_str = _get_core_version_source()
        if not core_version_str:
            logger.warning(
                "core version source missing - core_and_map disabled "
                "until version "
                "SSOT exists"
            )
            return _default_capability_map_path()
        if _parse_version(core_version_str) is None:
            logger.warning(
                "core version parser missing - core_and_map disabled "
                "until version "
                "SSOT exists"
            )
            return _default_capability_map_path()

        return _canary_capability_map_path()
    return _default_capability_map_path()


def _default_output_schemas_path() -> Path:
    return Path(__file__).with_name("output_schemas.yaml")


def _default_ssot_v1_path() -> Path:
    return Path(__file__).with_name("ssot") / "ssot_v1.yaml"


def get_output_schemas_path() -> Path:
    env = os.getenv("OUTPUT_SCHEMAS_PATH")
    if isinstance(env, str) and env.strip():
        return Path(env.strip())
    return _default_output_schemas_path()


@lru_cache(maxsize=2)
def load_ssot_v1() -> dict[str, Any]:
    ssot = _load_yaml(_default_ssot_v1_path())
    from app.services.llm_chat.capability_router.ssot_validator import (
        validate_ssot_policy,
    )

    validate_ssot_policy(ssot)
    return ssot


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=4)
def load_capability_map() -> dict[str, Any]:
    ssot = load_ssot_v1()

    env_path = os.getenv("CAPABILITY_MAP_PATH")
    capability_map_path_set = bool(
        isinstance(env_path, str) and env_path.strip()
    )  # noqa: E501

    mode = os.getenv("CAPABILITY_ROUTER_CANARY_MODE")
    mode = mode.strip() if isinstance(mode, str) else ""

    path = get_capability_map_path()
    data = _load_yaml(path)

    if (
        not capability_map_path_set
        and mode == "core_and_map"
        and path == _canary_capability_map_path()
    ):
        core_version_str = _get_core_version_source()
        core_version = (
            _parse_version(core_version_str or "")
            if core_version_str
            else None  # noqa: E501
        )

        if core_version is None:
            logger.warning(
                "core version source missing - core_and_map disabled "
                "until version "
                "SSOT exists"
            )
            data = _load_yaml(_default_capability_map_path())
        else:
            raw_caps = (
                data.get("capabilities") if isinstance(data, dict) else None
            )  # noqa: E501
            caps = raw_caps if isinstance(raw_caps, list) else []

            filtered: list[dict[str, Any]] = []
            for cap in caps:
                if not isinstance(cap, dict):
                    continue
                min_v_str = cap.get("min_core_version")
                min_v = _parse_version(str(min_v_str or "0.0.0"))
                if min_v is None:
                    continue
                if core_version >= min_v:
                    filtered.append(cap)

            if isinstance(data, dict):
                data = dict(data)
                data["capabilities"] = filtered

    from app.services.llm_chat.capability_router.ssot_validator import (
        validate_capability_map,
    )

    _schemas = load_output_schemas()

    # Stage A: allow additional SSOT sections at root level (e.g. mcp_policy_matrix)
    # without breaking strict validation of the capabilities payload.
    data_for_validation = data
    try:
        if isinstance(data, dict) and "mcp_policy_matrix" in data:
            data_for_validation = dict(data)
            data_for_validation.pop("mcp_policy_matrix", None)
    except Exception:
        data_for_validation = data

    _ = validate_capability_map(raw=data_for_validation, output_schemas=_schemas, ssot=ssot)

    try:
        if os.getenv("SSOT_DEBUG") == "1":
            capability_map_version = (
                data.get("capability_map_version")
                if isinstance(data, dict)
                else None  # noqa: E501
            )
            capability_map_loaded = bool(isinstance(data, dict) and data)
            logger.info(
                "capability_map_loaded=%s capability_map_version=%s "
                "capability_map_path_set=%s",
                capability_map_loaded,
                capability_map_version,
                capability_map_path_set,
            )
    except Exception:
        pass

    return data


def load_mcp_policy_matrix() -> dict[str, Any] | None:
    """Load Stage A MCP policy matrix (SSOT contract only).

    Runtime tolerance requirements:
    - If section is missing: return None.
    - If invalid: return None + log warning.

    CI strictness is enforced by tests that require this to be present and valid.
    """

    try:
        cap_map = load_capability_map()
    except Exception as e:
        logger.warning("load_mcp_policy_matrix failed to load capability map: %s", e)
        return None

    raw = cap_map.get("mcp_policy_matrix") if isinstance(cap_map, dict) else None
    if raw is None:
        return None

    if not isinstance(raw, list):
        logger.warning("mcp_policy_matrix invalid: expected list")
        return None

    caps_raw = cap_map.get("capabilities") if isinstance(cap_map, dict) else None
    caps_list = caps_raw if isinstance(caps_raw, list) else []
    known_capability_ids: set[str] = set()
    for c in caps_list:
        if isinstance(c, dict):
            cid = c.get("capability_id")
            if isinstance(cid, str) and cid.strip():
                known_capability_ids.add(cid.strip())

    from app.services.llm_chat.mcp.types import MCPExecutionMode

    allowed_execution_modes: set[str] = {m.value for m in MCPExecutionMode}

    validated_entries: list[dict[str, Any]] = []
    try:
        for idx, entry in enumerate(raw):
            if not isinstance(entry, dict):
                raise ValueError(f"entry_not_dict:{idx}")

            capability_id = entry.get("capability_id")
            if not (isinstance(capability_id, str) and capability_id.strip()):
                raise ValueError(f"missing_capability_id:{idx}")
            capability_id = capability_id.strip()
            if known_capability_ids and capability_id not in known_capability_ids:
                raise ValueError(f"unknown_capability_id:{capability_id}")

            side_effect_class = entry.get("side_effect_class")
            if not (isinstance(side_effect_class, str) and side_effect_class.strip()):
                raise ValueError(f"missing_side_effect_class:{idx}")
            side_effect_class = side_effect_class.strip()
            if side_effect_class not in _ALLOWED_SIDE_EFFECT_CLASS:
                raise ValueError(
                    f"invalid_side_effect_class:{capability_id}:{side_effect_class}"
                )

            modes_raw = entry.get("allowed_execution_modes")
            if not isinstance(modes_raw, list) or not modes_raw:
                raise ValueError(f"missing_allowed_execution_modes:{idx}")
            for m in modes_raw:
                if not (isinstance(m, str) and m.strip()):
                    raise ValueError(f"invalid_execution_mode:{capability_id}")
                if m.strip() not in allowed_execution_modes:
                    raise ValueError(
                        f"invalid_execution_mode:{capability_id}:{m.strip()}"
                    )

            validated_entries.append(dict(entry))
    except Exception as e:
        logger.warning("mcp_policy_matrix invalid - disabled: %s", e)
        return None

    version: str | None = None
    try:
        v = cap_map.get("capability_map_version") if isinstance(cap_map, dict) else None
        version = str(v).strip() if isinstance(v, str) and v.strip() else None
    except Exception:
        version = None

    return {
        "policy_matrix_version": version,
        "entries": validated_entries,
    }


@lru_cache(maxsize=4)
def load_output_schemas() -> dict[str, Any]:
    data = _load_yaml(get_output_schemas_path())
    from app.services.llm_chat.capability_router.ssot_validator import (
        validate_output_schemas,
    )

    _ = validate_output_schemas(data)
    return data
