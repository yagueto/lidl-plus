#!/usr/bin/env python3
"""Lidl Plus command-line tool."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path

import requests

from lidlplus import LidlPlusApi
from lidlplus.exceptions import LegalTermsException, LoginError, WebBrowserException

DEFAULT_TOKEN_FILE = Path.home() / ".config" / "lidl-plus" / "refresh_token"


def get_arguments():
    """Return parsed command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="lidl-plus",
        description="Lidl Plus API",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=28),
    )
    parser.add_argument("-c", "--country", metavar="CC", help="country (DE, BE, NL, AT, ...)")
    parser.add_argument("-l", "--language", metavar="LANG", help="language (de, en, fr, it, ...)")
    parser.add_argument("-u", "--user", help="Lidl Plus login username")
    parser.add_argument("-p", "--password", metavar="XXX", help="Lidl Plus login password")
    parser.add_argument(
        "--2fa",
        choices=["phone", "email"],
        default="phone",
        help="choose two-factor authentication method",
    )
    parser.add_argument("-r", "--refresh-token", metavar="TOKEN", help="refresh token to authenticate")
    parser.add_argument(
        "--token-file",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        help=f"read and update the refresh token in this file (default: {DEFAULT_TOKEN_FILE})",
    )
    parser.add_argument(
        "--not-accept-legal-terms",
        help="do not automatically accept legal term updates",
        action="store_true",
    )
    parser.add_argument(
        "--headless",
        help="run browser login headlessly (may be blocked by anti-bot checks)",
        action="store_true",
    )

    subparsers = parser.add_subparsers(title="commands", metavar="command", dest="command", required=True)
    subparsers.add_parser("auth", help="authenticate and print the refresh token")

    receipt = subparsers.add_parser("receipt", help="save receipts as JSON and HTML")
    receipt.add_argument("-a", "--all", help="fetch all receipts", action="store_true")
    receipt.add_argument("-n", "--limit", type=int, default=1, help="number of recent receipts to fetch")
    receipt.add_argument("-o", "--output-dir", type=Path, default=Path("out"), help="output directory")

    coupon = subparsers.add_parser("coupon", help="list or activate coupons")
    coupon.add_argument("-a", "--all", help="activate every available coupon", action="store_true")

    return vars(parser.parse_args())


def _stored_refresh_token(args):
    token = args.get("refresh_token")
    token_file = args["token_file"].expanduser()
    if token:
        return token
    if args["command"] != "auth" and token_file.is_file():
        return token_file.read_text(encoding="utf-8").strip()
    return ""


def _save_refresh_token(api, token_file):
    token = api.refresh_token
    if not token:
        return
    path = token_file.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as token_stream:
        token_stream.write(f"{token}\n")
    path.chmod(0o600)


def lidl_plus_login(args):
    """Return an authenticated client."""
    language = args.get("language") or input("Enter your language (de, en, ...): ")
    country = args.get("country") or input("Enter your country (DE, AT, ...): ")
    refresh_token = _stored_refresh_token(args)
    if refresh_token:
        return LidlPlusApi(language, country, refresh_token)

    login_method = input("Login with email or phone number? ([e]mail / [p]hone): ").lower()
    if login_method not in {"e", "p"}:
        raise LoginError('Login method must be "e" or "p"')

    prompt = "Enter your Lidl Plus email: " if login_method == "e" else "Enter your Lidl Plus phone number: "
    username = args.get("user") or input(prompt)
    password = args.get("password") or getpass("Enter your Lidl Plus password: ")
    api = LidlPlusApi(language, country)
    verification_prompt = f"Enter the verification code you received via {args['2fa']}: "
    api.login(
        username,
        password,
        login_method,
        verify_token_func=lambda: input(verification_prompt),
        verify_mode=args["2fa"],
        headless=args["headless"],
        accept_legal_terms=not args["not_accept_legal_terms"],
    )
    return api


def print_refresh_token(args):
    """Authenticate, save, and print the refresh token."""
    api = lidl_plus_login(args)
    _save_refresh_token(api, args["token_file"])
    print(api.refresh_token)


def save_tickets(args):
    """Save recent receipt details to disk."""
    if args["limit"] < 1:
        raise ValueError("--limit must be at least 1")

    api = lidl_plus_login(args)
    tickets = api.tickets()
    selected = tickets if args["all"] else tickets[: args["limit"]]
    output_dir = args["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    details = []
    for summary in selected:
        detail = api.ticket(summary["id"])
        details.append(detail)
        receipt_html = detail.get("htmlPrintedReceipt")
        if receipt_html:
            (output_dir / f"{summary['id']}.html").write_text(receipt_html, encoding="utf-8")

    (output_dir / "summary.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _save_refresh_token(api, args["token_file"])
    print(f"Saved {len(details)} receipt(s) to {output_dir}")


def _parse_api_datetime(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _available_coupon(coupon, now):
    if coupon.get("isActivated"):
        return False
    validity = coupon.get("validity", {})
    starts_at = validity.get("start")
    ends_at = validity.get("end")
    return (not starts_at or _parse_api_datetime(starts_at) <= now) and (
        not ends_at or _parse_api_datetime(ends_at) >= now
    )


def activate_coupons(args):
    """List coupons or activate all currently available coupons."""
    api = lidl_plus_login(args)
    coupons = api.coupons()
    if not args["all"]:
        print(json.dumps(coupons, ensure_ascii=False, indent=2))
        _save_refresh_token(api, args["token_file"])
        return

    activated = 0
    now = datetime.now(timezone.utc)
    for section in coupons.get("sections", []):
        for coupon in section.get("promotions", []):
            if _available_coupon(coupon, now):
                api.activate_coupon(coupon["id"])
                activated += 1

    _save_refresh_token(api, args["token_file"])
    print(f"Activated {activated} coupon(s)")


def main():
    """Run the selected command."""
    args = get_arguments()
    if args["command"] == "auth":
        print_refresh_token(args)
    elif args["command"] == "receipt":
        save_tickets(args)
    elif args["command"] == "coupon":
        activate_coupons(args)


def start():
    """Console entry point."""
    try:
        main()
    except KeyboardInterrupt:
        print("Aborted.", file=sys.stderr)
    except WebBrowserException as error:
        print(f"Browser login failed: {error}", file=sys.stderr)
        raise SystemExit(101) from error
    except LoginError as error:
        print(f"Login failed: {error}", file=sys.stderr)
        raise SystemExit(102) from error
    except LegalTermsException as error:
        print(f"Legal terms not accepted: {error}", file=sys.stderr)
        raise SystemExit(103) from error
    except (requests.RequestException, ValueError, KeyError) as error:
        print(f"Request failed: {error}", file=sys.stderr)
        raise SystemExit(104) from error


if __name__ == "__main__":
    start()
