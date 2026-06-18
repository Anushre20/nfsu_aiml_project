from sentence_transformers import SentenceTransformer
import faiss
import numpy as np


class Memory:

    def __init__(self, max_turns=6):

        self.max_turns = max_turns

        # Short term memory
        self.short_term = []

        # Embedding model
        self.embedder = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

        # MiniLM dimension = 384
        self.index = faiss.IndexFlatIP(384)

        # Stores actual text summaries
        self.documents = []

    # -------------------------
    # SHORT TERM MEMORY
    # -------------------------

    def add_short_term(self, role, content):

        self.short_term.append(
            (role, content)
        )

        if len(self.short_term) > self.max_turns:
            self.short_term.pop(0)

    def get_short_term(self):
        return self.short_term

    # -------------------------
    # LONG TERM MEMORY
    # -------------------------

    def add_long_term(self, text):

        embedding = self.embedder.encode(
            [text]
        )

        embedding = np.array(
            embedding,
            dtype=np.float32
        )

        faiss.normalize_L2(embedding)

        self.index.add(embedding)

        self.documents.append(text)

    def retrieve_long_term(self, query, k=3):

        if len(self.documents) == 0:
            return []

        query_embedding = self.embedder.encode(
            [query]
        )

        query_embedding = np.array(
            query_embedding,
            dtype=np.float32
        )

        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(
            query_embedding,
            min(k, len(self.documents))
        )

        results = []

        for idx in indices[0]:
            if idx != -1:
                results.append(
                    self.documents[idx]
                )

        return results