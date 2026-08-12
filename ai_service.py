"""
AI + RAG service.

The service has two modes:
1. Local RAG retrieval from data/knowledge/*.txt, with optional
   sentence-transformers + FAISS.
2. Optional Gemini generation when GEMINI_API_KEY is configured.

The inventory database is NOT embedded. Live stock must always come
from the database/API so answers cannot use stale stock values.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import GEMINI_API_KEY, GEMINI_MODEL, RAG_TOP_K

KNOWLEDGE_DIR = Path(__file__).parent / "data" / "knowledge"


@dataclass
class Chunk:
    text: str
    source: str


class KnowledgeBase:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self._model = None
        self._index = None
        self._embeddings = None
        self.reload()

    def reload(self) -> None:
        self.chunks = []
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            parts = re.split(r"\n\s*\n", text)
            for part in parts:
                part = part.strip()
                if part:
                    self.chunks.append(Chunk(part, path.name))
        self._build_index()

    def _build_index(self) -> None:
        self._model = self._index = self._embeddings = None
        if not self.chunks:
            return
        try:
            from sentence_transformers import SentenceTransformer
            import faiss
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            vectors = self._model.encode(
                [c.text for c in self.chunks],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            import numpy as np
            self._embeddings = np.asarray(vectors, dtype="float32")
            self._index = faiss.IndexFlatIP(self._embeddings.shape[1])
            self._index.add(self._embeddings)
        except Exception:
            # The app remains functional with lexical retrieval if optional
            # vector dependencies are unavailable.
            self._model = self._index = self._embeddings = None


    def find_product_name(self, query: str) -> str | None:
        """Find an exact product name mentioned in the user's question."""

        q = query.lower()

        product_names = [
            "esp32-cam",
            "esp32 devkit v1",
            "esp8266 nodemcu",
            "arduino uno r3",
            "hc-sr04 ultrasonic sensor",
            "dht11 temperature sensor",
        ]

        for name in product_names:
            if name in q:
                return name

        return None



    def search(self, query: str, k: int = RAG_TOP_K) -> list[dict[str, str]]:
        if not self.chunks:
            return []

        if self._index is not None and self._model is not None:
            vector = self._model.encode(
                [query], normalize_embeddings=True, show_progress_bar=False
            )
            scores, ids = self._index.search(vector.astype("float32"), min(k, len(self.chunks)))
            return [
                {"text": self.chunks[i].text, "source": self.chunks[i].source,
                 "score": f"{float(scores[0][rank]):.3f}"}
                for rank, i in enumerate(ids[0]) if i >= 0
            ]

        # Simple lexical fallback. This is intentionally transparent.
        terms = {t.lower() for t in re.findall(r"[a-zA-Z0-9_-]+", query) if len(t) > 2}
        scored = []
        for chunk in self.chunks:
            words = set(re.findall(r"[a-zA-Z0-9_-]+", chunk.text.lower()))
            score = len(terms & words)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"text": c.text, "source": c.source, "score": str(s)}
            for s, c in scored[:k]
        ]


KB = KnowledgeBase()


def _gemini_answer(question: str, context: str, inventory_context: str) -> str | None:
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""You are the AI assistant for an IoT hardware inventory management system.

        Your job is to have a natural, helpful conversation while providing accurate information.

        IMPORTANT RULES:

        1. For greetings and casual conversation:
        - Respond naturally and conversationally.
        - Do NOT search or discuss inventory unless the user asks about it.
        - Example:
            User: "Hi"
            Assistant: "Hey! 👋 How can I help you today?"

        2. For general questions:
        - Answer using your general knowledge.
        - Do not force the company knowledge base into the answer.

        3. For company/product-specific questions:
        - Use the supplied company knowledge.
        - Focus ONLY on the product or topic the user asked about.
        - Do NOT introduce other similar products unless the user asks for comparisons or alternatives.
        - If the user asks about ESP32-CAM, answer specifically about ESP32-CAM.
        - Do not start discussing ESP32 DevKit, ESP8266, or other variants unless relevant to the question.

        4. For inventory questions:
        - LIVE INVENTORY is the source of truth.
        - Never invent stock quantities.
        - Explain inventory information naturally instead of dumping raw database data.

        5. For combined questions:
        - Combine company knowledge with live inventory information when both are supplied.

        6. If required information is unavailable:
        - Clearly say that the information is unavailable.
        - Never make up facts.

        7. Keep answers concise, natural and conversational.
        - Avoid unnecessary product lists.
        - Answer the exact question first.
        - Add useful information only when relevant.

        COMPANY KNOWLEDGE:
        {context or "No relevant company documentation was retrieved."}

        LIVE INVENTORY:
        {inventory_context or "No live inventory information was requested or retrieved."}

        USER QUESTION:
        {question}
        """
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        return text.strip() if text else None
    except Exception:
        return None


def answer_question(question: str, inventory_context: str = "") -> dict[str, Any]:
    docs = KB.search(question)
    context = "\n\n".join(f"[{d['source']}]\n{d['text']}" for d in docs)
    answer = _gemini_answer(question, context, inventory_context)

    if answer:
        return {"answer": answer, "sources": [d["source"] for d in docs], "mode": "gemini_rag"}

    # Useful fallback when no LLM key is configured.
    if docs:
        return {
            "answer": (
                "I found this relevant information in the knowledge base:\n\n"
                + "\n\n".join(f"• {d['text']}" for d in docs)
            ),
            "sources": [d["source"] for d in docs],
            "mode": "rag_fallback",
        }

    return {
        "answer": (
            "I don't have enough information in the knowledge base to answer that "
            "reliably. Try a product/SKU name or ask an inventory question such as "
            "'Is ESP32-CAM in stock?'"
        ),
        "sources": [],
        "mode": "fallback",
    }