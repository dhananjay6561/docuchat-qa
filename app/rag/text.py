"""Shared tokenizer so the retriever and the mock LLM agree on what counts as a keyword."""

import re

WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

# Without this, "what is the..." would match every chunk and BM25 scores would be noise.
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it its me my of on or "
    "our should so that the their them there they this to us was we were what when where which "
    "who why will with you your about any get much many".split()
)


def _stem(word: str) -> str:
    # Minimal plural stemming so "refund" matches "refunds" without pulling in an NLP library.
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in WORD.findall(text.lower()) if w not in STOPWORDS]
