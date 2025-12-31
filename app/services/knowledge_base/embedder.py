from __future__ import annotations

import os
from typing import Protocol


class Embedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, *, model: str) -> None:
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        from openai import OpenAI  # type: ignore[import]

        self._client = OpenAI()
        return self._client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        client = self._get_client()
        resp = client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]


class OllamaEmbedder:
    def __init__(self, *, base_url: str, model: str) -> None:
        from langchain_community.embeddings import OllamaEmbeddings

        self._embeddings = OllamaEmbeddings(base_url=base_url, model=model)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [list(v) for v in self._embeddings.embed_documents(texts)]


def build_embedder(
    *,
    provider: str,
    openai_model: str,
    ollama_base_url: str,
    ollama_model: str,
) -> Embedder:
    provider_normalized = (provider or "").strip().lower()

    if provider_normalized == "openai":
        return OpenAIEmbedder(model=openai_model)

    if provider_normalized == "ollama":
        return OllamaEmbedder(base_url=ollama_base_url, model=ollama_model)

    raise ValueError(f"Unsupported RAG embedding provider: {provider}")
