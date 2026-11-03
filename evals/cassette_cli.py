"""Helpers for filling cassettes when requests are answered outside the code (no API key).

python -m evals.cassette_cli batches app --size 40   # split pending requests into batch files
python -m evals.cassette_cli merge app               # merge every *.responses.jsonl, clear pending
"""

import argparse
import json
from pathlib import Path

from app.llm.cassette import Cassette

CASSETTE_DIR = Path(__file__).resolve().parent / "cassettes"
PENDING_DIR = CASSETTE_DIR / "pending"


def batches(name: str, size: int) -> None:
    pending = PENDING_DIR / f"{name}.jsonl"
    rows = [line for line in pending.read_text().splitlines() if line.strip()]
    for old in PENDING_DIR.glob(f"{name}_batch_*.jsonl"):
        old.unlink()
    for i in range(0, len(rows), size):
        out = PENDING_DIR / f"{name}_batch_{i // size + 1:02d}.jsonl"
        out.write_text("\n".join(rows[i : i + size]) + "\n")
        print(out.relative_to(CASSETTE_DIR.parent.parent))
    print(f"{len(rows)} pending request(s)")


def merge(name: str) -> None:
    cassette = Cassette(CASSETTE_DIR / f"{name}.jsonl")
    added = 0
    for responses in sorted(PENDING_DIR.glob(f"{name}_batch_*.responses.jsonl")):
        for line in responses.read_text().splitlines():  # validate before merging
            if line.strip():
                row = json.loads(line)
                assert {"key", "response"} <= row.keys(), f"bad row in {responses.name}"
        added += cassette.merge(responses)
    for leftover in PENDING_DIR.glob(f"{name}*.jsonl"):
        leftover.unlink()
    print(f"Merged {added} new response(s); {name} cassette now has {len(cassette)} entries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("batches")
    b.add_argument("name")
    b.add_argument("--size", type=int, default=40)
    m = sub.add_parser("merge")
    m.add_argument("name")
    args = parser.parse_args()
    batches(args.name, args.size) if args.cmd == "batches" else merge(args.name)
