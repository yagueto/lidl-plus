# Python Lidl Plus API

> [!WARNING]
> This unofficial package uses reverse-engineered Lidl Plus endpoints. It is not affiliated with Lidl, and private
> endpoints can change without notice.

Fetch digital receipts, list coupons, and activate or deactivate coupons from Python or the command line.

Python 3.10 or newer is required.

## Installation

Install the base client:

```bash
pip install lidl-plus
```

Install browser authentication support when you need to obtain a refresh token:

```bash
pip install "lidl-plus[auth]"
```

The authentication extra uses Selenium 4 and Selenium Manager. It no longer depends on Selenium Wire, a separately
downloaded driver, `oic`, or the old Blinker compatibility pin. Install Chrome, Edge, or Firefox before authenticating.

For a development checkout:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements_dev.txt
```

## Authentication

Lidl authentication uses OAuth 2.0 with PKCE. The command opens a visible browser because Lidl's current login page
uses browser device checks and reCAPTCHA. Complete any challenge in the opened window.

```bash
lidl-plus --language de --country AT auth
```

The refresh token is printed and saved with owner-only permissions to:

```text
~/.config/lidl-plus/refresh_token
```

Subsequent CLI calls read that file automatically and replace it when Lidl rotates the token. Use `--token-file` to
choose another location, or `--refresh-token` to provide a token directly. `--headless` is available, but Lidl may
reject headless browser sessions.

Python authentication:

```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi(language="de", country="AT")
lidl.login(
    login="name@example.com",
    password="password",
    method="e",
    verify_token_func=lambda: input("Verification code: "),
)
print(lidl.refresh_token)
```

Use `method="p"` for a phone-number login. Browser authentication is only required to obtain the initial refresh
token.

## Receipts

Save the newest receipt:

```bash
lidl-plus --language de --country AT receipt
```

Save a specific number or every receipt:

```bash
lidl-plus --language de --country AT receipt --limit 10
lidl-plus --language de --country AT receipt --all --output-dir receipts
```

The command writes receipt details to `summary.json` and saves printable HTML when the API provides it.

Python:

```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi("de", "AT", refresh_token="...")
for receipt in lidl.tickets():
    detail = lidl.ticket(receipt["id"])
    print(detail)

# Persist this value after authenticated calls because Lidl rotates refresh tokens.
print(lidl.refresh_token)
```

The receipt detail call tries the v2 endpoint first and falls back to v3 for countries where v2 rejects receipt IDs.

## Coupons

List coupons:

```bash
lidl-plus --language de --country AT coupon
```

Activate every currently valid, inactive coupon:

```bash
lidl-plus --language de --country AT coupon --all
```

Python:

```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi("de", "AT", refresh_token="...")
coupons = lidl.coupons()

for section in coupons.get("sections", []):
    for coupon in section.get("promotions", []):
        print(coupon["title"], coupon["id"])

lidl.activate_coupon("coupon-id")
lidl.deactivate_coupon("coupon-id")
```

Coupon calls use the current `/app/api` routes and send the required `Country` header.

## Development

```bash
.venv/bin/python -m pytest
.venv/bin/flake8 lidlplus tests setup.py --max-line-length=120
.venv/bin/pylint --max-line-length=120 lidlplus
.venv/bin/mypy lidlplus
.venv/bin/black --check --line-length=120 lidlplus tests setup.py
```
