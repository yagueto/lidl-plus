"""Tests for browser authentication helpers."""

import json

from selenium.webdriver.common.by import By

from lidlplus.browser_auth import _fill_password, _performance_urls, _submit_form


class FakeBrowser:
    def get_log(self, log_type):
        assert log_type == "performance"
        return [
            {
                "message": json.dumps(
                    {
                        "message": {
                            "params": {
                                "request": {"url": "https://accounts.lidl.com/connect/authorize"},
                                "response": {
                                    "url": "https://accounts.lidl.com/connect/authorize/callback",
                                    "headers": {"Location": "com.lidlplus.app://callback?code=authorization-code"},
                                },
                            }
                        }
                    }
                )
            }
        ]


class FakeButton:
    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class FakePasswordInput:
    def __init__(self):
        self.value = None

    def send_keys(self, value):
        self.value = value


class FakeForm:
    def __init__(self, button):
        self.button = button

    def find_element(self, by, selector):
        assert (by, selector) == (By.CSS_SELECTOR, 'button[type="submit"]')
        return self.button


class FakeInput:
    def __init__(self, form):
        self.form = form

    def find_element(self, by, selector):
        assert (by, selector) == (By.XPATH, "./ancestor::form")
        return self.form


class FakeWait:
    def __init__(self, elements):
        self.elements = elements
        self.locators = []

    def until(self, locator):
        self.locators.append(locator)
        return self.elements[locator]


def test_performance_urls_include_redirect_location():
    assert _performance_urls(FakeBrowser()) == [
        "https://accounts.lidl.com/connect/authorize",
        "https://accounts.lidl.com/connect/authorize/callback",
        "com.lidlplus.app://callback?code=authorization-code",
    ]


def test_submit_form_finds_button_from_input_ancestor():
    button = FakeButton()

    _submit_form(FakeInput(FakeForm(button)))

    assert button.clicked


def test_fill_password_uses_current_primary_button(monkeypatch):
    password_input = FakePasswordInput()
    button = FakeButton()
    password_locator = (By.CSS_SELECTOR, '[data-testid="login-input-password"]')
    submit_locator = (By.CSS_SELECTOR, '[data-testid="button-primary"]')
    wait = FakeWait({password_locator: password_input, submit_locator: button})
    monkeypatch.setattr(
        "lidlplus.browser_auth.expected_conditions.element_to_be_clickable",
        lambda locator: locator,
    )

    _fill_password(wait, "password")

    assert wait.locators == [password_locator, submit_locator]
    assert password_input.value == "password"
    assert button.clicked
