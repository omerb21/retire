from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


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
    return _load_yaml(get_capability_map_path())


@lru_cache(maxsize=4)
def load_output_schemas() -> dict[str, Any]:
    return _load_yaml(get_output_schemas_path())
