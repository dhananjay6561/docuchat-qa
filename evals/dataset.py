"""Loads and validates the golden dataset so a typo in the YAML fails loudly, not silently."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.yaml"
CATEGORIES = ("factual", "multi-doc", "unanswerable", "tool", "adversarial")


@dataclass(frozen=True)
class GoldenCase:
    id: str
    category: str
    question: str
    expected_answer: str
    expected_sources: list[str]
    should_refuse: bool
    expected_tool: dict[str, Any] | None = None
    must_not_contain: list[str] = field(default_factory=list)


def load_cases(path: Path = DATASET_PATH) -> list[GoldenCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = [GoldenCase(**item) for item in raw["cases"]]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ids in golden dataset")
    for case in cases:
        if case.category not in CATEGORIES:
            raise ValueError(f"{case.id}: unknown category {case.category!r}")
        if case.should_refuse and case.expected_sources:
            raise ValueError(f"{case.id}: a refusal case cannot expect sources")
    return cases
