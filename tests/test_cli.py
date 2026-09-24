"""Tests for command-line behavior."""

from datetime import datetime, timezone

from lidlplus.__main__ import _available_coupon, _save_refresh_token


class FakeApi:
    refresh_token = "rotated-refresh-token"


def test_available_coupon_handles_zulu_dates():
    coupon = {
        "isActivated": False,
        "validity": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-12-31T23:59:59Z",
        },
    }

    assert _available_coupon(coupon, datetime(2026, 9, 24, tzinfo=timezone.utc))


def test_available_coupon_rejects_activated_or_expired():
    now = datetime(2026, 9, 24, tzinfo=timezone.utc)
    assert not _available_coupon({"isActivated": True}, now)
    assert not _available_coupon(
        {
            "isActivated": False,
            "validity": {"end": "2026-01-01T00:00:00+00:00"},
        },
        now,
    )


def test_refresh_token_is_saved_with_private_permissions(tmp_path):
    token_file = tmp_path / "config" / "refresh_token"

    _save_refresh_token(FakeApi(), token_file)

    assert token_file.read_text(encoding="utf-8") == "rotated-refresh-token\n"
    assert token_file.stat().st_mode & 0o777 == 0o600
