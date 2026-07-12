"""In-memory vector RAG store over stadium knowledge documents.

Uses Google Gemini embeddings when an API key is available; falls back to a
deterministic keyword/TF-IDF-ish ranking so the assistant still works offline
(in tests and demos without network). The interface is intentionally simple:
`search(query, k)` returns the top-k doc dicts.
"""
from __future__ import annotations

from collections import Counter
import logging
import math
import re
from typing import Any

from ..core.config import settings
from .docs import KNOWLEDGE_DOCS

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Tokenizes a string into lowercase alphanumeric words.

    Args:
        text: The raw string to tokenize.

    Returns:
        A list of lowercase word tokens.
    """
    return _WORD_RE.findall(text.lower())


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Computes the cosine similarity between two TF-IDF vector dicts.

    Args:
        a: The first token-weight dictionary.
        b: The second token-weight dictionary.

    Returns:
        The cosine similarity score as a float.
    """
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(t, 0.0) for t, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class KnowledgeStore:
    """RAG store with embedding-first retrieval and a keyword fallback."""

    def __init__(self, docs: list[dict[str, str]] | None = None) -> None:
        """Initializes the KnowledgeStore.

        Args:
            docs: Optional list of document dicts containing 'title' and 'text'.
        """
        self.docs = docs if docs is not None else list(KNOWLEDGE_DOCS)
        self._vectors: list[list[float]] | None = None
        self._tfidf: list[dict[str, float]] = []
        self._idf: dict[str, float] = {}
        self._client: Any | None = None
        self._search_cache: dict[tuple[str, int, bool], list[dict[str, str]]] = {}
        self._build_tfidf()

    # ---- indexing --------------------------------------------------------
    def _build_tfidf(self) -> None:
        """Builds TF-IDF index for the stored documents."""
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
        """Ensures document embeddings are computed via Gemini.

        If embeddings are not yet generated, attempts to call the Gemini API
        to generate and store them. Falls back to keyword retrieval on failure.

        Returns:
            True if embeddings were successfully loaded or generated, False otherwise.
        """
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
        except Exception as e:
            # Network/auth failure -> fall back to keyword ranking.
            logger.warning("Gemini embedding generation failed: %s", e)
            self._vectors = None
            return False

    async def _embed_query(self, query: str) -> list[float] | None:
        """Generates an embedding vector for the query string using Gemini.

        Args:
            query: The search query string.

        Returns:
            The query embedding vector as a list of floats, or None on failure.
        """
        if self._client is None or self._vectors is None:
            return None
        try:
            from google.genai import types

            resp = await self._client.aio.models.embed_content(
                model="gemini-embedding-001",
                contents=[query],
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            )
            return list(resp.embeddings[0])
        except Exception as e:
            logger.warning("Gemini query embedding failed: %s", e)
            return None

    # ---- query -----------------------------------------------------------
    async def search(self, query: str, k: int = 3) -> list[dict[str, str]]:
        """Searches the store for documents matching the query.

        First attempts semantic search via embeddings, falling back to TF-IDF.

        Args:
            query: The search query string.
            k: The number of top documents to return.

        Returns:
            A list of the top k document dictionaries.
        """
        has_embeddings = await self._ensure_embeddings()
        cache_key = (query, k, has_embeddings)
        if cache_key in self._search_cache:
            # Return shallow copies of dicts to prevent external mutation
            return [dict(d) for d in self._search_cache[cache_key]]

        if has_embeddings:
            qv = await self._embed_query(query)
            if qv is not None:
                scored = []
                for i, dv in enumerate(self._vectors or []):
                    scored.append((self._dot(qv, dv), i))
                scored.sort(reverse=True)
                results = [self.docs[i] for _, i in scored[:k] if _ >= 0]
                if len(self._search_cache) >= 1024:
                    self._search_cache.clear()
                self._search_cache[cache_key] = results
                return [dict(d) for d in results]

        # keyword fallback
        qv = self._query_tfidf(query)
        scored = sorted(((_cosine(qv, tv), i) for i, tv in enumerate(self._tfidf)), reverse=True)
        results = [self.docs[i] for s, i in scored[:k] if s > 0]
        if len(self._search_cache) >= 1024:
            self._search_cache.clear()
        self._search_cache[cache_key] = results
        return [dict(d) for d in results]

    def _query_tfidf(self, query: str) -> dict[str, float]:
        """Computes the TF-IDF representation of a query.

        Args:
            query: The query string to compute TF-IDF for.

        Returns:
            A dictionary mapping tokens to TF-IDF weights.
        """
        toks = _tokenize(query)
        tf = Counter(toks)
        total = len(toks) or 1
        return {t: (c / total) * self._idf.get(t, 0.0) for t, c in tf.items()}

    def search_sync(self, query: str, k: int = 3) -> list[dict[str, str]]:
        """Synchronously searches the store using TF-IDF keyword ranking.

        Args:
            query: The search query string.
            k: The number of top documents to return.

        Returns:
            A list of the top k document dictionaries.
        """
        cache_key = (query, k, False)
        if cache_key in self._search_cache:
            # Return shallow copies of dicts to prevent external mutation
            return [dict(d) for d in self._search_cache[cache_key]]

        qv = self._query_tfidf(query)
        scored = sorted(((_cosine(qv, tv), i) for i, tv in enumerate(self._tfidf)), reverse=True)
        results = [self.docs[i] for s, i in scored[:k] if s > 0]
        if len(self._search_cache) >= 1024:
            self._search_cache.clear()
        self._search_cache[cache_key] = results
        return [dict(d) for d in results]

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        """Computes the dot product of two vectors.

        Args:
            a: The first float vector.
            b: The second float vector.

        Returns:
            The dot product of the two vectors.
        """
        return sum(x * y for x, y in zip(a, b, strict=False))

