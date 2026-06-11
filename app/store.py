from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from hashlib import sha1
from typing import Any, Iterable


EMBEDDING_DIM = 384
DEFAULT_COLLECTION = "assistkb_chunks"


@dataclass(slots=True)
class VectorRecord:
    text: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str | int | None = None


@dataclass(slots=True)
class SearchHit:
    id: str | int
    score: float
    text: str
    metadata: dict[str, Any]


def _require_qdrant() -> tuple[Any, Any, Any, Any]:
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, PointStruct, VectorParams
    except ImportError as exc:
        raise RuntimeError(
            "qdrant-client est requis pour utiliser QdrantStore. "
            "Installez-le avec: pip install qdrant-client"
        ) from exc
    return QdrantClient, Distance, PointStruct, VectorParams


def stable_point_id(record: VectorRecord) -> str | int:
    if isinstance(record.id, int):
        return record.id

    metadata = record.metadata or {}
    if record.id is not None:
        raw_id = str(record.id)
    elif metadata.get("source") is not None and (
        metadata.get("chunk_index") is not None or metadata.get("position") is not None
    ):
        chunk_index = metadata.get("chunk_index", metadata.get("position"))
        raw_id = f"{metadata['source']}|{chunk_index}"
    else:
        text_hash = sha1(record.text.encode("utf-8")).hexdigest()
        raw_id = f"{metadata.get('source', 'unknown')}|{text_hash}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))


class QdrantStore:
    def __init__(
        self,
        collection_name: str | None = None,
        vector_size: int = EMBEDDING_DIM,
        url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.collection_name = collection_name or os.environ.get(
            "QDRANT_COLLECTION", DEFAULT_COLLECTION
        )
        self.vector_size = vector_size
        self.url = url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY")
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            QdrantClient, _, _, _ = _require_qdrant()
            self._client = QdrantClient(url=self.url, api_key=self.api_key)
        return self._client

    def ensure_collection(self) -> None:
        _, Distance, _, VectorParams = _require_qdrant()

        if not self._collection_exists():
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            return

        info = self.client.get_collection(self.collection_name)
        vectors_config = info.config.params.vectors
        size = getattr(vectors_config, "size", None)
        distance = str(getattr(vectors_config, "distance", "")).lower()

        if size != self.vector_size:
            raise ValueError(
                f"Collection Qdrant '{self.collection_name}' en dimension {size}, "
                f"mais {self.vector_size} etait attendu."
            )
        if "cosine" not in distance:
            raise ValueError(
                f"Collection Qdrant '{self.collection_name}' en distance {distance!r}, "
                "mais Cosine est attendu pour des vecteurs normalises."
            )

    def upsert(self, records: Iterable[VectorRecord]) -> int:
        _, _, PointStruct, _ = _require_qdrant()
        points = []

        for record in records:
            self._validate_vector(record.vector)
            point_id = stable_point_id(record)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=record.vector,
                    payload={
                        "text": record.text,
                        "metadata": record.metadata,
                    },
                )
            )

        if not points:
            return 0

        self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchHit]:
        self._validate_vector(query_vector)

        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )
            scored_points = getattr(response, "points", response)
        else:
            scored_points = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )

        hits: list[SearchHit] = []
        for point in scored_points:
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    id=point.id,
                    score=float(point.score),
                    text=str(payload.get("text", "")),
                    metadata=dict(payload.get("metadata") or {}),
                )
            )
        return hits

    def count(self) -> int:
        response = self.client.count(
            collection_name=self.collection_name,
            exact=True,
        )
        return int(response.count)

    def _collection_exists(self) -> bool:
        if hasattr(self.client, "collection_exists"):
            return bool(self.client.collection_exists(self.collection_name))

        try:
            self.client.get_collection(self.collection_name)
            return True
        except Exception:
            return False

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self.vector_size:
            raise ValueError(
                f"Vecteur invalide: {len(vector)} dimensions, "
                f"{self.vector_size} attendu."
            )


def get_store() -> QdrantStore:
    vector_store = os.environ.get("VECTOR_STORE", "qdrant").lower()
    if vector_store != "qdrant":
        raise ValueError(
            f"VECTOR_STORE={vector_store!r} non supporte pour le projet A. "
            "Utilisez VECTOR_STORE=qdrant."
        )
    return QdrantStore()
