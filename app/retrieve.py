import argparse
import os
from typing import Any, Optional, List, Dict

from app.embed import MODEL_NAME, _require_sentence_transformers, embed_texts
from app.store import QdrantStore, get_store


class Retriever:
    def __init__(
        self,
        threshold: Optional[float] = None,
        model_name: str = MODEL_NAME,
    ):
        self.threshold = (
            float(os.environ.get("RETRIEVAL_THRESHOLD", "0.35"))
            if threshold is None
            else threshold
        )
        self.model_name = model_name
        self._model: Optional[Any] = None
        self._store: Optional[QdrantStore] = None

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

    def search(self, question: str, top_k: int = 5) -> List[Dict]:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Recherche vectorielle dans Qdrant.")
    parser.add_argument("question", help="Question a rechercher dans le corpus indexe")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    retriever = Retriever(threshold=args.threshold)
    hits = retriever.search(args.question, top_k=args.top_k)

    if not hits:
        print("Aucun chunk au-dessus du seuil.")
        return

    for hit in hits:
        preview = hit["text"].replace("\n", " ")[:180]
        print(f"[{hit['score']:.3f}] {hit['source']} :: {preview}")


if __name__ == "__main__":
    main()