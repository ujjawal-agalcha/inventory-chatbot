import os
import re
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"


# ============================================================
# EMBEDDING MODEL
# ============================================================

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# ============================================================
# RAG SETTINGS
# ============================================================

TOP_K = 3


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

print("Loading embedding model...")

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)

print("Embedding model loaded.")


# ============================================================
# LOAD DOCUMENTS
# ============================================================

def load_documents():
    """
    Load all .txt files from the knowledge directory.
    Each paragraph becomes a separate knowledge chunk.
    """

    documents = []

    KNOWLEDGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in sorted(
        KNOWLEDGE_DIR.glob("*.txt")
    ):

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        # Split on blank lines
        parts = re.split(
            r"\n\s*\n",
            text,
        )

        for part in parts:

            part = part.strip()

            if part:

                documents.append(
                    {
                        "text": part,
                        "source": path.name,
                    }
                )

    return documents


# ============================================================
# BUILD VECTOR INDEX
# ============================================================

documents = load_documents()

if documents:

    print(
        f"Loaded {len(documents)} knowledge chunks."
    )

    embeddings = embedding_model.encode(
        [doc["text"] for doc in documents],
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    embeddings = np.asarray(
        embeddings,
        dtype="float32",
    )

    index = faiss.IndexFlatIP(
        embeddings.shape[1]
    )

    index.add(
        embeddings
    )

else:

    print(
        "WARNING: No knowledge documents found."
    )

    embeddings = None
    index = None


# ============================================================
# GEMINI
# ============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    max_retries=2,
)


# ============================================================
# RETRIEVE KNOWLEDGE
# ============================================================

def retrieve(
    query: str,
    k: int = TOP_K,
):
    """
    Retrieve the most relevant knowledge chunks.
    """

    if not documents or index is None:

        return []

    query_embedding = embedding_model.encode(
        [query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32",
    )

    scores, ids = index.search(
        query_embedding,
        min(k, len(documents)),
    )

    results = []

    for rank, document_id in enumerate(
        ids[0]
    ):

        if document_id < 0:
            continue

        results.append(
            {
                "text": documents[
                    document_id
                ]["text"],

                "source": documents[
                    document_id
                ]["source"],

                "score": float(
                    scores[0][rank]
                ),
            }
        )

    return results


# ============================================================
# ANSWER USING RAG
# ============================================================

def answer_with_rag(
    question: str,
) -> str:

    results = retrieve(
        question
    )

    if not results:

        return (
            "I couldn't find relevant information "
            "in the knowledge base."
        )

    context = "\n\n".join(
        [
            result["text"]
            for result in results
        ]
    )

    prompt = f"""
You are an AI assistant for an IoT hardware
inventory management system.

Answer the user's question using the knowledge
provided below.

IMPORTANT RULES:

1. Use the provided knowledge as the source of truth
   for company-specific information.

2. Do not invent company-specific facts.

3. If the knowledge does not contain enough information
   to answer the question, say that the information is
   not available in the knowledge base.

4. Do NOT provide current inventory quantities from the
   knowledge base. Current stock information belongs to
   the inventory system.

5. Answer naturally and concisely.

KNOWLEDGE:
----------------
{context}
----------------

USER QUESTION:
{question}
"""

    response = llm.invoke(
        prompt
    )

    content = response.content

    if isinstance(
        content,
        str,
    ):
        return content

    if isinstance(
        content,
        list,
    ):

        text_parts = []

        for item in content:

            if isinstance(
                item,
                dict,
            ):

                text = item.get(
                    "text"
                )

                if text:
                    text_parts.append(
                        text
                    )

        if text_parts:
            return "\n".join(
                text_parts
            )

    return str(content)


# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "RAG Knowledge Assistant"
    )
    print(
        "Type 'exit' to quit."
    )
    print()

    while True:

        question = input(
            "You: "
        ).strip()

        if question.lower() == "exit":
            break

        try:

            results = retrieve(
                question
            )

            print()
            print(
                "Retrieved knowledge:"
            )

            for result in results:

                print(
                    f"- {result['source']} "
                    f"(score={result['score']:.3f})"
                )

            answer = answer_with_rag(
                question
            )

            print()
            print(
                f"Assistant: {answer}"
            )
            print()

        except Exception as error:

            print()
            print(
                "RAG error:"
            )
            print(
                repr(error)
            )
            print()
            