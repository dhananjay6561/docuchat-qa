"""Validates real responses against the committed openapi.json.

If the code and the spec drift apart (a renamed field, a new status code), these checks fail, so
the spec that clients and the Postman collection rely on stays honest.
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SPEC_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


class OpenAPISpec:
    def __init__(self, path: Path = SPEC_PATH) -> None:
        self.document: dict[str, Any] = json.loads(path.read_text())

    def response_schema(self, path: str, method: str, status: int) -> dict[str, Any]:
        response = self.document["paths"][path][method.lower()]["responses"][str(status)]
        return response["content"]["application/json"]["schema"]

    def documented_statuses(self, path: str, method: str) -> set[int]:
        return {int(code) for code in self.document["paths"][path][method.lower()]["responses"]}

    def validate(self, payload: Any, path: str, method: str, status: int) -> list[str]:
        """Return validation errors (empty list = payload matches the spec)."""
        schema = self._resolve_refs(self.response_schema(path, method, status))
        validator = Draft202012Validator(schema)
        return [
            f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in validator.iter_errors(payload)
        ]

    def _resolve_refs(self, schema: Any) -> Any:
        # Inline local $refs so the validator doesn't need to know the spec's URI layout.
        if isinstance(schema, dict):
            if "$ref" in schema:
                target: Any = self.document
                for part in schema["$ref"].lstrip("#/").split("/"):
                    target = target[part]
                return self._resolve_refs(target)
            return {key: self._resolve_refs(value) for key, value in schema.items()}
        if isinstance(schema, list):
            return [self._resolve_refs(item) for item in schema]
        return schema
