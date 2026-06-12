import os
import re

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

REFUSAL_ANSWER = "Je ne dispose pas de cette information dans le corpus."
MODEL_NAME = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")


class GenerationError(RuntimeError):
    pass


def _safe_error_message(exc: Exception) -> str:
    message = str(exc)
    message = re.sub(r"AIza[0-9A-Za-z_-]+", "<redacted>", message)
    message = re.sub(r"xai-[0-9A-Za-z_-]+", "<redacted>", message)
    message = re.sub(r"gsk_[0-9A-Za-z_-]+", "<redacted>", message)
    message = re.sub(r"(?i)(api[_-]?key=)[^&\s]+", r"\1<redacted>", message)
    if len(message) > 500:
        message = f"{message[:500]}..."
    return f"{type(exc).__name__}: {message}"


def is_groq_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def _get_client() -> OpenAI:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY est manquante dans l'environnement ou .env.")
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


# client = genai.Client(
#     api_key=os.getenv("GEMINI_API_KEY")
# )
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

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un assistant RAG strict qui repond uniquement avec le contexte fourni.",
                },
                {
                    "role": "user",
                    "content": build_prompt(question, sources),
                },
            ],
        )
    except Exception as exc:
        raise GenerationError(_safe_error_message(exc)) from exc

    usage = getattr(response, "usage", None)
    answer = ""
    if response.choices:
        answer = (response.choices[0].message.content or "").strip()

    return {
        "answer": answer or REFUSAL_ANSWER,
        "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
    }
