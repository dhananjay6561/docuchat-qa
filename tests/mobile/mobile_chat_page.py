"""Page Object for the chat UI in mobile Chrome, driven by Appium (Selenium WebDriver API).

Same data-testid locators as the desktop Playwright ChatPage, so both suites break on the same
UI changes and nowhere else.
"""

from appium.webdriver import Remote
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait


def tid(test_id: str) -> tuple[str, str]:
    return By.CSS_SELECTOR, f'[data-testid="{test_id}"]'


class MobileChatPage:
    def __init__(self, driver: Remote, base_url: str, timeout: float = 15) -> None:
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, timeout)

    def open(self) -> "MobileChatPage":
        self.driver.get(self.base_url)
        self.wait.until(ec.element_to_be_clickable(tid("message-input")))
        return self

    def assistant_messages(self) -> list[WebElement]:
        return self.driver.find_elements(*tid("message-assistant"))

    def ask(self, message: str) -> WebElement:
        before = len(self.assistant_messages())
        field = self.driver.find_element(*tid("message-input"))
        field.clear()
        field.send_keys(message)
        self.driver.find_element(*tid("send-button")).click()
        self.wait.until(lambda d: len(self.assistant_messages()) > before)
        return self.assistant_messages()[-1]

    @staticmethod
    def sources_of(message: WebElement) -> list[str]:
        return [el.text for el in message.find_elements(*tid("source-item"))]

    @staticmethod
    def is_refusal(message: WebElement) -> bool:
        return len(message.find_elements(*tid("refusal-badge"))) == 1

    def has_horizontal_overflow(self) -> bool:
        # On a phone, content wider than the screen means sideways scrolling: a layout bug.
        return self.driver.execute_script(
            "return document.documentElement.scrollWidth > window.innerWidth + 1;"
        )

    def start_new_chat(self) -> None:
        self.driver.find_element(*tid("new-session-button")).click()
