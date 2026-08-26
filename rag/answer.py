"""Question -> retrieved context -> a cited, grounded answer via Groq.

Used by the Knowledge Base UI page for direct policy lookups (distinct from
the free-form chat agent in agent/graph.py, which composes its own answers
around tool calls).
"""

import logging
import os

from pydantic import BaseModel

from rag.retrieval import retrieve

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the FinAssist AI knowledge-base assistant. Answer the user's question "
    "using ONLY the provided context from internal company policy documents. If the "
    "context does not contain the answer, say plainly that you don't have that "
    "information in the knowledge base -- do not invent or guess an answer."
)


class AnswerResult(BaseModel):
    success: bool
    query: str
    answer: str = ""
    sources: list[str] = []
    error: str | None = None


def answer_question(query: str, k: int = 4) -> AnswerResult:
    chunks = retrieve(query, k=k)
    sources = sorted({c.source for c in chunks})

    if not chunks:
        return AnswerResult(
            success=True,
            query=query,
            answer="I don't have information about that in the knowledge base.",
            sources=[],
        )

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return AnswerResult(
            success=False,
            query=query,
            error="GROQ_API_KEY is not configured, so an answer cannot be generated.",
            sources=sources,
        )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        context = "\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
            ],
            max_tokens=350,
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            logger.warning("Groq returned an empty answer for %r", query)
            return AnswerResult(success=False, query=query, error="Received an empty response from the model.", sources=sources)
        return AnswerResult(success=True, query=query, answer=answer, sources=sources)
    except Exception as exc:
        logger.warning("answer_question failed for %r: %s", query, exc)
        return AnswerResult(success=False, query=query, error=str(exc), sources=sources)
