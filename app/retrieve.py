from __future__ import annotations

import os
from typing import Any

from app.embed import MODEL_NAME, _require_sentence_transformers, embed_texts
from app.store import QdrantStore, get_store


class Retriever:
    def __init__(
        self,
        threshold: float | None = None,
        model_name: str = MODEL_NAME,
    ):
        self.threshold = (
            float(os.environ.get("RETRIEVAL_THRESHOLD", "0.35"))
            if threshold is None
            else threshold
        )
        self.model_name = model_name
        self._model: Any | None = None
        self._store: QdrantStore | None = None

    @property
    def model(self) -> Any:
        if self._model is None:
            SentenceTransformer = _require_sentence_transformers()
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def store(self) -> QdrantStore:
        if self._store is None:
            self._store = get_store()
            self._store.ensure_collection()
        return self._store

    def search(self, question: str, top_k: int = 5) -> list[dict]:
        query_vector = embed_texts([question], self.model)[0]
        hits = self.store.search(query_vector, top_k=top_k)

        results = []
        for hit in hits:
            if hit.score < self.threshold:
                continue

            source = hit.metadata.get("source", "source inconnue")
            results.append(
                {
                    "text": hit.text,
                    "source": source,
                    "score": hit.score,
                    "metadata": hit.metadata,
                }
            )

        return results
