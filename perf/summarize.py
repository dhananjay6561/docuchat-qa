"""Turns Locust's CSV output plus the app's log DB into a markdown performance report.

uv run python -m perf.summarize <csv_prefix> <log_db> <label>
"""

import csv
import sqlite3
import sys
from pathlib import Path

REPORTS = Path(__file__).resolve().parent / "reports"


def main(csv_prefix: str, db_path: str, label: str) -> None:
    rows = list(csv.DictReader(open(f"{csv_prefix}_stats.csv")))
    total = next(r for r in rows if r["Name"] == "Aggregated")
    chat_rows = [r for r in rows if r["Name"].startswith("/chat")]

    with sqlite3.connect(db_path) as conn:
        logged, avg_cost, avg_tokens, total_cost = conn.execute(
            "SELECT COUNT(*), AVG(estimated_cost), AVG(token_count), SUM(estimated_cost) FROM chat_logs"
        ).fetchone()

    requests = int(total["Request Count"])
    failures = int(total["Failure Count"])
    lines = [
        f"# Load test: {label}",
        "",
        "| Metric | Value |",
        "|---|---|",
        "| Users | ramped 10 → 25 → 50 over 90 s |",
        f"| Requests | {requests} ({float(total['Requests/s']):.1f} req/s) |",
        f"| Error rate | {failures / requests:.2%} ({failures} failed) |",
        f"| p50 / p95 / p99 latency (all requests) | {total['50%']} / {total['95%']} / {total['99%']} ms |",
        f"| Chat requests logged in DB | {logged} |",
        f"| Avg tokens per chat request | {avg_tokens:.0f} (mock: 4 characters ≈ 1 token) |",
        f"| Avg estimated cost per chat request | ${avg_cost:.6f} (at $4 / $20 per MTok in/out) |",
        f"| Estimated cost of the whole run | ${total_cost:.4f} |",
        "",
        "| Endpoint | Requests | Failures | p50 ms | p95 ms | p99 ms |",
        "|---|---|---|---|---|---|",
    ]
    for r in [*chat_rows, *[r for r in rows if r["Name"] == "/health"]]:
        lines.append(
            f"| {r['Name']} | {r['Request Count']} | {r['Failure Count']} | {r['50%']} | {r['95%']} | {r['99%']} |"
        )
    report = "\n".join(lines) + "\n"
    out = REPORTS / f"{Path(csv_prefix).name}.md"
    out.write_text(report)
    print(report)


if __name__ == "__main__":
    main(*sys.argv[1:4])
