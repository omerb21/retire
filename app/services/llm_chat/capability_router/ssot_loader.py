from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("app.capability_router.ssot")


def _default_capability_map_path() -> Path:
    return Path(__file__).with_name("capability_map.yaml")


def get_capability_map_path() -> Path:
    env = os.getenv("CAPABILITY_MAP_PATH")
    if isinstance(env, str) and env.strip():
        return Path(env.strip())
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
    data = _load_yaml(get_capability_map_path())

    try:
        from app.services.llm_chat.capability_router.ssot_validator import \
            validate_capability_map

        _schemas = load_output_schemas()
        _ = validate_capability_map(raw=data, output_schemas=_schemas)
    except Exception:
        raise

    try:
        if os.getenv("SSOT_DEBUG") == "1":
            path_env = os.getenv("CAPABILITY_MAP_PATH")
            capability_map_path_set = bool(
                isinstance(path_env, str) and path_env.strip()
            )
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
        from app.services.llm_chat.capability_router.ssot_validator import \
            validate_output_schemas

        _ = validate_output_schemas(data)
    except Exception:
        raise
    return data
