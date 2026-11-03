"""Generates a Postman collection from openapi.json, with test scripts, for Newman to run in CI.

Response schemas are copied from the spec into each request's tests, so Postman checks the API
against the same contract as the pytest suite. Regenerate after changing the API:

    uv run python -m scripts.export_postman
"""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / "openapi.json").read_text())
OUTPUT = ROOT / "postman" / "docuchat.postman_collection.json"


def resolve(node: Any) -> Any:
    """Inline $refs so each embedded schema is self-contained."""
    if isinstance(node, dict):
        if "$ref" in node:
            target: Any = SPEC
            for part in node["$ref"].lstrip("#/").split("/"):
                target = target[part]
            return resolve(target)
        return {k: resolve(v) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve(item) for item in node]
    return node


def schema_for(path: str, method: str, status: int) -> dict[str, Any]:
    return resolve(
        SPEC["paths"][path][method]["responses"][str(status)]["content"]["application/json"]["schema"]
    )


def request(name: str, method: str, path: str, body: dict | None, status: int, checks: list[str]) -> dict:
    lines = [f'pm.test("status is {status}", () => pm.response.to.have.status({status}));']
    documented = SPEC["paths"].get(path, {}).get(method.lower(), {}).get("responses", {})
    if str(status) in documented and "content" in documented[str(status)]:
        schema = json.dumps(schema_for(path, method.lower(), status))
        lines.append(f'pm.test("body matches openapi.json", () => pm.response.to.have.jsonSchema({schema}));')
    lines += checks
    item: dict[str, Any] = {
        "name": name,
        "request": {
            "method": method,
            "header": [
                {"key": "Content-Type", "value": "application/json"},
                {"key": "X-API-Key", "value": "{{apiKey}}"},
            ],
            "url": {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"], "path": path.strip("/").split("/")},
        },
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": lines}}],
    }
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body)}
    return item


def build() -> dict:
    body = lambda session, message: {"session_id": session, "message": message}  # noqa: E731
    return {
        "info": {
            "name": f"{SPEC['info']['title']} {SPEC['info']['version']}",
            "description": "Generated from openapi.json by scripts/export_postman.py. Do not edit by hand.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}, {"key": "apiKey", "value": ""}],
        "item": [
            {"name": "system", "item": [request("health", "GET", "/health", None, 200, [
                'pm.test("reports ok", () => pm.expect(pm.response.json().status).to.eql("ok"));',
            ])]},
            {"name": "chat", "item": [
                request("answered with sources", "POST", "/chat", body("pm-1", "How many days of paid sick leave do employees get?"), 200, [
                    'pm.test("not refused", () => pm.expect(pm.response.json().refused).to.be.false);',
                    'pm.test("cites a source", () => pm.expect(pm.response.json().sources.length).to.be.above(0));',
                ]),
                request("refusal for unanswerable question", "POST", "/chat", body("pm-2", "What is the CEO's favourite football team?"), 200, [
                    'pm.test("refused", () => pm.expect(pm.response.json().refused).to.be.true);',
                    'pm.test("no sources", () => pm.expect(pm.response.json().sources).to.eql([]));',
                ]),
                request("order status uses the tool", "POST", "/chat", body("pm-3", "Where is my order ORD-1002?"), 200, [
                    'pm.test("tool called", () => pm.expect(pm.response.json().tool_calls).to.include("get_order_status"));',
                ]),
                request("empty message is rejected", "POST", "/chat", body("pm-4", ""), 422, [
                    'pm.test("names the field", () => pm.expect(JSON.stringify(pm.response.json().detail)).to.include("message"));',
                ]),
                request("wrong method", "GET", "/chat", None, 405, []),
            ]},
        ],
    }  # fmt: skip


if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
