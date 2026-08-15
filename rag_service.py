import os
import re
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv


load_dotenv()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"


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

def answer_with_rag(question: str) -> str:
    results = retrieve(question)

    if not results:
        return "I couldn't find relevant information in the knowledge base."

    return "\n\n".join(r["text"] for r in results)