from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeBaseSettings:
    enabled: bool
    auto_build_index: bool
    index_path: str
    source_globs: tuple[str, ...]
    chunk_max_chars: int
    top_k: int
    min_score: float
    embedding_provider: str
    openai_embedding_model: str
    ollama_base_url: str
    ollama_embedding_model: str


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_kb_settings() -> KnowledgeBaseSettings:
    enabled = _parse_bool(os.getenv("RAG_ENABLED"))

    auto_build_index = _parse_bool(os.getenv("RAG_AUTO_BUILD"))

    index_path = os.getenv(
        "RAG_INDEX_PATH",
        "artifacts/knowledge_base/kb_index.json",
    )

    raw_globs = os.getenv(
        "RAG_SOURCE_GLOBS",
        "MD/docs/**/*.md",
    )
    source_globs = tuple(g.strip() for g in raw_globs.split(",") if g.strip())

    chunk_max_chars = int(os.getenv("RAG_CHUNK_MAX_CHARS", "1600"))
    top_k = int(os.getenv("RAG_TOP_K", "4"))
    min_score = float(os.getenv("RAG_MIN_SCORE", "0.25"))

    embedding_provider = (os.getenv("RAG_EMBEDDING_PROVIDER") or "ollama").strip().lower()
    openai_embedding_model = (os.getenv("RAG_OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small").strip()

    ollama_base_url = (os.getenv("RAG_OLLAMA_BASE_URL") or "http://localhost:11434").strip()
    ollama_embedding_model = (os.getenv("RAG_OLLAMA_EMBEDDING_MODEL") or "nomic-embed-text").strip()

    return KnowledgeBaseSettings(
        enabled=enabled,
        auto_build_index=auto_build_index,
        index_path=index_path,
        source_globs=source_globs,
        chunk_max_chars=chunk_max_chars,
        top_k=top_k,
        min_score=min_score,
        embedding_provider=embedding_provider,
        openai_embedding_model=openai_embedding_model,
        ollama_base_url=ollama_base_url,
        ollama_embedding_model=ollama_embedding_model,
    )
