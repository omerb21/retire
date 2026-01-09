from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType


_LEGACY_MODULE: ModuleType | None = None


def load_legacy_steps_module() -> ModuleType:
    global _LEGACY_MODULE
    if _LEGACY_MODULE is not None:
        return _LEGACY_MODULE

    legacy_path = Path(__file__).resolve().parent.parent / "steps.py"
    if not legacy_path.exists():
        raise ImportError(f"Legacy steps.py not found at {legacy_path}")

    steps_pkg = (__package__ or "").rsplit(".", 1)[0]
    if not steps_pkg:
        raise ImportError("Failed to resolve parent package for legacy steps loader")

    module_name = f"{steps_pkg}._legacy_steps_py"
    loader = SourceFileLoader(module_name, str(legacy_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise ImportError(f"Failed to create module spec for {legacy_path}")

    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    _LEGACY_MODULE = module
    return module
