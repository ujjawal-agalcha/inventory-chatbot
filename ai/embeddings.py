import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# pyrefly: ignore [missing-import]
import faiss
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer

from config import KNOWLEDGE_DIR

logger = logging.getLogger("ai.embeddings")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 3

_embedding_model: Optional[SentenceTransformer] = None
_documents: List[Dict[str, Any]] = []
_index: Optional[faiss.IndexFlatIP] = None
_initialized = False


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading sentence transformer model: %s", EMBEDDING_MODEL_NAME)
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def load_documents() -> List[Dict[str, Any]]:
    """
    Load all .txt files from the knowledge directory.
    Each paragraph becomes a separate knowledge chunk.
    """
    documents = []
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    for path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        parts = re.split(r"\n\s*\n", text)
        for part in parts:
            part = part.strip()
            if part:
                documents.append({
                    "text": part,
                    "source": path.name,
                })
    return documents


def build_or_refresh_index():
    global _documents, _index, _initialized
    _documents = load_documents()

    if _documents:
        model = get_embedding_model()
        embeddings = model.encode(
            [doc["text"] for doc in _documents],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        embeddings = np.asarray(embeddings, dtype="float32")
        _index = faiss.IndexFlatIP(embeddings.shape[1])
        _index.add(embeddings)
        logger.info("Loaded %d knowledge chunks into vector index.", len(_documents))
    else:
        logger.warning("No knowledge documents found in %s", KNOWLEDGE_DIR)
        _index = None

    _initialized = True


def retrieve(query: str, k: int = TOP_K) -> List[Dict[str, Any]]:
    """Retrieve top-K matching knowledge chunks for query."""
    global _initialized
    if not _initialized:
        build_or_refresh_index()

    if not _documents or _index is None:
        return []

    model = get_embedding_model()
    query_embedding = model.encode(
        [query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    query_embedding = np.asarray(query_embedding, dtype="float32")
    scores, ids = _index.search(query_embedding, min(k, len(_documents)))

    results = []
    for rank, document_id in enumerate(ids[0]):
        if document_id < 0:
            continue
        results.append({
            "text": _documents[document_id]["text"],
            "source": _documents[document_id]["source"],
            "score": float(scores[0][rank]),
        })
    return results


def answer_with_rag(question: str) -> str:
    results = retrieve(question)
    if not results:
        return "I couldn't find relevant information in the knowledge base."
    return "\n\n".join(r["text"] for r in results)
