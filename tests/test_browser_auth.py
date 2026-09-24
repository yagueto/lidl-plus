"""Tests for browser authentication helpers."""

import json

from lidlplus.browser_auth import _performance_urls


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


def test_performance_urls_include_redirect_location():
    assert _performance_urls(FakeBrowser()) == [
        "https://accounts.lidl.com/connect/authorize",
        "https://accounts.lidl.com/connect/authorize/callback",
        "com.lidlplus.app://callback?code=authorization-code",
    ]
