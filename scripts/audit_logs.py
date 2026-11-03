"""Audits the chat log database for raw personal data that slipped past masking.

Masking happens before writes, so anything this finds is a masking bug. Run it against a copy of
the production log DB:

    uv run python -m scripts.audit_logs path/to/docuchat.db
"""

import re
import sqlite3
import sys
from pathlib import Path

# Deliberately broader than app/pii.py: the audit should catch what the masker misses.
SUSPICIOUS = {
    "phone-like digit run": re.compile(r"\+?\d[\d .()-]{8,}\d"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # order ETAs look like digit runs but aren't PII


def audit(db_path: Path) -> list[tuple[str, str, str, str]]:
    findings = []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT message_id, user_message, answer FROM chat_logs").fetchall()
    for message_id, user_message, answer in rows:
        for column, text in (("user_message", user_message), ("answer", answer)):
            for label, pattern in SUSPICIOUS.items():
                for match in pattern.findall(text):
                    if ISO_DATE.match(match):
                        continue
                    findings.append((message_id, column, label, match))
    return findings


if __name__ == "__main__":
    findings = audit(Path(sys.argv[1]))
    for message_id, column, label, match in findings:
        print(f"{message_id}  {column:12}  {label:20}  {match}")
    print(f"{len(findings)} finding(s)")
    sys.exit(1 if findings else 0)
