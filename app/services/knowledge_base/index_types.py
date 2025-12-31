from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source_path: str
    start_line: int
    end_line: int
    content: str
    embedding: list[float]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float
