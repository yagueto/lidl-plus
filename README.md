**This python package is unofficial and is not related in any way to Lidl. It was developed by reversed engineered requests and can stop working at anytime!**

> [!IMPORTANT]
> Auth and ticket download are working as of August 2025. This fork fixes errors after Lidl's API changes.
> Many changes are based upon other user's reports on @Andre0512's repo, as well as my own research


# Python Lidl Plus API

Fetch receipts, activate cupons and more. Useful to analyse spending patterns, find the date of a specific lost ticket (think of warranties!), etc
## Installation
> [!IMPORTANT]
> The version on PyPi is currently broken. To run, clone or download the repo directly, and install the requirements with "pip install -r requirements.txt"

```bash
pip install lidl-plus
```

## Authentication
To login in Lidl Plus we need to simulate the app login.
This is a bit complicated, we need a web browser and some additional python packages.
After we have received the token once, we can use it for further requestes and we don't need a browser anymore.

#### Prerequisites
* Check you have installed one of the supported web browser
  - Chromium
  - Google Chrome
  - Mozilla Firefox [tested August 2025, working]
  - Microsoft Edge
* Install additional python packages
  ```bash
  pip install "lidl-plus[auth]"
  ```
#### Commandline-Tool
```bash
$ lidl-plus auth
Enter your language (de, en, ...): de
Enter your country (DE, AT, ...): AT
Enter your lidl plus username (phone number): +4915784632296
Enter your lidl plus password:
Enter the verify code you received via phone: 590287
------------------------- refresh token ------------------------
2D4FC2A699AC703CAB8D017012658234917651203746021A4AA3F735C8A53B7F
----------------------------------------------------------------
```

#### Python
```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi(language="de", country="AT")
lidl.login(phone="+4915784632296", password="password", verify_token_func=lambda: input("Insert code: "))
print(lidl.refresh_token)
```
## Usage
Currently, the only features are fetching receipts and activating coupons
### Receipts

Get your receipts as json and receive a list of bought items like:
```json
{
    "currentUnitPrice": "2,19",
    "quantity": "1",
    "isWeight": false,
    "originalAmount": "2,19",
    "name": "Vegane Frikadellen",
    "taxGroup": "1",
    "taxGroupName": "A",
    "codeInput": "4023456245134",
    "discounts": [
        {
            "description": "5€ Coupon",
            "amount": "0,21"
        }
    ],
    "deposit": null,
    "giftSerialNumber": null
},
```

#### Commandline-Tool
> [!IMPORTANT]
> Now it's no longer required to specify the "--all" flag, it will always ask and will automatically save them. 
```bash
$ lidl-plus --language=de --country=AT --refresh-token=XXXXX receipt
```

#### Python
```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi("de", "AT", refresh_token="XXXXXXXXXX")
for receipt in lidl.tickets():
    pprint(lidl.ticket(receipt["id"]))
```

### Coupons

You can list all coupons and activate/deactivate them by id
```json
{
    "sections": [
        {
            "name": "FavoriteStore",
            "coupons": []
        },
        {
            "name": "AllStores",
            "coupons": [
                {
                    "id": "2c9b3554-a09c-412c-8be4-d41cbff13572",
                    "image": "https://lidlplusprod.blob.core.windows.net/images/coupons/LT/IDISC0000254911.png?t=1695452076",
                    "type": "Standard",
                    "offerTitle": "1 + 1",
                    "title": "👨🏻‍🍳 Frozen 👨🏻‍🍳",
                    "offerDescriptionShort": "FREE",
                    "isSegmented": false,
                    "startValidityDate": "2023-09-24T21:00:00Z",
                    "endValidityDate": "2023-10-01T20:59:59Z",
                    "isActivated": false,
                    "apologizeText": "Xxxxxxxxxxxxxxxxx",
                    "apologizeStatus": false,
                    "apologizeTitle": "Xxxxxxxxxxxxxxxxxxx",
                    "promotionId": "DISC0000254911",
                    "tagSpecial": "",
                    "firstColor": "#ffc700",
                    "secondaryColor": null,
                    "firstFontColor": "#4a4a4a",
                    "secondaryFontColor": null,
                    "isSpecial": false,
                    "hasAsterisk": false,
                    "isHappyHour": false,
                    "stores": []
                },
                .......
            ]
        },
        {
            "name": "OtherStores",
            "coupons": []
        }
    ]
}
```

#### Commandline-Tool

Activate all available coupons

```bash
$ lidl-plus --language=de --country=AT --refresh-token=XXXXX coupon --all
```

#### Python
```python
from lidlplus import LidlPlusApi

lidl = LidlPlusApi("de", "AT", refresh_token="XXXXXXXXXX")
for section in lidl.coupons()["sections"]:
  for coupon in section["coupons"]:
    print("found coupon: ", coupon["title"], coupon["id"])
```

## Help
#### Commandline-Tool
```commandline
Lidl Plus API

options:
  -h, --help                show this help message and exit
  -c CC, --country CC       country (DE, BE, NL, AT, ...)
  -l LANG, --language LANG  language (de, en, fr, it, ...)
  -u USER, --user USER      Lidl Plus login username
  -p XXX, --password XXX    Lidl Plus login password
  --2fa {phone,email}       choose two factor auth method
  -r TOKEN, --refresh-token TOKEN
                            refresh token to authenticate
  --skip-verify             skip ssl verification
  --not-accept-legal-terms  not auto accept legal terms updates
  -d, --debug               debug mode

commands:
  auth                      authenticate and get token
  receipt                   output last receipts as json
  coupon                    activate coupons
```


