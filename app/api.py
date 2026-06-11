import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.retrieve import Retriever
from app.generate import generate_answer

app = FastAPI(title="AssistKB-Neosoft RAG API")

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

@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    start = time.time()
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=422, detail="La question ne peut pas être vide.")
    if request.top_k < 1 or request.top_k > 20:
        raise HTTPException(status_code=422, detail="top_k doit être compris entre 1 et 20.")

    sources = retriever.search(
        question=question,
        top_k=request.top_k
    )

    generation = generate_answer(
        question=question,
        sources=sources
    )

    latency_ms = round((time.time() - start) * 1000, 2)

    return {
        "answer": generation["answer"],
        "sources": sources,
        "latency_ms": latency_ms,
        "input_tokens": generation["input_tokens"],
        "output_tokens": generation["output_tokens"]
    }
