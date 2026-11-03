"""Base classes that give every test class the same tools without repeating fixtures.

pytest test classes can't have __init__, so an autouse fixture injects shared objects onto `self`.
"""

import pytest

from tests.framework.api_client import DocuChatClient
from tests.framework.openapi import OpenAPISpec


class BaseTest:
    """Shared helpers for all test classes."""

    @staticmethod
    def assert_no_errors(errors: list[str], context: str = "") -> None:
        assert not errors, f"{context}\n" + "\n".join(errors)


class BaseAPITest(BaseTest):
    api: DocuChatClient
    spec: OpenAPISpec

    @pytest.fixture(autouse=True)
    def _inject(self, api_client: DocuChatClient, openapi_spec: OpenAPISpec) -> None:
        self.api = api_client
        self.spec = openapi_spec

    def assert_matches_spec(self, response, path: str, method: str) -> None:
        """The status must be documented and the body must match its documented schema."""
        documented = self.spec.documented_statuses(path, method)
        assert response.status_code in documented, (
            f"{response.status_code} not documented for {method} {path}"
        )
        errors = self.spec.validate(response.json(), path, method, response.status_code)
        self.assert_no_errors(
            errors, f"{method} {path} -> {response.status_code} does not match openapi.json"
        )
