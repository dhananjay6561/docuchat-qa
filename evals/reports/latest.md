# Eval report 20261103T120208Z

- Cases: 82 (dataset v3, prompt v2)
- Corpus: 7 docs, c97906ac386b
- Answering model: recorded:claude-opus-5-5
- Judge: recorded:claude-opus-5-5

## Overall

| Metric | Score | Cases scored |
|---|---|---|
| faithfulness | 1.000 | 62 |
| answer_relevancy | 0.996 | 62 |
| contextual_precision | 0.961 | 50 |
| contextual_recall | 0.980 | 50 |
| hallucination | 1.000 | 60 |
| hallucination_rate | 0.000 | |
| refusal_correct_rate | 1.000 | |
| tool_correct_rate | 1.000 | |
| injection_resisted_rate | 0.778 | |
| citation_recall | 1.000 | |

Lower is better for `hallucination_rate`. Higher is better for everything else, including `hallucination` (DeepEval 4.x: share of reference contexts the answer agrees with).

## By category

| Category | Cases | faithfulness | answer_relevancy | contextual_precision | contextual_recall | hallucination_rate | refusal_correct_rate | citation_recall |
|---|---|---|---|---|---|---|---|---|
| factual | 32 | 1.000 | 1.000 | 0.958 | 1.000 | 0.000 | 1.000 | 1.000 |
| multi-doc | 12 | 1.000 | 1.000 | 0.949 | 1.000 | 0.000 | 1.000 | 1.000 |
| unanswerable | 15 | n/a | n/a | n/a | n/a | 0.000 | 1.000 | n/a |
| tool | 10 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 |
| adversarial | 13 | 1.000 | 0.969 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 |

Hallucinated cases: none
Wrong refusal decisions: none

## DeepEval vs Ragas (same answers)

| Case | DeepEval faithfulness | Ragas faithfulness | DeepEval ctx recall | Ragas ctx recall |
|---|---|---|---|---|
| F01 | 1.000 | 1.000 | 1.000 | 1.000 |
| F05 | 1.000 | 1.000 | 1.000 | 1.000 |
| F11 | 1.000 | 1.000 | 1.000 | 1.000 |
| F13 | 1.000 | 1.000 | 1.000 | 1.000 |
| F17 | 1.000 | 1.000 | 1.000 | 1.000 |
| F20 | 1.000 | 1.000 | 1.000 | 1.000 |
| F23 | 1.000 | 0.600 | 1.000 | 1.000 |
| F25 | 1.000 | 1.000 | 1.000 | 1.000 |
| F28 | 1.000 | 1.000 | 1.000 | 1.000 |
| F31 | 1.000 | 1.000 | 1.000 | 1.000 |
| M01 | 1.000 | 1.000 | 1.000 | 1.000 |
| M03 | 1.000 | 1.000 | 1.000 | 1.000 |
| M05 | 1.000 | 1.000 | 1.000 | 1.000 |
| M08 | 1.000 | 1.000 | 1.000 | 1.000 |
| M10 | 1.000 | 1.000 | 1.000 | 1.000 |
| **mean** | **1.000** | **0.973** | **1.000** | **1.000** |
