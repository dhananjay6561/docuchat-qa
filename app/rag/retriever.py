"""BM25 keyword retriever.

Chosen over embeddings for this project because it needs no model download, is fully
deterministic (same query -> same chunks, which keeps eval runs comparable) and is easy to explain.
`Retriever` is an interface so an embedding retriever can be dropped in and compared later.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.rag.loader import Chunk
from app.rag.text import tokenize


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Retriever(ABC):
    @abstractmethod
    def search(self, query: str, k: int) -> list[Hit]: ...


class BM25Retriever(Retriever):
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._index = BM25Okapi([tokenize(c.text) for c in chunks])

    def search(self, query: str, k: int) -> list[Hit]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._index.get_scores(tokens)
        ranked = sorted(zip(self.chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        # A zero score means no keyword overlap at all, so passing it to the LLM would only add noise.
        return [Hit(chunk, float(score)) for chunk, score in ranked[:k] if score > 0]
