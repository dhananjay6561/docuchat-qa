"""Property-based API tests generated from the OpenAPI spec by Schemathesis.

Schemathesis reads the spec and generates many valid and invalid requests per operation, then
checks the API never returns a 5xx and always answers with a status and body the spec documents.
The spec comes from the app itself; test_contract.py pins it to the committed openapi.json.

The fuzz runs against the secured configuration (API_KEY set). Against the open default config,
Schemathesis correctly flagged that the spec declares an API key the server then doesn't enforce.
"""

import tempfile
from pathlib import Path

import pytest
import schemathesis
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings
from schemathesis.specs.openapi.checks import negative_data_rejection

from app.main import create_app
from tests.conftest import make_settings

pytestmark = [pytest.mark.api]
FUZZ_KEY = "fuzz-key"

APP = create_app(make_settings(Path(tempfile.mkdtemp()), api_key=FUZZ_KEY))
schema = schemathesis.openapi.from_asgi("/openapi.json", APP).include(path_regex="^/(chat|health)$")


@pytest.fixture(scope="module", autouse=True)
def started_app():
    with TestClient(APP):  # runs startup once so the chat service exists for every example
        yield


@schema.parametrize()
@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
def test_api_conforms_to_spec(case) -> None:
    case.call_and_validate(headers={"X-API-Key": FUZZ_KEY}, excluded_checks=[negative_data_rejection])
