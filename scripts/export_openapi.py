"""Writes the API's OpenAPI spec to openapi.json so API tests and the Postman export use one source."""

import json
from pathlib import Path

from app.main import create_app

OUTPUT = Path(__file__).resolve().parent.parent / "openapi.json"

if __name__ == "__main__":
    spec = create_app().openapi()
    OUTPUT.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
