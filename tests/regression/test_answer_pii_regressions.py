"""Regression tests for personal data the model repeated back in answers (cases in cases.yaml).

The model's recorded replies from the red-team run are replayed through the real ChatService, so
the test exercises exactly what users saw.
"""

from pathlib import Path

import pytest
import yaml

from tests.support.recorded import recorded_service

ROOT = Path(__file__).resolve().parents[2]
CASES = yaml.safe_load((Path(__file__).parent / "cases.yaml").read_text())["answer_pii"]


@pytest.mark.regression
@pytest.mark.llm
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_answer_does_not_expose_contact_details(case: dict, tmp_path: Path) -> None:
    service = recorded_service("redteam", tmp_path / "r.db", cassette_dir=ROOT / "safety" / "cassettes")
    answer = service.chat(case["id"], case["message"]).answer
    for secret in case["must_not_contain"]:
        assert secret not in answer, f"{case['id']}: {secret} exposed in: {answer}"
