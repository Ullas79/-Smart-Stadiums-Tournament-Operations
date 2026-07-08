"""In-memory vector RAG store over stadium knowledge documents.

Uses Google Gemini embeddings when an API key is available; falls back to a
deterministic keyword/TF-IDF-ish ranking so the assistant still works offline
(in tests and demos without network). The interface is intentionally simple:
`search(query, k)` returns the top-k doc dicts.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..core.config import settings
from .docs import KNOWLEDGE_DOCS

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(t, 0.0) for t, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class KnowledgeStore:
    """RAG store with embedding-first retrieval and a keyword fallback."""

    def __init__(self, docs: list[dict[str, str]] | None = None) -> None:
        self.docs = docs if docs is not None else list(KNOWLEDGE_DOCS)
        self._vectors: list[list[float]] | None = None
        self._tfidf: list[dict[str, float]] = []
        self._idf: dict[str, float] = {}
        self._client = None
        self._build_tfidf()

    # ---- indexing --------------------------------------------------------
    def _build_tfidf(self) -> None:
        doc_tokens = [_tokenize(d["text"]) for d in self.docs]
        n = len(self.docs) or 1
        df: Counter[str] = Counter()
        for toks in doc_tokens:
            for t in set(toks):
                df[t] += 1
        self._idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
        self._tfidf = []
        for toks in doc_tokens:
            tf = Counter(toks)
            total = len(toks) or 1
            vec = {t: (c / total) * self._idf.get(t, 0.0) for t, c in tf.items()}
            self._tfidf.append(vec)

    async def _ensure_embeddings(self) -> bool:
        """Try to embed all docs with Gemini. Returns True if available."""
        if self._vectors is not None:
            return True
        if not settings.google_api_key or settings.google_api_key.startswith("test"):
            return False
        try:
            from google import genai
            from google.genai import types

            if self._client is None:
                self._client = genai.Client(api_key=settings.google_api_key)
            texts = [f"{d['title']}: {d['text']}" for d in self.docs]
            resp = await self._client.aio.models.embed_content(
                model="gemini-embedding-001",
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            self._vectors = [list(e) for e in resp.embeddings]
            return True
        except Exception:
            # Network/auth failure -> fall back to keyword ranking.
            self._vectors = None
            return False

    async def _embed_query(self, query: str) -> list[float] | None:
        if self._client is None or self._vectors is None:
            return None
        try:
            from google import genai  # noqa: F401
            from google.genai import types

            resp = await self._client.aio.models.embed_content(
                model="gemini-embedding-001",
                contents=[query],
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            )
            return list(resp.embeddings[0])
        except Exception:
            return None

    # ---- query -----------------------------------------------------------
    async def search(self, query: str, k: int = 3) -> list[dict[str, str]]:
        if await self._ensure_embeddings():
            qv = await self._embed_query(query)
            if qv is not None:
                scored = []
                for i, dv in enumerate(self._vectors or []):
                    scored.append((self._dot(qv, dv), i))
                scored.sort(reverse=True)
                return [self.docs[i] for _, i in scored[:k] if _ >= 0]
        # keyword fallback
        qv = self._query_tfidf(query)
        scored = sorted(((_cosine(qv, tv), i) for i, tv in enumerate(self._tfidf)), reverse=True)
        return [self.docs[i] for s, i in scored[:k] if s > 0]

    def _query_tfidf(self, query: str) -> dict[str, float]:
        toks = _tokenize(query)
        tf = Counter(toks)
        total = len(toks) or 1
        return {t: (c / total) * self._idf.get(t, 0.0) for t, c in tf.items()}

    def search_sync(self, query: str, k: int = 3) -> list[dict[str, str]]:
        """Synchronous keyword retrieval (no network). Used by tool handlers
        that may run inside an existing event loop, and by tests."""
        qv = self._query_tfidf(query)
        scored = sorted(((_cosine(qv, tv), i) for i, tv in enumerate(self._tfidf)), reverse=True)
        return [self.docs[i] for s, i in scored[:k] if s > 0]


    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=False))
