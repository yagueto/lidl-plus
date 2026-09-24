"""Browser-based authentication for Lidl Plus."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from lidlplus.exceptions import LegalTermsException, LoginError, WebBrowserException


@dataclass(frozen=True)
class LoginCredentials:
    """Credentials and login method entered by the user."""

    login: str
    password: str
    method: str


@dataclass(frozen=True)
class BrowserLoginOptions:
    """Options for the interactive browser login."""

    accept_legal_terms: bool = True
    headless: bool = False
    timeout: int = 180
    verify_mode: str = "phone"
    verify_token_func: Callable[[], str] | None = None


def _create_browser(headless):
    errors = []
    browser_options = (
        (webdriver.Chrome, webdriver.ChromeOptions(), "goog:loggingPrefs"),
        (webdriver.Edge, webdriver.EdgeOptions(), "ms:loggingPrefs"),
        (webdriver.Firefox, webdriver.FirefoxOptions(), None),
    )
    for browser_factory, options, log_capability in browser_options:
        if log_capability:
            options.set_capability(log_capability, {"performance": "ALL"})
        if headless:
            options.add_argument("-headless" if browser_factory is webdriver.Firefox else "--headless=new")
        try:
            return browser_factory(options=options)
        except WebDriverException as error:
            errors.append(error)

    raise WebBrowserException("Unable to start Chrome, Edge, or Firefox") from errors[-1]


def _performance_urls(browser):
    try:
        entries = browser.get_log("performance")
    except WebDriverException:
        return []

    urls = []
    for entry in entries:
        try:
            message = json.loads(entry["message"])["message"]
        except (KeyError, TypeError, ValueError):
            continue

        params = message.get("params", {})
        request = params.get("request", {})
        response = params.get("response", {})
        for url in (request.get("url"), response.get("url")):
            if url:
                urls.append(url)

        headers = response.get("headers", {})
        location = headers.get("location") or headers.get("Location")
        if location:
            urls.append(location)
    return urls


def _visible_text(browser, selector):
    messages = []
    for element in browser.find_elements(By.CSS_SELECTOR, selector):
        if element.is_displayed() and element.text.strip():
            messages.append(element.text.strip())
    return messages


def _raise_login_error(browser):
    messages = _visible_text(browser, ".input-error-message")
    if not messages:
        messages = _visible_text(browser, '[role="alert"]')
    if messages:
        raise LoginError(" ".join(dict.fromkeys(messages)))


class _BrowserLogin:  # pylint: disable=too-few-public-methods
    def __init__(self, login_url, credentials, extract_code, options):
        self.login_url = login_url
        self.credentials = credentials
        self.extract_code = extract_code
        self.options = options
        self.browser = None

    def _handle_legal_terms(self):
        checkboxes = [
            checkbox for checkbox in self.browser.find_elements(By.ID, "checkbox_Accepted") if checkbox.is_displayed()
        ]
        if not checkboxes:
            return False
        if not self.options.accept_legal_terms:
            titles = _visible_text(self.browser, "h2")
            raise LegalTermsException(titles[0] if titles else "Updated legal terms require acceptance")
        if not checkboxes[0].is_selected():
            checkboxes[0].click()
        form = checkboxes[0].find_element(By.XPATH, "./ancestor::form")
        form.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        return True

    def _select_verification_method(self):
        test_id = "link-phone-switch-action" if self.options.verify_mode == "phone" else "link-email-switch-action"
        links = [
            link
            for link in self.browser.find_elements(By.CSS_SELECTOR, f'[data-testid="{test_id}"]')
            if link.is_displayed()
        ]
        if links:
            links[0].click()
            return True
        return False

    def _fill_credentials(self):
        wait = WebDriverWait(self.browser, min(self.options.timeout, 60))
        if self.credentials.method == "p":
            phone_inputs = [
                phone_input
                for phone_input in self.browser.find_elements(By.CSS_SELECTOR, '[data-testid="input-phone-text"]')
                if phone_input.is_displayed()
            ]
            if not phone_inputs:
                wait.until(
                    expected_conditions.element_to_be_clickable(
                        (By.CSS_SELECTOR, '[data-testid="switch-method-button"]')
                    )
                ).click()
            login_selector = '[data-testid="input-phone-text"]'
        else:
            login_selector = '[data-testid="input-email"]'

        wait.until(expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, login_selector))).send_keys(
            self.credentials.login
        )
        wait.until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="login-or-register-submit-button"]')
            )
        ).click()
        wait.until(
            expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="login-input-password"]'))
        ).send_keys(self.credentials.password)
        password_view = wait.until(
            expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="password-step-view"]'))
        )
        password_view.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()

    def _submit_verification_code(self):
        verification_inputs = [
            verification_input
            for verification_input in self.browser.find_elements(
                By.CSS_SELECTOR,
                '[name="VerificationCode"], [autocomplete="one-time-code"]',
            )
            if verification_input.is_displayed()
        ]
        if not verification_inputs:
            return False
        if self.options.verify_token_func is None:
            raise LoginError("A verification code is required")
        verification_inputs[0].send_keys(self.options.verify_token_func())
        form = verification_inputs[0].find_element(By.XPATH, "./ancestor::form")
        form.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        return True

    def _wait_for_code(self):
        deadline = time.monotonic() + self.options.timeout
        verification_submitted = False
        method_selected = False

        while time.monotonic() < deadline:
            _raise_login_error(self.browser)
            if self._handle_legal_terms():
                time.sleep(0.25)
                continue
            for candidate_url in [self.browser.current_url, *_performance_urls(self.browser)]:
                code = self.extract_code(candidate_url)
                if code:
                    return code
            if not method_selected and self._select_verification_method():
                method_selected = True
                time.sleep(0.25)
                continue
            if not verification_submitted:
                verification_submitted = self._submit_verification_code()
            time.sleep(0.25)

        raise LoginError("Timed out waiting for the Lidl authorization redirect")

    def run(self):
        """Run the login flow and always close the browser."""
        self.browser = _create_browser(self.options.headless)
        try:
            self.browser.get(self.login_url)
            self._fill_credentials()
            return self._wait_for_code()
        except TimeoutException as error:
            _raise_login_error(self.browser)
            raise LoginError("The Lidl login page did not reach the expected step") from error
        finally:
            self.browser.quit()


def get_authorization_code(login_url, credentials, extract_code, options):
    """Complete the current Lidl login flow and return its OAuth code."""
    if credentials.method not in {"e", "p"}:
        raise ValueError('Unknown login method. Use "e" for email or "p" for phone.')
    if options.verify_mode not in {"phone", "email"}:
        raise ValueError('Unknown verification mode. Use "phone" or "email".')
    return _BrowserLogin(login_url, credentials, extract_code, options).run()
