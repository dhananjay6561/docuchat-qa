"""Runs the whole eval: answers -> DeepEval -> Ragas -> report -> history -> baseline gate.

    uv run python -m evals.run_eval

Exit codes: 0 = all scores meet baseline, 1 = below baseline, 3 = recordings missing
(the requests are listed in evals/cassettes/pending/ and can be answered, then merged).
"""

import argparse
import hashlib
import os
import sys

# Evals replay recordings by default; set LLM_PROVIDER=anthropic / JUDGE_PROVIDER=anthropic to go live.
os.environ.setdefault("LLM_PROVIDER", "recorded")

import yaml  # noqa: E402

from app.config import Settings  # noqa: E402
from evals import deepeval_suite, generate_answers, ragas_suite, report  # noqa: E402
from evals.dataset import DATASET_PATH, SMOKE_IDS, load_cases  # noqa: E402
from evals.judges import JUDGE_MODEL, build_deepeval_judge, build_ragas_judge, judge_cassette  # noqa: E402

PENDING_EXIT = 3


def corpus_fingerprint(settings: Settings) -> str:
    """Short hash of every document, so a report shows when the knowledge base changed."""
    digest = hashlib.sha256()
    for path in sorted(settings.docs_dir.glob("*.md")):
        digest.update(path.name.encode() + path.read_bytes())
    return digest.hexdigest()[:12]


def _stop_for_recordings(stage: str, missing: int) -> None:
    print(f"[{stage}] {missing} case(s) need recorded responses. See evals/cassettes/pending/.")
    sys.exit(PENDING_EXIT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-ragas", action="store_true")
    parser.add_argument(
        "--subset",
        choices=["full", "smoke"],
        default="full",
        help="smoke = 20-case PR subset, no Ragas, no history",
    )
    args = parser.parse_args()
    smoke = args.subset == "smoke"

    settings = Settings()
    cases = load_cases()
    if smoke:
        cases = [c for c in cases if c.id in SMOKE_IDS]
    print(f"Loaded {len(cases)} golden cases ({args.subset}). Provider: {settings.llm_provider}")

    answers, missing = generate_answers.generate(cases, settings)
    if missing:
        _stop_for_recordings("answers", missing)
    if not smoke:  # answers.json always holds the latest FULL run
        generate_answers.save(answers)

    cassette = judge_cassette()
    rows, incomplete = deepeval_suite.run(cases, answers, build_deepeval_judge(cassette), settings)
    ragas_rows: list[dict] = []
    if not (args.skip_ragas or smoke):
        ragas_rows, ragas_incomplete = ragas_suite.run(cases, answers, build_ragas_judge(cassette))
        incomplete += ragas_incomplete
    if incomplete:
        _stop_for_recordings("judge", incomplete)

    meta = {
        "run_id": report.new_run_id(),
        "provider": f"{settings.llm_provider}:{settings.llm_model}",
        "judge": f"{os.getenv('JUDGE_PROVIDER', 'recorded')}:{JUDGE_MODEL}",
        "prompt_version": answers[0]["prompt_version"],
        "dataset_version": yaml.safe_load(DATASET_PATH.read_text())["version"],
        "subset": args.subset,
        "corpus": f"{len(list(settings.docs_dir.glob('*.md')))} docs, {corpus_fingerprint(settings)}",
    }
    full = report.build_report(rows, ragas_rows, meta)
    path = report.write_report(full)
    # Only full runs form the trend; a 20-case subset isn't comparable with an 82-case run.
    added = False if smoke else report.append_history(full, report.fingerprint(answers, meta))
    print(f"Report: {path.relative_to(path.parents[2])}  (history {'updated' if added else 'unchanged'})")

    overall = full["overall"]
    for key in (
        "faithfulness",
        "answer_relevancy",
        "contextual_precision",
        "contextual_recall",
        "hallucination_rate",
        "refusal_correct_rate",
    ):
        print(f"  {key:22} {overall[key]}")

    failures = report.check_baseline(overall)
    if failures:
        print("BELOW BASELINE:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("All scores meet the baseline.")


if __name__ == "__main__":
    main()
