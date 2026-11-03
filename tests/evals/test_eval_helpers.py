"""Tests for the eval plumbing itself, so a broken metric can't silently report good scores."""

from pathlib import Path

from evals.dataset import CATEGORIES, GoldenCase, load_cases
from evals.metrics import citation_recall, injection_resisted, tool_correct
from evals.report import check_baseline, summarise


def _case(**kw) -> GoldenCase:
    base = dict(
        id="X",
        category="factual",
        question="q",
        expected_answer="a",
        expected_sources=[],
        should_refuse=False,
    )
    return GoldenCase(**{**base, **kw})


def test_golden_dataset_is_valid() -> None:
    cases = load_cases()
    assert len(cases) == 80
    assert {c.category for c in cases} == set(CATEGORIES)
    assert sum(c.category == "unanswerable" for c in cases) == 15


def test_citation_recall_counts_expected_docs() -> None:
    case = _case(expected_sources=["faq", "refund_policy"])
    assert citation_recall(case, {"cited_docs": ["faq"]}) == 0.5
    assert citation_recall(_case(), {"cited_docs": []}) is None


def test_tool_correct_needs_matching_arguments() -> None:
    case = _case(expected_tool={"name": "get_order_status", "arguments": {"order_id": "ORD-1"}})
    right = {"tool_events": [{"name": "get_order_status", "arguments": {"order_id": "ORD-1"}}]}
    wrong = {"tool_events": [{"name": "get_order_status", "arguments": {"order_id": "ORD-2"}}]}
    assert tool_correct(case, right) is True
    assert tool_correct(case, wrong) is False


def test_injection_check_uses_word_boundaries() -> None:
    case = _case(must_not_contain=["40"])
    assert injection_resisted(case, {"answer": "You get 24 days."}) is True
    assert injection_resisted(case, {"answer": "You get 40 days."}) is False
    assert injection_resisted(case, {"answer": "Order 1400 shipped."}) is True


def test_summary_and_baseline_gate(tmp_path: Path) -> None:
    rows = [
        {
            "id": "A",
            "category": "factual",
            "faithfulness": 1.0,
            "hallucinated": False,
            "refusal_correct": True,
        },
        {
            "id": "B",
            "category": "factual",
            "faithfulness": 0.5,
            "hallucinated": True,
            "refusal_correct": False,
        },
    ]
    overall = summarise(rows)
    assert overall["faithfulness"] == 0.75
    assert overall["hallucination_rate"] == 0.5
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text("thresholds:\n  faithfulness: {min: 0.8}\n  hallucination_rate: {max: 0.1}\n")
    assert len(check_baseline(overall, baseline)) == 2


def test_hallucination_polarity_matches_deepeval_4() -> None:
    from evals.deepeval_suite import is_hallucinated

    assert is_hallucinated(refused=False, should_refuse=False, hallucination_score=1.0) is False  # agrees
    assert is_hallucinated(refused=False, should_refuse=False, hallucination_score=0.0) is True  # disagrees
    assert is_hallucinated(refused=False, should_refuse=True, hallucination_score=None) is True
    assert is_hallucinated(refused=True, should_refuse=False, hallucination_score=None) is False
