from __future__ import annotations

import json
import logging
import math
from functools import lru_cache
from pathlib import Path

from app.services.knowledge_base.embedder import build_embedder
from app.services.knowledge_base.index_types import KnowledgeChunk, RetrievedChunk
from app.services.knowledge_base.paths import repo_root_from_here

logger = logging.getLogger("app.knowledge_base")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y

    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    if denom <= 0:
        return 0.0
    return dot / denom


@lru_cache(maxsize=4)
def _load_index_cached(path_str: str, mtime_ns: int, size: int) -> list[KnowledgeChunk]:
    try:
        payload = json.loads(Path(path_str).read_text(encoding="utf-8"))
    except Exception:
        return []

    chunks_raw = payload.get("chunks")
    if not isinstance(chunks_raw, list):
        return []

    chunks: list[KnowledgeChunk] = []
    for item in chunks_raw:
        if not isinstance(item, dict):
            continue
        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            continue
        chunks.append(
            KnowledgeChunk(
                chunk_id=str(item.get("chunk_id") or ""),
                source_path=str(item.get("source_path") or ""),
                start_line=int(item.get("start_line") or 0),
                end_line=int(item.get("end_line") or 0),
                content=str(item.get("content") or ""),
                embedding=[float(x) for x in embedding if isinstance(x, (int, float))],
            )
        )

    return chunks


def _load_index(index_path: str) -> list[KnowledgeChunk]:
    root = repo_root_from_here()
    path = (root / Path(index_path)).resolve()
    if not path.exists() or not path.is_file():
        return []

    try:
        st = path.stat()
    except Exception:
        return []

    return _load_index_cached(
        str(path), int(getattr(st, "st_mtime_ns", 0)), int(st.st_size)
    )


def retrieve_relevant_chunks(
    *,
    query: str,
    index_path: str,
    top_k: int,
    min_score: float,
    embedding_provider: str,
    openai_embedding_model: str,
    ollama_base_url: str,
    ollama_embedding_model: str,
) -> list[RetrievedChunk]:
    if not query or not query.strip():
        return []

    chunks = _load_index(index_path)
    if not chunks:
        return []

    embedder = build_embedder(
        provider=embedding_provider,
        openai_model=openai_embedding_model,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_embedding_model,
    )
    query_vec = embedder.embed_texts([query.strip()])[0]

    scored: list[RetrievedChunk] = []
    for ch in chunks:
        score = _cosine_similarity(query_vec, ch.embedding)
        if score >= float(min_score or 0.0):
            scored.append(RetrievedChunk(chunk=ch, score=score))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[: max(1, int(top_k or 4))]
