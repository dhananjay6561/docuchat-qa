"""Stage 3: a second opinion from Ragas on a fixed subset of the same answers.

Two different eval libraries use different judge prompts. Comparing their faithfulness and
context-recall scores on the same cases shows how much a score depends on the tool measuring it.
"""

import asyncio
import math
from typing import Any

from ragas import SingleTurnSample
from ragas.llms.base import BaseRagasLLM
from ragas.metrics import Faithfulness, LLMContextRecall

from app.llm.cassette import CassetteMiss
from evals.dataset import GoldenCase

# Fixed subset (answerable, grounded in docs) so the comparison is like-for-like across runs.
RAGAS_CASE_IDS = (
    "F01", "F05", "F11", "F13", "F17", "F20", "F23", "F25", "F28", "F31",
    "M01", "M03", "M05", "M08", "M10",
)  # fmt: skip


def _score(metric: Any, sample: SingleTurnSample) -> float | None:
    try:
        value = asyncio.run(metric.single_turn_ascore(sample))
    except CassetteMiss:
        return None
    return None if value is None or math.isnan(value) else round(float(value), 4)


def run(
    cases: list[GoldenCase], answers: list[dict[str, Any]], judge: BaseRagasLLM
) -> tuple[list[dict], int]:
    by_id = {a["id"]: a for a in answers}
    faithfulness = Faithfulness(llm=judge)
    context_recall = LLMContextRecall(llm=judge)
    results, incomplete = [], 0
    for case in (c for c in cases if c.id in RAGAS_CASE_IDS):
        answer = by_id.get(case.id)
        if answer is None:
            incomplete += 1
            continue
        sample = SingleTurnSample(
            user_input=case.question,
            response=answer["answer"],
            reference=case.expected_answer,
            retrieved_contexts=[r["text"] for r in answer["retrieved"]] or ["(none)"],
        )
        row = {
            "id": case.id,
            "faithfulness": _score(faithfulness, sample),
            "context_recall": _score(context_recall, sample),
        }
        incomplete += row["faithfulness"] is None or row["context_recall"] is None
        results.append(row)
    return results, incomplete
