"""Tests for the Lidl Plus API client."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from lidlplus import LidlPlusApi


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _respond(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        return self._respond("POST", url, **kwargs)

    def request(self, method, url, **kwargs):
        return self._respond(method, url, **kwargs)


def authenticated_api(responses):
    session = FakeSession(responses)
    api = LidlPlusApi("de", "at", session=session)
    api._token = "access-token"
    api._expires = datetime.now(timezone.utc) + timedelta(hours=1)
    return api, session


def test_oauth_url_uses_pkce_and_registration_context():
    api = LidlPlusApi("de", "at")

    parsed = urlparse(api._register_link)
    query = parse_qs(parsed.query)

    assert parsed.path == "/connect/authorize"
    assert query["client_id"] == ["LidlPlusNativeClient"]
    assert query["redirect_uri"] == ["com.lidlplus.app://callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid profile offline_access lpprofile lpapis"]
    assert query["Country"] == ["AT"]
    assert query["language"] == ["de-AT"]
    assert 43 <= len(api._code_verifier) <= 128


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("com.lidlplus.app://callback?code=plain", "plain"),
        ("https://accounts.lidl.com/callback#code=fragment", "fragment"),
        (
            "https://accounts.lidl.com/login?returnUrl=" "com%3A%2F%2Flidlplus.app%2Fcallback%3Fcode%3Dnested",
            "nested",
        ),
        ("https://accounts.lidl.com/login?error=denied", None),
    ],
)
def test_extract_authorization_code(url, expected):
    assert LidlPlusApi._extract_code_from_url(url) == expected


def test_refresh_token_rotation_and_current_headers():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                }
            )
        ]
    )
    api = LidlPlusApi("en", "gb", refresh_token="old-refresh", session=session)

    headers = api._default_headers()

    assert headers["Authorization"] == "Bearer new-access"
    assert headers["App-Version"] == "17.9.3"
    assert api.refresh_token == "new-refresh"
    assert session.calls[0][2]["data"] == {
        "refresh_token": "old-refresh",
        "grant_type": "refresh_token",
    }


def test_refresh_response_can_omit_refresh_token():
    session = FakeSession([FakeResponse({"access_token": "new-access", "expires_in": 3600})])
    api = LidlPlusApi("en", "gb", refresh_token="existing-refresh", session=session)

    api._default_headers()

    assert api.refresh_token == "existing-refresh"


def test_tickets_follows_pagination_without_extra_request():
    api, session = authenticated_api(
        [
            FakeResponse({"tickets": [{"id": "one"}], "totalCount": 2, "size": 1}),
            FakeResponse({"tickets": [{"id": "two"}], "totalCount": 2, "size": 1}),
        ]
    )

    assert api.tickets() == [{"id": "one"}, {"id": "two"}]
    assert [call[2]["params"]["pageNumber"] for call in session.calls] == [1, 2]
    assert all(call[2]["params"]["onlyFavorite"] == "false" for call in session.calls)


def test_ticket_uses_v3_when_v2_detail_fails():
    api, session = authenticated_api(
        [
            FakeResponse(status_code=404),
            FakeResponse({"id": "receipt", "htmlPrintedReceipt": "<html />"}),
        ]
    )

    detail = api.ticket("receipt")

    assert detail["id"] == "receipt"
    assert "/api/v2/AT/tickets/receipt" in session.calls[0][1]
    assert "/api/v3/AT/tickets/receipt" in session.calls[1][1]


def test_coupon_calls_use_current_routes_and_country_header():
    api, session = authenticated_api(
        [
            FakeResponse({"sections": []}),
            FakeResponse(text=""),
            FakeResponse(text=""),
        ]
    )

    assert api.coupons() == {"sections": []}
    assert api.activate_coupon("coupon-id") == ""
    assert api.deactivate_coupon("coupon-id") == ""

    assert session.calls[0][1].endswith("/app/api/v2/promotionslist")
    assert session.calls[1][1].endswith("/app/api/v1/promotions/coupon-id/activation")
    assert session.calls[2][1].endswith("/app/api/v1/promotions/coupon-id/activation")
    assert [call[0] for call in session.calls] == ["GET", "POST", "DELETE"]
    assert all(call[2]["headers"]["Country"] == "AT" for call in session.calls)
