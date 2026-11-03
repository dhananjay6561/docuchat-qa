"""Loads and validates the golden dataset so a typo in the YAML fails loudly, not silently."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.yaml"
CATEGORIES = ("factual", "multi-doc", "unanswerable", "tool", "adversarial")

# 20-case smoke subset for pull requests: every category, plus the guardrail case (A12), so a PR
# gets a real quality signal in a fraction of the time. main and nightly runs use all cases.
SMOKE_IDS = (
    "F01", "F05", "F11", "F17", "F20", "F23", "F28", "F31",
    "M01", "M03", "M05",
    "U01", "U03", "U07", "U14",
    "T01", "T03", "T07",
    "A02", "A12",
)  # fmt: skip


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
