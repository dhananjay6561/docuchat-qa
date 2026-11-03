"""Summarises a promptfoo results file into a per-category markdown report.

    uv run python -m safety.summarize safety/reports/latest.json

Exit code 1 if any attack succeeded or any test errored, so CI can gate on it.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

REPORT_MD = Path(__file__).resolve().parent / "reports" / "latest.md"


def main(results_path: Path) -> int:
    data = json.loads(results_path.read_text())
    rows = data["results"]["results"]
    by_category: dict[str, list[dict]] = defaultdict(list)
    failures: list[str] = []
    for row in rows:
        category = (row.get("metadata") or {}).get("category") or row["testCase"]["metadata"]["category"]
        by_category[category].append(row)
        if row["success"]:
            continue
        grading = row.get("gradingResult")
        if grading:  # the API answered but an attack check failed
            reasons = [c["reason"] for c in grading.get("componentResults", []) if not c["pass"]]
            failures.append(f"{row['vars']['id']} ({category}): {'; '.join(reasons)}")
        else:  # the request itself failed (e.g. API down or recording missing)
            failures.append(f"{row['vars']['id']} ({category}): request error: {str(row.get('error'))[:120]}")

    passed = sum(r["success"] for r in rows)
    lines = [
        "# Red-team results",
        "",
        f"- Run: {data['results']['timestamp']}  (promptfoo eval {data['evalId']})",
        f"- Attacks: {len(rows)}, defended: {passed}, failed: {len(rows) - passed}",
        "",
        "| Category | Attacks | Defended | Failed |",
        "|---|---|---|---|",
    ]
    for category, items in by_category.items():
        ok = sum(r["success"] for r in items)
        lines.append(f"| {category} | {len(items)} | {ok} | {len(items) - ok} |")
    lines += ["", "## Failures", ""] + ([f"- {f}" for f in failures] or ["None."])
    REPORT_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
