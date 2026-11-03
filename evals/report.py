"""Stage 4: turn per-case scores into a summary, a markdown report, a history entry and a gate."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from evals.dataset import CATEGORIES

EVALS_DIR = Path(__file__).resolve().parent
REPORTS_DIR = EVALS_DIR / "reports"
HISTORY_PATH = EVALS_DIR / "history.json"
BASELINE_PATH = EVALS_DIR / "baseline.yaml"

LLM_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "contextual_precision",
    "contextual_recall",
    "hallucination",
)
RATE_CHECKS = ("refusal_correct", "tool_correct", "injection_resisted")


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(mean(present), 4) if present else None


def _rate(values: list[bool | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 4) if present else None


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"cases": len(rows)}
    for metric in LLM_METRICS:
        values = [r.get(metric) for r in rows]
        summary[metric] = _avg(values)
        summary[f"{metric}_n"] = sum(v is not None for v in values)
    for check in RATE_CHECKS:
        summary[f"{check}_rate"] = _rate([r.get(check) for r in rows])
    summary["citation_recall"] = _avg([r.get("citation_recall") for r in rows])
    summary["hallucination_rate"] = _rate([r["hallucinated"] for r in rows])
    summary["hallucinated_cases"] = [r["id"] for r in rows if r["hallucinated"]]
    summary["failed_refusal_cases"] = [r["id"] for r in rows if not r["refusal_correct"]]
    return summary


def build_report(rows: list[dict], ragas_rows: list[dict], meta: dict[str, Any]) -> dict[str, Any]:
    by_category = {c: summarise([r for r in rows if r["category"] == c]) for c in CATEGORIES}
    comparison = []
    deepeval_by_id = {r["id"]: r for r in rows}
    for rg in ragas_rows:
        de = deepeval_by_id.get(rg["id"], {})
        comparison.append(
            {
                "id": rg["id"],
                "deepeval_faithfulness": de.get("faithfulness"),
                "ragas_faithfulness": rg["faithfulness"],
                "deepeval_contextual_recall": de.get("contextual_recall"),
                "ragas_context_recall": rg["context_recall"],
            }
        )
    return {
        "meta": meta,
        "overall": summarise(rows),
        "by_category": by_category,
        "ragas_comparison": comparison,
        "cases": rows,
    }


def fingerprint(answers: list[dict], meta: dict[str, Any]) -> str:
    """Identifies what was evaluated, so re-running the same cassette doesn't add a fake trend point."""
    payload = json.dumps(
        {
            "answers": answers,
            "prompt": meta["prompt_version"],
            "dataset": meta["dataset_version"],
            "judge": meta["judge"],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def history_metrics(report: dict[str, Any]) -> dict[str, Any]:
    overall = report["overall"]
    keys = (
        "cases",
        "hallucination_rate",
        "refusal_correct_rate",
        "injection_resisted_rate",
        "tool_correct_rate",
    )
    return {**{k: overall[k] for k in keys}, **{m: overall[m] for m in LLM_METRICS}}


def append_history(report: dict[str, Any], fp: str, path: Path = HISTORY_PATH) -> bool:
    history = json.loads(path.read_text()) if path.exists() else []
    if history and history[-1]["fingerprint"] == fp:
        return False
    history.append(
        {
            "run_id": report["meta"]["run_id"],
            "fingerprint": fp,
            "prompt_version": report["meta"]["prompt_version"],
            "dataset_version": report["meta"]["dataset_version"],
            "corpus": report["meta"].get("corpus"),
            "provider": report["meta"]["provider"],
            "judge": report["meta"]["judge"],
            **history_metrics(report),
        }
    )
    path.write_text(json.dumps(history, indent=2) + "\n")
    return True


def check_baseline(overall: dict[str, Any], path: Path = BASELINE_PATH) -> list[str]:
    """Returns human-readable failures; an empty list means the gate passes."""
    if not path.exists():
        return []
    rules = yaml.safe_load(path.read_text())["thresholds"]
    failures = []
    for metric, rule in rules.items():
        value = overall.get(metric)
        if value is None:
            failures.append(f"{metric}: no score produced")
        elif "min" in rule and value < rule["min"]:
            failures.append(f"{metric}: {value} < min {rule['min']}")
        elif "max" in rule and value > rule["max"]:
            failures.append(f"{metric}: {value} > max {rule['max']}")
    return failures


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def to_markdown(report: dict[str, Any]) -> str:
    meta, overall = report["meta"], report["overall"]
    cols = [
        "faithfulness",
        "answer_relevancy",
        "contextual_precision",
        "contextual_recall",
        "hallucination_rate",
        "refusal_correct_rate",
        "citation_recall",
    ]
    lines = [
        f"# Eval report {meta['run_id']}",
        "",
        f"- Cases: {overall['cases']} ({meta.get('subset', 'full')} set; dataset v{meta['dataset_version']}, "
        f"prompt v{meta['prompt_version']})",
        f"- Corpus: {meta.get('corpus', 'n/a')}",
        f"- Answering model: {meta['provider']}",
        f"- Judge: {meta['judge']}",
        "",
        "## Overall",
        "",
        "| Metric | Score | Cases scored |",
        "|---|---|---|",
    ]
    for m in LLM_METRICS:
        lines.append(f"| {m} | {_fmt(overall[m])} | {overall[f'{m}_n']} |")
    for key in (
        "hallucination_rate",
        "refusal_correct_rate",
        "tool_correct_rate",
        "injection_resisted_rate",
        "citation_recall",
    ):
        lines.append(f"| {key} | {_fmt(overall[key])} | |")
    lines += [
        "",
        "Lower is better for `hallucination_rate`. Higher is better for everything else, including "
        "`hallucination` (DeepEval 4.x: share of reference contexts the answer agrees with).",
        "",
        "## By category",
        "",
        "| Category | Cases | " + " | ".join(cols) + " |",
        "|---|---|" + "---|" * len(cols),
    ]
    for cat, s in report["by_category"].items():
        lines.append(f"| {cat} | {s['cases']} | " + " | ".join(_fmt(s[c]) for c in cols) + " |")
    lines += [
        "",
        f"Hallucinated cases: {', '.join(overall['hallucinated_cases']) or 'none'}",
        f"Wrong refusal decisions: {', '.join(overall['failed_refusal_cases']) or 'none'}",
    ]
    if report["ragas_comparison"]:
        lines += [
            "",
            "## DeepEval vs Ragas (same answers)",
            "",
            "| Case | DeepEval faithfulness | Ragas faithfulness | DeepEval ctx recall | Ragas ctx recall |",
            "|---|---|---|---|---|",
        ]
        for row in report["ragas_comparison"]:
            lines.append(
                f"| {row['id']} | {_fmt(row['deepeval_faithfulness'])} | {_fmt(row['ragas_faithfulness'])} "
                f"| {_fmt(row['deepeval_contextual_recall'])} | {_fmt(row['ragas_context_recall'])} |"
            )
        means = {
            k: _avg([r[k] for r in report["ragas_comparison"]])
            for k in report["ragas_comparison"][0]
            if k != "id"
        }
        lines.append("| **mean** | " + " | ".join(f"**{_fmt(v)}**" for v in means.values()) + " |")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    smoke = report["meta"].get("subset") == "smoke"
    name = f"{report['meta']['run_id']}{'-smoke' if smoke else ''}"
    (REPORTS_DIR / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
    markdown = to_markdown(report)
    (REPORTS_DIR / f"{name}.md").write_text(markdown)
    (REPORTS_DIR / ("smoke-latest.md" if smoke else "latest.md")).write_text(markdown)
    return REPORTS_DIR / f"{name}.md"


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
