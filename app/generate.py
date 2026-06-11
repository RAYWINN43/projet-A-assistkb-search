import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)
def build_prompt(question: str, sources: list[dict]) -> str:
    context = "\n\n".join(
        [
            f"[Source {i+1}] {s['source']}\n{s['text']}"
            for i, s in enumerate(sources)
        ]
    )

    return f"""
    
Tu es un RAG strict.

Règles obligatoires que tu doit suivre :
1. Tu dois répondre uniquement avec les passages fournis.
2. Tu dois citer les sources utilisées.
3. Si les passages ne permettent pas de répondre, tu dois dire :
   Je ne peux pas répondre avec les documents fournis.
4. Tu ne dois jamais inventer une information.
5. Tu ne dois pas utiliser tes connaissances générales.

Question utilisateur :
{question}

Passages disponibles :
{context}

Réponse attendue :
- Réponse claire
"""

def generate_answer(question: str, sources: list[dict]) -> dict:
    if not sources:
        return {
            "answer": "Je ne peux pas répondre avec les documents fournis.",
            "input_tokens": 0,
            "output_tokens": 0
        }

    prompt = build_prompt(question, sources)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    usage = getattr(response, "usage_metadata", None)

    return {
        "answer": response.text,
        "input_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
        "output_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0
    }