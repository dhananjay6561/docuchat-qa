"""Record/replay store for LLM responses.

Each request is hashed to a key. A cassette maps keys to recorded responses, so an eval run can be
replayed offline and gives identical results every time. A request with no recorded response is
written to a pending file so it can be answered (by a live model or a person) and merged back in.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


class CassetteMiss(LookupError):
    """No recorded response for this request yet; it has been added to the pending file."""


def request_key(payload: Any) -> str:
    # sort_keys makes the hash independent of dict ordering, so the same request always matches.
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


class Cassette:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.pending_path = path.parent / "pending" / f"{path.stem}.jsonl"
        self._entries: dict[str, Any] = {}
        self._pending: set[str] = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._entries[row["key"]] = row["response"]

    def __len__(self) -> int:
        return len(self._entries)

    def lookup(self, request: Any) -> Any:
        key = request_key(request)
        if key in self._entries:
            return self._entries[key]
        self._record_pending(key, request)
        raise CassetteMiss(key)

    def _record_pending(self, key: str, request: Any) -> None:
        if key in self._pending:
            return
        self._pending.add(key)
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        with self.pending_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "request": request}, ensure_ascii=False) + "\n")

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def merge(self, responses_file: Path) -> int:
        """Add answered requests to the cassette. Returns how many new entries were added."""
        added = 0
        for line in responses_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row["key"] not in self._entries:
                self._entries[row["key"]] = row["response"]
                added += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Sorted, one entry per line: stable diffs when the cassette changes in git.
        lines = [
            json.dumps({"key": k, "response": v}, ensure_ascii=False)
            for k, v in sorted(self._entries.items())
        ]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return added
