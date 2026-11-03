"""Loads the markdown docs and splits them into chunks small enough to retrieve precisely."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    id: str  # "<doc>#<n>", stable so tests and the golden dataset can reference it
    doc: str  # file name without extension
    text: str


def load_chunks(docs_dir: Path, max_words: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(_split(path.stem, path.read_text(encoding="utf-8"), max_words))
    if not chunks:
        raise FileNotFoundError(f"No .md documents found in {docs_dir}")
    return chunks


def _split(doc: str, text: str, max_words: int) -> list[Chunk]:
    # Paragraph-based chunking keeps sentences and list items together, which reads better as a
    # cited snippet than fixed-size windows that cut mid-sentence.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    title = paragraphs[0].lstrip("# ") if paragraphs and paragraphs[0].startswith("#") else doc
    groups: list[list[str]] = [[]]
    for para in paragraphs:
        size = sum(len(p.split()) for p in groups[-1])
        if groups[-1] and size + len(para.split()) > max_words:
            groups.append([])
        groups[-1].append(para)
    # Prefixing the doc title gives every chunk the keywords of its document (e.g. "Refund Policy").
    return [
        Chunk(id=f"{doc}#{i}", doc=doc, text="\n\n".join(group if i == 0 else [f"({title})", *group]))
        for i, group in enumerate(groups)
    ]
