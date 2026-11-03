"""Negative tests: bad input, wrong methods, auth failures and a broken LLM must fail cleanly."""

from pathlib import Path

import allure
import pytest
from fastapi.testclient import TestClient

from app.llm.base import LLMProvider, LLMResponse, LLMUnavailableError
from app.main import create_app
from tests.conftest import make_settings
from tests.framework.api_client import DocuChatClient
from tests.framework.base_test import BaseAPITest

pytestmark = [pytest.mark.api]


class DownProvider(LLMProvider):
    """Simulates an LLM outage (network error, rate limit, provider 5xx)."""

    name = "down"

    def complete(self, system, messages, tools) -> LLMResponse:
        raise LLMUnavailableError("simulated outage")


@allure.feature("API negative cases")
class TestValidation(BaseAPITest):
    @pytest.mark.parametrize(
        ("body", "field"),
        [
            ({"message": "hi"}, "session_id"),
            ({"session_id": "s"}, "message"),
            ({"session_id": "", "message": "hi"}, "session_id"),
            ({"session_id": "s", "message": ""}, "message"),
            ({"session_id": "s", "message": "x" * 2001}, "message"),
            ({"session_id": "s" * 65, "message": "hi"}, "session_id"),
            ({"session_id": 123, "message": "hi"}, "session_id"),
            ({"session_id": "s", "message": ["not", "a", "string"]}, "message"),
        ],
        ids=["no-session", "no-message", "empty-session", "empty-message", "message-too-long",
             "session-too-long", "session-not-string", "message-not-string"],
    )  # fmt: skip
    def test_invalid_body_returns_422_naming_the_field(self, body: dict, field: str) -> None:
        response = self.api.raw("POST", "/chat", json=body)
        assert response.status_code == 422
        assert any(field in error["loc"] for error in response.json()["detail"])

    def test_malformed_json_returns_422(self) -> None:
        response = self.api.raw(
            "POST", "/chat", content=b"{not json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_undecodable_body_returns_400(self) -> None:
        # Found by the Schemathesis fuzz: invalid UTF-8 gets 400, which the spec now documents.
        response = self.api.raw(
            "POST", "/chat", content=b"\xff\xfe{", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert 400 in self.spec.documented_statuses("/chat", "post")

    def test_wrong_method_returns_405(self) -> None:
        assert self.api.raw("GET", "/chat").status_code == 405

    def test_unknown_route_returns_404(self) -> None:
        assert self.api.raw("GET", "/does-not-exist").status_code == 404


@allure.feature("API negative cases")
class TestAuth:
    @pytest.fixture
    def secured(self, tmp_path: Path):
        with TestClient(create_app(make_settings(tmp_path, api_key="s3cret"))) as client:
            yield client

    def test_missing_key_returns_401(self, secured: TestClient) -> None:
        response = DocuChatClient(secured).chat("auth", "What is the return window?")
        assert response.status_code == 401

    def test_wrong_key_returns_401(self, secured: TestClient) -> None:
        response = DocuChatClient(secured, api_key="wrong").chat("auth", "What is the return window?")
        assert response.status_code == 401

    def test_correct_key_is_accepted(self, secured: TestClient) -> None:
        response = DocuChatClient(secured, api_key="s3cret").chat("auth", "What is the return window?")
        assert response.status_code == 200

    def test_health_stays_public(self, secured: TestClient) -> None:
        # Load balancers and uptime checks must reach /health without credentials.
        assert DocuChatClient(secured).health().status_code == 200


@allure.feature("API negative cases")
class TestLLMOutage:
    def test_llm_outage_returns_503_not_500(self, tmp_path: Path) -> None:
        with TestClient(create_app(make_settings(tmp_path), llm=DownProvider())) as client:
            response = DocuChatClient(client).chat("outage", "What is the return window?")
        assert response.status_code == 503
        assert response.json()["detail"] == "LLM provider unavailable"
