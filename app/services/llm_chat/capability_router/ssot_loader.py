from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger("app.capability_router.ssot")


def _default_capability_map_path() -> Path:
    return Path(__file__).with_name("capability_map.yaml")


def _canary_capability_map_path() -> Path:
    return Path(__file__).with_name("capability_map_canary.yaml")


def _get_core_version_source() -> Optional[str]:
    try:
        raw_version = os.environ.get("APP_VERSION") or os.environ.get("SERVICE_VERSION")
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
                "core version source missing - core_and_map disabled until version SSOT exists"
            )
            return _default_capability_map_path()
        if _parse_version(core_version_str) is None:
            logger.warning(
                "core version parser missing - core_and_map disabled until version SSOT exists"
            )
            return _default_capability_map_path()

        return _canary_capability_map_path()
    return _default_capability_map_path()


def _default_output_schemas_path() -> Path:
    return Path(__file__).with_name("output_schemas.yaml")


def get_output_schemas_path() -> Path:
    env = os.getenv("OUTPUT_SCHEMAS_PATH")
    if isinstance(env, str) and env.strip():
        return Path(env.strip())
    return _default_output_schemas_path()


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=4)
def load_capability_map() -> dict[str, Any]:
    env_path = os.getenv("CAPABILITY_MAP_PATH")
    capability_map_path_set = bool(isinstance(env_path, str) and env_path.strip())

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
            _parse_version(core_version_str or "") if core_version_str else None
        )

        if core_version is None:
            logger.warning(
                "core version source missing - core_and_map disabled until version SSOT exists"
            )
            data = _load_yaml(_default_capability_map_path())
        else:
            raw_caps = data.get("capabilities") if isinstance(data, dict) else None
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

    try:
        from app.services.llm_chat.capability_router.ssot_validator import (
            validate_capability_map,
        )

        _schemas = load_output_schemas()
        _ = validate_capability_map(raw=data, output_schemas=_schemas)
    except Exception:
        raise

    try:
        if os.getenv("SSOT_DEBUG") == "1":
            capability_map_version = (
                data.get("capability_map_version") if isinstance(data, dict) else None
            )
            capability_map_loaded = bool(isinstance(data, dict) and data)
            logger.info(
                "capability_map_loaded=%s capability_map_version=%s capability_map_path_set=%s",
                capability_map_loaded,
                capability_map_version,
                capability_map_path_set,
            )
    except Exception:
        pass

    return data


@lru_cache(maxsize=4)
def load_output_schemas() -> dict[str, Any]:
    data = _load_yaml(get_output_schemas_path())
    try:
        from app.services.llm_chat.capability_router.ssot_validator import (
            validate_output_schemas,
        )

        _ = validate_output_schemas(data)
    except Exception:
        raise
    return data
