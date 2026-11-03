"""Guards the indirect-injection red-team tests: they only mean something if the poisoned document
is actually retrieved and shown to the model. If retrieval changes and stops surfacing it, these
fail instead of the red-team silently reporting a hollow pass."""

from pathlib import Path

import pytest
import yaml

from app.config import Settings
from app.rag.loader import load_chunks
from app.rag.retriever import BM25Retriever

CONFIG = yaml.safe_load((Path(__file__).resolve().parents[2] / "safety" / "promptfooconfig.yaml").read_text())
INDIRECT = [t["vars"] for t in CONFIG["tests"] if t["metadata"]["category"] == "prompt-injection-indirect"]


@pytest.mark.safety
@pytest.mark.parametrize("attack", INDIRECT, ids=[a["id"] for a in INDIRECT])
def test_poisoned_document_reaches_the_model(attack: dict) -> None:
    settings = Settings(_env_file=None)
    retriever = BM25Retriever(load_chunks(settings.docs_dir, settings.chunk_words))
    docs = [hit.chunk.doc for hit in retriever.search(attack["prompt"], settings.retrieval_top_k)]
    assert "supplier_notice" in docs


def test_poisoned_document_contains_an_injection() -> None:
    text = (Path(__file__).resolve().parents[2] / "data" / "docs" / "supplier_notice.md").read_text()
    assert "ignore all previous instructions" in text.lower()
