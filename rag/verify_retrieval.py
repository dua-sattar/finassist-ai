"""Manual end-to-end RAG quality check (Phase 5): retrieval + a real generated,
cited answer, for 5 canonical in-scope questions plus 1 out-of-scope question
that should NOT get a confidently invented answer.

Retrieval itself (rag.retrieval.retrieve) is free/local and needs no API key.
This script's answer-generation step calls Groq, so it needs GROQ_API_KEY set
in .env. Not a pytest suite (that's Phase 15) -- read the printed output.
"""

import os
import sys

from dotenv import load_dotenv

from rag.retrieval import retrieve

load_dotenv()

# Windows consoles often default to a legacy codepage (e.g. cp1252) that can't
# print characters an LLM might generate (em dashes, smart quotes, etc.).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SYSTEM_PROMPT = (
    "You are the FinAssist AI knowledge-base assistant. Answer the user's "
    "question using ONLY the provided context from internal company policy "
    "documents. If the context does not contain the answer, say plainly that "
    "you don't have that information in the knowledge base -- do not invent "
    "or guess an answer, and do not cite a source in that case. If you DID "
    "answer from the context, end with 'Source: <filename>' citing the "
    "document(s) the answer came from."
)

# (question, expected primary source file or None for out-of-scope)
CANONICAL_QUESTIONS = [
    ("What documents are required for client onboarding?", "required_documents.md"),
    ("What is FinAssist AI's refund policy?", "refund_policy.md"),
    ("How do I close my FinAssist AI account?", "account_closure.md"),
    ("What services does FinAssist AI offer?", "services.md"),
    ("What happens if I miss a payment?", "payment_policy.md"),
    ("What's the weather like in Paris today?", None),
]


def answer_with_citation(client, model: str, question: str, chunks) -> str:
    context = "\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        max_tokens=250,
    )
    return response.choices[0].message.content.strip()


def main() -> None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print(
            "GROQ_API_KEY is not set. Add it to your .env file to run the "
            "answer-generation step of this verification (retrieval itself "
            "works without it)."
        )
        return

    from groq import Groq

    client = Groq(api_key=api_key)
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    correct = 0
    for question, expected_source in CANONICAL_QUESTIONS:
        chunks = retrieve(question, k=4)
        sources = [c.source for c in chunks]
        answer = answer_with_citation(client, model, question, chunks)

        print(f"Q: {question}")
        print(f"  retrieved sources: {sources}")
        print(f"  answer: {answer}")

        if expected_source is not None:
            hit = expected_source in sources
            correct += int(hit)
            print(f"  [{'OK' if hit else 'MISS'}] expected {expected_source!r} among retrieved sources")
        else:
            print("  [out-of-scope question -- read the answer above manually: it should decline "
                  "rather than confidently invent a company policy answer]")
        print()

    in_scope_total = sum(1 for _, s in CANONICAL_QUESTIONS if s is not None)
    print(f"Retrieval accuracy: {correct}/{in_scope_total} in-scope questions retrieved the expected source.")


if __name__ == "__main__":
    main()
