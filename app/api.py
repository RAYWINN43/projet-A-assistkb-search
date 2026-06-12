import logging
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.generate import GenerationError, MODEL_NAME, generate_answer, is_groq_configured
from app.retrieve import Retriever


app = FastAPI(title="AssistKB-Neosoft RAG API")
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]
    latency_ms: float
    input_tokens: int
    output_tokens: int


retriever = Retriever(threshold=0.35)


@app.get("/health")
def health():
    qdrant_status = {
        "ready": False,
        "indexed_chunks": None,
        "error": None,
    }

    try:
        store = retriever.store
        qdrant_status["indexed_chunks"] = store.count()
        qdrant_status["ready"] = True
    except Exception as exc:
        qdrant_status["error"] = f"{type(exc).__name__}: {exc}"

    return {
        "status": "ok",
        "groq_configured": is_groq_configured(),
        "groq_model": MODEL_NAME,
        "qdrant": qdrant_status,
    }


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    start = time.time()
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=422, detail="La question ne peut pas etre vide.")
    if request.top_k < 1 or request.top_k > 20:
        raise HTTPException(status_code=422, detail="top_k doit etre compris entre 1 et 20.")

    try:
        sources = retriever.search(
            question=question,
            top_k=request.top_k,
        )
    except Exception as exc:
        logger.exception("Erreur pendant la recherche vectorielle")
        raise HTTPException(
            status_code=503,
            detail=(
                "Erreur pendant la recherche vectorielle. "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc

    try:
        generation = generate_answer(
            question=question,
            sources=sources,
        )
    except GenerationError as exc:
        logger.exception("Erreur pendant la generation Groq")
        raise HTTPException(
            status_code=502,
            detail=f"Erreur pendant la generation Groq. {exc}",
        ) from exc
    except RuntimeError as exc:
        logger.exception("Configuration Groq invalide")
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    latency_ms = round((time.time() - start) * 1000, 2)

    return {
        "answer": generation["answer"],
        "sources": sources,
        "latency_ms": latency_ms,
        "input_tokens": generation["input_tokens"],
        "output_tokens": generation["output_tokens"],
    }
