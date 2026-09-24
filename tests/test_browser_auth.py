"""Tests for browser authentication helpers."""

import json

from selenium.webdriver.common.by import By

from lidlplus.browser_auth import _performance_urls, _submit_form


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
