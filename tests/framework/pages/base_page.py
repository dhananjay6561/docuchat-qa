"""Base Page Object: shared waits and locator helpers for every page."""

from playwright.sync_api import Locator, Page


class BasePage:
    path = "/"

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url

    def open(self) -> "BasePage":
        self.page.goto(f"{self.base_url}{self.path}")
        return self

    def by_test_id(self, test_id: str) -> Locator:
        # data-testid locators survive styling and copy changes, unlike CSS classes or text.
        return self.page.get_by_test_id(test_id)
