"""Contract tests: every response the API gives must match what openapi.json promises."""

import allure
import pytest

from tests.framework.base_test import BaseAPITest

pytestmark = [pytest.mark.api]


@allure.feature("API contract")
class TestContract(BaseAPITest):
    @pytest.mark.smoke
    def test_health_matches_spec(self) -> None:
        response = self.api.health()
        assert response.status_code == 200
        self.assert_matches_spec(response, "/health", "get")

    @pytest.mark.parametrize(
        "message",
        [
            "How many days of paid sick leave do employees get?",  # answered with sources
            "What is the CEO's favourite football team?",  # refusal
            "Where is ORD-1002?",  # tool call
        ],
        ids=["answered", "refused", "tool"],
    )
    def test_chat_responses_match_spec(self, message: str) -> None:
        response = self.api.chat("contract", message)
        assert response.status_code == 200
        self.assert_matches_spec(response, "/chat", "post")

    def test_validation_error_matches_spec(self) -> None:
        response = self.api.raw("POST", "/chat", json={"session_id": ""})
        assert response.status_code == 422
        self.assert_matches_spec(response, "/chat", "post")

    def test_session_id_is_echoed(self) -> None:
        assert self.api.chat("echo-me", "What is the return window?").json()["session_id"] == "echo-me"

    def test_spec_on_disk_matches_running_app(self) -> None:
        # openapi.json is committed for clients and Postman; it must equal what the app serves.
        served = self.api.raw("GET", "/openapi.json").json()
        assert served == self.spec.document, "openapi.json is stale: run `python -m scripts.export_openapi`"
