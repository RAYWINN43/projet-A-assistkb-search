import os

from dotenv import load_dotenv
from google import genai


load_dotenv()

REFUSAL_ANSWER = "Je ne dispose pas de cette information dans le corpus."
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY est manquante dans l'environnement ou .env.")
    return genai.Client(api_key=api_key)


def build_prompt(question: str, sources: list[dict]) -> str:
    context = "\n\n".join(
        f"[Source {index + 1}] {source['source']}\n{source['text']}"
        for index, source in enumerate(sources)
    )

    return f"""
Tu es un RAG strict.

Regles obligatoires que tu dois suivre :
1. Tu dois repondre uniquement avec les passages fournis.
2. Tu dois citer les sources utilisees.
3. Si les passages ne permettent pas de repondre, tu dois dire exactement :
   {REFUSAL_ANSWER}
4. Tu ne dois jamais inventer une information.
5. Tu ne dois pas utiliser tes connaissances generales.

Question utilisateur :
{question}

Passages disponibles :
{context}

Reponse attendue :
- Reponse claire
"""


def generate_answer(question: str, sources: list[dict]) -> dict:
    if not sources:
        return {
            "answer": REFUSAL_ANSWER,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    response = _get_client().models.generate_content(
        model=MODEL_NAME,
        contents=build_prompt(question, sources),
    )

    usage = getattr(response, "usage_metadata", None)

    return {
        "answer": response.text,
        "input_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
        "output_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
    }
