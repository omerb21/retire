from __future__ import annotations

import logging
from pathlib import Path

from app.services.knowledge_base.indexer import build_knowledge_base_index
from app.services.knowledge_base.paths import repo_root_from_here
from app.services.knowledge_base.retriever import retrieve_relevant_chunks
from app.services.knowledge_base.settings import get_kb_settings

logger = logging.getLogger("app.knowledge_base")


def build_rag_system_message(*, user_message: str) -> str | None:
    settings = get_kb_settings()
    if not settings.enabled:
        return None

    if settings.auto_build_index:
        root = repo_root_from_here()
        index_file = root / Path(settings.index_path)
        if not index_file.exists():
            try:
                build_knowledge_base_index(
                    index_path=settings.index_path,
                    source_globs=settings.source_globs,
                    chunk_max_chars=settings.chunk_max_chars,
                    embedding_provider=settings.embedding_provider,
                    openai_embedding_model=settings.openai_embedding_model,
                    ollama_base_url=settings.ollama_base_url,
                    ollama_embedding_model=settings.ollama_embedding_model,
                )
            except Exception as e:
                logger.warning("RAG auto-build index failed: %s", e)

    try:
        retrieved = retrieve_relevant_chunks(
            query=user_message,
            index_path=settings.index_path,
            top_k=settings.top_k,
            min_score=settings.min_score,
            embedding_provider=settings.embedding_provider,
            openai_embedding_model=settings.openai_embedding_model,
            ollama_base_url=settings.ollama_base_url,
            ollama_embedding_model=settings.ollama_embedding_model,
        )
    except Exception as e:
        logger.warning("RAG retrieval failed: %s", e)
        return None

    if not retrieved:
        return None

    parts: list[str] = []
    citations: list[str] = []
    for idx, item in enumerate(retrieved, start=1):
        ch = item.chunk
        cite = f"[{idx}] {ch.source_path}:{ch.start_line}-{ch.end_line}"
        citations.append(cite)
        parts.append(f"{cite}\n{ch.content}")

    joined = "\n\n---\n\n".join(parts)

    return (
        "ידע מערכת שנשלף מה-Knowledge Base (חובה להשתמש בו):\n"
        "- אם יש סתירה בין הידע הכללי שלך לבין הידע כאן, פעל לפי הידע כאן בלבד.\n"
        "- בכל תשובה, חובה לצרף סעיף 'מקורות' ולצטט את המסמכים/קטעים שבהם השתמשת (לפי המספרים [1], [2]...).\n\n"
        f"{joined}"
    )
