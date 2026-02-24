from __future__ import annotations

import json
import logging
from pathlib import Path

from app.services.knowledge_base.embedder import build_embedder
from app.services.knowledge_base.index_types import KnowledgeChunk
from app.services.knowledge_base.paths import repo_root_from_here, to_repo_relative_path

logger = logging.getLogger("app.knowledge_base")


def _iter_source_files(*, source_globs: tuple[str, ...]) -> list[Path]:
    root = repo_root_from_here()

    files: list[Path] = []
    for pattern in source_globs:
        try:
            matched = list(root.glob(pattern))
        except Exception:
            matched = []
        for p in matched:
            if p.is_file():
                files.append(p)

    # stable order
    files = sorted({p.resolve() for p in files})
    return files


def _read_text_file(path: Path, *, max_bytes: int = 2_000_000) -> list[str]:
    try:
        if path.stat().st_size > max_bytes:
            return []
    except Exception:
        return []

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    return content.splitlines()


def _chunk_lines(
    lines: list[str],
    *,
    max_chars: int,
    min_lines: int = 6,
) -> list[tuple[int, int, str]]:
    if not lines:
        return []

    max_chars = max(400, int(max_chars or 1600))

    chunks: list[tuple[int, int, str]] = []

    start = 0
    current: list[str] = []
    current_chars = 0

    def _flush(end_idx_exclusive: int) -> None:
        nonlocal start, current, current_chars
        if not current:
            return
        if len(current) < min_lines:
            return
        text = "\n".join(current).strip()
        if not text:
            return
        chunks.append((start + 1, end_idx_exclusive, text))
        current = []
        current_chars = 0

    for i, ln in enumerate(lines):
        ln_str = (ln or "").rstrip()
        current.append(ln_str)
        current_chars += len(ln_str) + 1

        # split on blank lines if we already accumulated enough
        if (not ln_str.strip()) and current_chars >= int(max_chars * 0.6):
            _flush(i + 1)
            start = i + 1
            continue

        if current_chars >= max_chars:
            _flush(i + 1)
            start = i + 1

    _flush(len(lines))
    return chunks


def build_knowledge_base_index(
    *,
    index_path: str,
    source_globs: tuple[str, ...],
    chunk_max_chars: int,
    embedding_provider: str,
    openai_embedding_model: str,
    ollama_base_url: str,
    ollama_embedding_model: str,
) -> dict:
    root = repo_root_from_here()
    output_path = root / Path(index_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = _iter_source_files(source_globs=source_globs)
    logger.info("KB indexing started: files=%s", len(files))

    embedder = build_embedder(
        provider=embedding_provider,
        openai_model=openai_embedding_model,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_embedding_model,
    )

    chunks: list[KnowledgeChunk] = []
    batch_texts: list[str] = []
    batch_meta: list[tuple[str, int, int]] = []

    def _flush_batch() -> None:
        nonlocal batch_texts, batch_meta, chunks
        if not batch_texts:
            return
        vectors = embedder.embed_texts(batch_texts)
        for (source_path, start_line, end_line), content, emb in zip(
            batch_meta, batch_texts, vectors
        ):
            chunk_id = f"{source_path}:{start_line}-{end_line}"
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    source_path=source_path,
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    embedding=list(emb),
                )
            )
        batch_texts = []
        batch_meta = []

    for p in files:
        rel = to_repo_relative_path(p)
        lines = _read_text_file(p)
        for start_line, end_line, text in _chunk_lines(
            lines, max_chars=chunk_max_chars
        ):
            batch_texts.append(text)
            batch_meta.append((rel, start_line, end_line))
            if len(batch_texts) >= 32:
                _flush_batch()

    _flush_batch()

    payload = {
        "version": 1,
        "source_globs": list(source_globs),
        "chunk_max_chars": int(chunk_max_chars),
        "embedding_provider": embedding_provider,
        "openai_embedding_model": openai_embedding_model,
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "source_path": c.source_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content": c.content,
                "embedding": c.embedding,
            }
            for c in chunks
        ],
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info("KB indexing finished: chunks=%s path=%s", len(chunks), output_path)

    return payload
