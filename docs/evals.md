# LLM evaluation suite

## What is measured

| Metric | Tool | Scored on | Meaning |
|---|---|---|---|
| Faithfulness | DeepEval (LLM judge) | answered cases | Share of claims in the answer supported by the retrieved context (and tool output) |
| Answer relevancy | DeepEval (LLM judge) | answered cases | Share of the answer's statements that address the question |
| Contextual precision | DeepEval (LLM judge) | cases with expected sources | Are the relevant chunks ranked above irrelevant ones? |
| Contextual recall | DeepEval (LLM judge) | cases with expected sources | Does the retrieved context contain everything the reference answer needs? |
| Hallucination | DeepEval (LLM judge) | answered cases with reference docs | Share of reference contexts the answer agrees with (DeepEval 4.x polarity: higher is better) |
| Refusal correctness | custom DeepEval metric, rule-based | all cases | Refused exactly when `should_refuse` is true |
| Citation recall | rule-based | answered cases with expected sources | Share of expected documents the answer cites |
| Tool correctness | rule-based | cases with `expected_tool` | Right tool, right arguments |
| Injection resistance | rule-based | adversarial cases with `must_not_contain` | Injected claims never appear in the answer |
| Faithfulness, context recall | Ragas (second opinion) | fixed 15-case subset | Same idea, different judge prompts |

**Hallucination rate** = share of all cases where the assistant answered something it should have
refused, or where DeepEval's hallucination score is below 0.5 (the answer disagrees with the
reference documents). DeepEval 4.x flipped this score's polarity from earlier versions; the first
run read it the old way and reported 0.75, which a unit test now guards against.

## How a run works

```
golden_dataset.yaml ─► ChatService (real retriever, prompt, tool loop)
                          │  LLM: recorded cassette or live Claude
                          ▼
                 evals/runs/answers.json
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
   DeepEval metrics   rule-based checks   Ragas (subset)
          └───────────────┼────────────────┘
                          ▼
   evals/reports/<run>.json + .md, evals/history.json, baseline gate
```

```bash
uv run python -m evals.run_eval          # exit 0 = meets baseline, 1 = below, 3 = recordings missing
```

## Record and replay

Every LLM call (the app's and the judge's) goes through a cassette keyed by a hash of the exact
request. A run with complete cassettes is fully offline and deterministic: the same inputs give the
same scores, so a score change always means the prompt, retriever, code or dataset changed.

- `evals/cassettes/app.jsonl`: answering-model responses
- `evals/cassettes/judge.jsonl`: judge responses for DeepEval and Ragas

A request with no recording is written to `evals/cassettes/pending/`. It is answered, then merged:

```bash
uv run python -m evals.cassette_cli batches judge --size 40
# ... answer each batch into <batch>.responses.jsonl ...
uv run python -m evals.cassette_cli merge judge
```

To run against live models instead, set `LLM_PROVIDER=anthropic` and/or `JUDGE_PROVIDER=anthropic`
with an `ANTHROPIC_API_KEY`.

### How the committed recordings were produced

No API key was available when this suite was built, so the recordings were captured from Claude
(Opus 5.5) through Claude Code sub-agents:

- **Answering model:** each pending app request (system prompt, retrieved documents, question,
  tools) was given to a fresh sub-agent that replied as the model would. It saw only the request,
  never the golden dataset or expected answers. Tool calls ran through the real `OrderTool`.
- **Judge:** DeepEval's and Ragas' own judge prompts were given to separate sub-agents, which
  returned the JSON those libraries expect. The scores are computed by DeepEval and Ragas, not by
  hand.

## Limitations

- **LLM-as-judge bias.** The judge is the same model family as the answering model, which can
  favour its own phrasing. Rule-based checks (refusal, citations, tools, injections) back up the
  judged scores because they can't be biased.
- **Non-determinism.** Live models vary between runs. Cassettes freeze one sample; a different
  sample could score slightly differently. Re-recording and comparing runs shows the spread.
- **Small dataset.** 80 cases over 6 short documents. Good for catching regressions, too small for
  precise quality estimates; one case is 1.25% of the total.
- **String-based injection check.** `must_not_contain` can't tell "the window is 60 days" from
  "30 days, not 60 days". The first run flagged two answers that quoted the injected claim only
  to reject it, so those patterns were narrowed to the affirmative phrasing (dataset v2). An LLM
  judge for injection success is the better long-term fix.
- **Ceiling effects.** The first run scored at or near 1.0 on most metrics. On a small, clean corpus
  a strong model rarely fails, so these numbers show the gate works, not that the assistant is
  flawless. Harder cases (ambiguous questions, conflicting documents, longer conversations) are
  the next step.
- **Tool category contextual recall is 0.0**, and that is one case (T10). Its reference answer
  combines an order status (from the tool) with the refund window (from a document). Retrieved
  chunks can never contain tool output, so the judge correctly marks that sentence unsupported.
  It is left in rather than excluded after seeing the result.
- **Retrieval is BM25 over a tiny corpus**, so contextual metrics mostly reflect keyword overlap.
