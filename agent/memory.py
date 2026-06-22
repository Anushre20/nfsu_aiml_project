import functools
from pathlib import Path

import faiss
import numpy as np


@functools.lru_cache(maxsize=None)
def _get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


class Memory:

    MAX_DOCS = 50

    def __init__(self, max_turns=6):
        self.max_turns = max_turns
        self.short_term = []
        self._embedder = None
        self.documents = []
        self.index = None

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = _get_embedder()
            self.dimension = self._embedder.get_embedding_dimension()
            self.index = faiss.IndexFlatIP(self.dimension)
        return self._embedder

    def add_short_term(self, role, content):
        self.short_term.append((role, content))
        if len(self.short_term) > self.max_turns:
            self.short_term.pop(0)

    def get_short_term(self):
        return self.short_term

    def _ensure_index(self):
        if self.index is None:
            self.embedder
        return self.index

    def add_long_term(self, text):
        self._ensure_index()
        embedding = self.embedder.encode([text])
        embedding = np.array(embedding, dtype=np.float32)
        faiss.normalize_L2(embedding)
        self.index.add(embedding)
        self.documents.append(text)
        if len(self.documents) > self.MAX_DOCS:
            ids_to_remove = np.array([0])
            self.index.remove_ids(ids_to_remove)
            self.documents.pop(0)

    def retrieve_long_term(self, query, k=3):
        if self.index is None or len(self.documents) == 0:
            return None
        self._ensure_index()
        query_embedding = self.embedder.encode([query])
        query_embedding = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(query_embedding)
        scores, indices = self.index.search(
            query_embedding,
            min(k, len(self.documents))
        )
        results = []
        for idx in indices[0]:
            if idx != -1:
                results.append(self.documents[idx])
        return results

    def reset_short_term(self):
        self.short_term.clear()

    def reset(self):
        self.short_term.clear()
        self.documents.clear()
        if self.index is not None:
            self.index.reset()

    def memory_stats(self):
        return {
            "short_term_turns": len(self.short_term),
            "long_term_docs": len(self.documents) if self.index else 0,
            "dimension": self.dimension if self.index else None,
            "max_docs": self.MAX_DOCS,
            "max_turns": self.max_turns,
        }
