from app.config import Settings
from app.rag.loader import load_chunks
from app.rag.retriever import BM25Retriever


def _retriever(settings: Settings) -> BM25Retriever:
    return BM25Retriever(load_chunks(settings.docs_dir, settings.chunk_words))


def test_chunks_have_stable_ids(settings: Settings) -> None:
    chunks = load_chunks(settings.docs_dir, settings.chunk_words)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
    assert "refund_policy#0" in ids


def test_finds_the_right_document(settings: Settings) -> None:
    hits = _retriever(settings).search("How many days of annual leave do employees get?", k=3)
    assert hits[0].chunk.doc == "leave_policy"


def test_returns_nothing_for_unrelated_query(settings: Settings) -> None:
    assert _retriever(settings).search("quantum chromodynamics lattice", k=3) == []


def test_stopword_only_query_returns_nothing(settings: Settings) -> None:
    assert _retriever(settings).search("what is the", k=3) == []
