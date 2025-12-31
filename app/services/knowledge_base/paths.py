from __future__ import annotations

from pathlib import Path


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[3]


def to_repo_relative_path(path: Path) -> str:
    root = repo_root_from_here()
    try:
        rel = path.resolve().relative_to(root)
    except Exception:
        return str(path)
    return str(rel).replace("\\", "/")
