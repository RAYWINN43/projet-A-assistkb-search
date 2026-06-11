from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.store import EMBEDDING_DIM, VectorRecord, get_store


MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "64"))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "120"))

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS_PATHS = (
    ROOT_DIR / "corpus" / "chunks.jsonl",
    ROOT_DIR / "corpus" / "processed" / "chunks.jsonl",
)
RAW_CORPUS_DIR = ROOT_DIR / "corpus" / "raw"


@dataclass(slots=True)
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str | int | None = None


def _require_sentence_transformers() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers est requis pour calculer les embeddings. "
            "Installez-le avec: pip install sentence-transformers"
        ) from exc
    return SentenceTransformer


def batched(items: list[Chunk], batch_size: int) -> Iterable[list[Chunk]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def normalize_vector(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


def normalize_vectors(vectors: Iterable[Iterable[float]]) -> list[list[float]]:
    return [normalize_vector(vector) for vector in vectors]


def load_chunks(chunks_path: Path | None = None) -> list[Chunk]:
    selected_path = chunks_path or _find_chunks_path()
    if selected_path is not None:
        return _load_chunks_jsonl(selected_path)

    print(
        "[embed] corpus/chunks.jsonl introuvable, fallback lecture texte de corpus/raw "
        "(R1 pourra remplacer par app.ingest)."
    )
    return _load_raw_corpus_chunks(RAW_CORPUS_DIR)


def _find_chunks_path() -> Path | None:
    env_path = os.environ.get("CHUNKS_PATH")
    if env_path:
        path = Path(env_path)
        return path if path.exists() else None

    for path in DEFAULT_CHUNKS_PATHS:
        if path.exists():
            return path
    return None


def _load_chunks_jsonl(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            text = str(data.get("text", "")).strip()
            if not text:
                continue
            metadata = dict(data.get("metadata") or {})
            for key in ("source", "type", "position", "language"):
                if key not in metadata and data.get(key) is not None:
                    metadata[key] = data[key]
            metadata.setdefault(
                "chunk_index",
                data.get("chunk_index", data.get("position", line_number - 1)),
            )
            chunks.append(Chunk(id=data.get("id"), text=text, metadata=metadata))

    if not chunks:
        raise ValueError(f"Aucun chunk lisible dans {path}")
    return chunks


def _load_raw_corpus_chunks(raw_dir: Path) -> list[Chunk]:
    if not raw_dir.exists():
        raise FileNotFoundError(
            "Aucun corpus a indexer: corpus/chunks.jsonl et corpus/raw introuvables."
        )

    chunks: list[Chunk] = []
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file():
            continue

        text = _extract_text(path)
        if not text:
            continue

        source = path.relative_to(ROOT_DIR).as_posix()
        for chunk_index, (start, end, chunk_text) in enumerate(split_text(text)):
            chunks.append(
                Chunk(
                    text=chunk_text,
                    metadata={
                        "source": source,
                        "chunk_index": chunk_index,
                        "start": start,
                        "end": end,
                    },
                )
            )

    if not chunks:
        raise ValueError("Aucun texte exploitable trouve dans corpus/raw.")
    return chunks


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".json"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".csv":
        return _extract_csv_text(path)
    if suffix in {".html", ".htm"}:
        return _strip_html(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    return ""


def _extract_csv_text(path: Path) -> str:
    rows: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        for row in reader:
            values = [cell.strip() for cell in row if cell.strip()]
            if values:
                rows.append(" | ".join(values))
    return "\n".join(rows)


def _strip_html(raw_html: str) -> str:
    without_scripts = re.sub(
        r"<(script|style).*?</\1>",
        " ",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return html.unescape(re.sub(r"\s+", " ", without_tags)).strip()


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"[embed] PDF ignore sans pypdf: {path}")
        return ""

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        print(f"[embed] PDF ignore illisible: {path} ({exc})")
        return ""
    return "\n".join(pages)


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> Iterable[tuple[int, int, str]]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return

    step = max(1, chunk_size - chunk_overlap)
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunk = cleaned[start:end].strip()
        if chunk:
            yield start, end, chunk
        if end == len(cleaned):
            break
        start += step


def embed_texts(texts: list[str], model: Any) -> list[list[float]]:
    vectors = model.encode(
        texts,
        batch_size=len(texts),
        convert_to_numpy=True,
        normalize_embeddings=False,
        show_progress_bar=False,
    )
    normalized = normalize_vectors(vectors)
    for vector in normalized:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"Dimension embedding invalide: {len(vector)} au lieu de {EMBEDDING_DIM}."
            )
    return normalized


def index_chunks(chunks: list[Chunk], batch_size: int = BATCH_SIZE) -> int:
    SentenceTransformer = _require_sentence_transformers()
    model = SentenceTransformer(MODEL_NAME)
    store = get_store()
    store.ensure_collection()

    indexed = 0
    total = len(chunks)
    for chunk_batch in batched(chunks, batch_size):
        texts = [chunk.text for chunk in chunk_batch]
        vectors = embed_texts(texts, model)
        records = [
            VectorRecord(
                id=chunk.id,
                text=chunk.text,
                metadata={
                    **chunk.metadata,
                    "embedding_model": MODEL_NAME,
                    "embedding_dim": EMBEDDING_DIM,
                },
                vector=vector,
            )
            for chunk, vector in zip(chunk_batch, vectors, strict=True)
        ]
        indexed += store.upsert(records)
        print(f"[embed] {indexed}/{total} chunks indexes")

    return indexed


def search_query(query: str, top_k: int) -> None:
    SentenceTransformer = _require_sentence_transformers()
    model = SentenceTransformer(MODEL_NAME)
    vector = embed_texts([query], model)[0]
    store = get_store()
    store.ensure_collection()

    hits = store.search(vector, top_k=top_k)
    for hit in hits:
        source = hit.metadata.get("source", "source inconnue")
        preview = hit.text.replace("\n", " ")[:180]
        print(f"[{hit.score:.3f}] {source} :: {preview}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexation embeddings vers Qdrant.")
    parser.add_argument("--chunks", type=Path, help="Chemin vers corpus/chunks.jsonl")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--query", help="Recherche rapide apres indexation existante")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if args.query:
        search_query(args.query, args.top_k)
        return

    chunks = load_chunks(args.chunks)
    indexed = index_chunks(chunks, batch_size=args.batch_size)
    print(
        f"[embed] Termine : {indexed} chunks dans le vector store "
        f"({MODEL_NAME}, dim={EMBEDDING_DIM})"
    )


if __name__ == "__main__":
    main()
