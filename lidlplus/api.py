"""Lidl Plus API client."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from lidlplus.exceptions import MissingLogin


class LidlPlusApi:
    """Lidl Plus API connector."""

    # pylint: disable=too-many-instance-attributes

    _CLIENT_ID = "LidlPlusNativeClient"
    _AUTH_API = "https://accounts.lidl.com"
    _TICKET_API = "https://tickets.lidlplus.com/api/v2"
    _TICKET_V3_API = "https://tickets.lidlplus.com/api/v3"
    _COUPONS_API = "https://coupons.lidlplus.com/app/api"
    _APP = "com.lidlplus.app"
    _OS = "iOs"
    _TIMEOUT = 10
    _TOKEN_LEEWAY = timedelta(seconds=30)
    _APP_VERSION = "17.9.3"

    def __init__(self, language, country, refresh_token="", app_version=None, session=None):
        self._login_url = ""
        self._code_verifier = ""
        self._refresh_token = refresh_token
        self._expires = None
        self._token = ""
        self._country = country.upper()
        self._language = language.lower()
        self._app_version = app_version or self._APP_VERSION
        self._session = session or requests.Session()

    @property
    def refresh_token(self):
        """Return the current refresh token."""
        return self._refresh_token

    @property
    def token(self):
        """Return the current access token."""
        return self._token

    def _register_oauth_client(self):
        if self._login_url:
            return self._login_url

        self._code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(self._code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        params = {
            "client_id": self._CLIENT_ID,
            "response_type": "code",
            "scope": "openid profile offline_access lpprofile lpapis",
            "redirect_uri": f"{self._APP}://callback",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        self._login_url = f"{self._AUTH_API}/connect/authorize?{urlencode(params)}"
        return self._login_url

    def _auth(self, payload):
        default_secret = base64.b64encode(f"{self._CLIENT_ID}:secret".encode()).decode()
        response = self._session.post(
            f"{self._AUTH_API}/connect/token",
            headers={
                "Authorization": f"Basic {default_secret}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=payload,
            timeout=self._TIMEOUT,
        )
        response.raise_for_status()
        tokens = response.json()
        self._expires = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        self._token = tokens["access_token"]
        self._refresh_token = tokens.get("refresh_token", self._refresh_token)
        return tokens

    def _renew_token(self):
        payload = {"refresh_token": self._refresh_token, "grant_type": "refresh_token"}
        return self._auth(payload)

    def _authorization_code(self, code):
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{self._APP}://callback",
            "code_verifier": self._code_verifier,
        }
        return self._auth(payload)

    @property
    def _register_link(self):
        params = {
            "Country": self._country,
            "language": f"{self._language}-{self._country}",
        }
        return f"{self._register_oauth_client()}&{urlencode(params)}"

    @staticmethod
    def _extract_code_from_url(candidate_url):
        if not candidate_url:
            return None
        parsed = urlparse(candidate_url)
        for values in (parse_qs(parsed.query), parse_qs(parsed.fragment)):
            codes = values.get("code")
            if codes and codes[0]:
                return codes[0]
            for key in ("redirect_uri", "returnUrl", "ReturnUrl"):
                for nested_url in values.get(key, []):
                    if nested_code := LidlPlusApi._extract_code_from_url(nested_url):
                        return nested_code
        return None

    def login(self, login, password, method="e", **kwargs):
        """Authenticate through a real browser and store the resulting tokens."""
        try:
            from lidlplus.browser_auth import (  # pylint: disable=import-outside-toplevel
                BrowserLoginOptions,
                LoginCredentials,
                get_authorization_code,
            )
        except ImportError as error:
            from lidlplus.exceptions import WebBrowserException  # pylint: disable=import-outside-toplevel

            raise WebBrowserException(
                'Browser authentication requires the optional dependency: pip install "lidl-plus[auth]"'
            ) from error

        code = get_authorization_code(
            self._register_link,
            LoginCredentials(login, password, method),
            self._extract_code_from_url,
            BrowserLoginOptions(
                accept_legal_terms=kwargs.get("accept_legal_terms", True),
                headless=kwargs.get("headless", False),
                timeout=kwargs.get("timeout", 180),
                verify_mode=kwargs.get("verify_mode", "phone"),
                verify_token_func=kwargs.get("verify_token_func"),
            ),
        )
        return self._authorization_code(code)

    def _default_headers(self):
        now = datetime.now(timezone.utc)
        if self._refresh_token and (
            not self._token or self._expires is None or now + self._TOKEN_LEEWAY >= self._expires
        ):
            self._renew_token()
        if not self._token:
            raise MissingLogin("You need to login!")
        return {
            "Authorization": f"Bearer {self._token}",
            "App-Version": self._app_version,
            "Operating-System": self._OS,
            "App": "com.lidl.eci.lidl.plus",
            "Accept-Language": self._language,
        }

    def _request(self, method, url, **kwargs):
        headers = {**self._default_headers(), **kwargs.pop("headers", {})}
        response = self._session.request(
            method,
            url,
            headers=headers,
            timeout=self._TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def tickets(self, only_favorite=False):
        """Return all receipt summaries, following the API pagination."""
        url = f"{self._TICKET_API}/{self._country}/tickets"
        tickets = []
        page_number = 1
        while True:
            page = self._request(
                "GET",
                url,
                params={"pageNumber": page_number, "onlyFavorite": str(only_favorite).lower()},
            ).json()
            page_tickets = page.get("tickets", [])
            tickets.extend(page_tickets)
            if not page_tickets or len(tickets) >= page.get("totalCount", len(tickets)):
                break
            page_number += 1
        return tickets

    def ticket(self, ticket_id):
        """Return full data for one receipt."""
        url = f"{self._TICKET_API}/{self._country}/tickets/{ticket_id}"
        try:
            return self._request("GET", url).json()
        except requests.HTTPError:
            fallback = f"{self._TICKET_V3_API}/{self._country}/tickets/{ticket_id}"
            return self._request("GET", fallback).json()

    def coupon_promotions_v1(self):
        """Return the older single-section coupon list."""
        url = f"{self._COUPONS_API}/v1/promotionslist"
        return self._request("GET", url, headers={"Country": self._country}).json()

    def activate_coupon_promotion_v1(self, promotion_id):
        """Activate a coupon using its coupon ID."""
        return self.activate_coupon(promotion_id)

    def coupons(self):
        """Return the current sectioned coupon list."""
        url = f"{self._COUPONS_API}/v2/promotionslist"
        return self._request("GET", url, headers={"Country": self._country}).json()

    def activate_coupon(self, coupon_id):
        """Activate a coupon using its coupon ID."""
        url = f"{self._COUPONS_API}/v1/promotions/{coupon_id}/activation"
        return self._request("POST", url, headers={"Country": self._country}).text

    def deactivate_coupon(self, coupon_id):
        """Deactivate a coupon using its coupon ID."""
        url = f"{self._COUPONS_API}/v1/promotions/{coupon_id}/activation"
        return self._request("DELETE", url, headers={"Country": self._country}).text
