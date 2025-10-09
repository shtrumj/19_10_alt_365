#!/usr/bin/env python3
"""
Full Outlook Flow Simulation

Covers:
 1) JSON Autodiscover (modern clients)
 2) XML Autodiscover (2006/2006a)
 3) Validate EXCH/EXPR AuthPackage = Ntlm and MAPI URL
 4) MAPI/HTTP authentication negotiation
    - GET /mapi/emsmdb -> 401 with WWW-Authenticate: Negotiate, NTLM
    - HEAD /mapi/emsmdb -> 401 with WWW-Authenticate: Negotiate, NTLM
    - POST empty with Basic -> 401 with WWW-Authenticate: Negotiate, NTLM
    - POST NTLM Type1 -> 401 with NTLM Type2 blob present
 5) EWS reachability (HTTP method/URL sanity)

Outputs a concise pass/fail summary.
"""
import os
import sys
import json
import requests
from urllib.parse import quote

# Configuration
HOST = os.environ.get("EX_HOST", "owa.shtrum.com")
AUTO_HOST = os.environ.get("EX_AUTO_HOST", "autodiscover.shtrum.com")
EMAIL = os.environ.get("EX_EMAIL", "yonatan@shtrum.com")
BASE_URL = f"https://{HOST}"
MAPI_URL = f"{BASE_URL}/mapi/emsmdb"
EWS_URL = f"{BASE_URL}/EWS/Exchange.asmx"

# Unsafe cert OK for test lab
VERIFY = False

NTLM_TYPE1 = "TlRMTVNTUAABAAAAB4IIAAAAAAAAAAAAAAAAAAAAAAA="


def require(cond, msg):
    if not cond:
        raise AssertionError(msg)


def json_autodiscover():
    url = f"https://{AUTO_HOST}/autodiscover/autodiscover.json/v1.0/{quote(EMAIL)}"
    r = requests.get(url, verify=VERIFY)
    print("JSON Autodiscover:", r.status_code)
    require(r.status_code == 200, f"JSON AD expected 200, got {r.status_code}")
    data = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else r.json()
    require("Protocol" in data and data.get("Protocol") in ("Exchange", "EXCH"), "JSON AD protocol invalid")
    return data


def xml_autodiscover():
    url = f"https://{AUTO_HOST}/autodiscover/autodiscover.xml"
    body = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<Autodiscover xmlns='http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006'>"
        f"<Request><EMailAddress>{EMAIL}</EMailAddress>"
        "<AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>"
        "</Request></Autodiscover>"
    )
    r = requests.post(url, data=body, headers={"Content-Type": "text/xml"}, verify=VERIFY)
    print("XML Autodiscover:", r.status_code)
    require(r.status_code == 200, f"XML AD expected 200, got {r.status_code}")
    xml = r.text
    require("<Type>EXCH</Type>" in xml and "<Type>EXPR</Type>" in xml, "Missing EXCH/EXPR blocks")
    require("<AuthPackage>Ntlm</AuthPackage>" in xml, "EXCH/EXPR not advertising NTLM")
    require("/mapi/emsmdb" in xml, "MAPI URL not present")
    return xml


def mapi_negotiate():
    # GET -> 401 Negotiate, NTLM
    r = requests.get(MAPI_URL, verify=VERIFY)
    print("MAPI GET:", r.status_code, r.headers.get("WWW-Authenticate"))
    require(r.status_code == 401, "MAPI GET should be 401")
    wa = r.headers.get("WWW-Authenticate", "")
    require("Negotiate" in wa and "NTLM" in wa, "WWW-Authenticate missing Negotiate, NTLM (GET)")

    # HEAD -> 401 Negotiate, NTLM
    r = requests.head(MAPI_URL, verify=VERIFY)
    print("MAPI HEAD:", r.status_code, r.headers.get("WWW-Authenticate"))
    require(r.status_code == 401, "MAPI HEAD should be 401")
    wa = r.headers.get("WWW-Authenticate", "")
    require("Negotiate" in wa and "NTLM" in wa, "WWW-Authenticate missing Negotiate, NTLM (HEAD)")

    # Empty Basic -> 401 Negotiate, NTLM
    r = requests.post(MAPI_URL, headers={
        "Authorization": "Basic eW9uYXRhbkBzaHRydW0uY29tOkdpYiQwbjU3OSE=",
        "Content-Type": "application/mapi-http",
    }, data=b"", verify=VERIFY)
    print("MAPI Basic-empty POST:", r.status_code, r.headers.get("WWW-Authenticate"))
    require(r.status_code == 401, "Basic-empty should be 401")
    require("NTLM" in r.headers.get("WWW-Authenticate", ""), "Missing NTLM in challenge for Basic-empty")

    # NTLM Type1 -> expect Type2 in header
    r = requests.post(MAPI_URL, headers={
        "Authorization": f"NTLM {NTLM_TYPE1}",
        "Content-Type": "application/mapi-http",
    }, data=b"", verify=VERIFY)
    wa = r.headers.get("WWW-Authenticate", "")
    print("MAPI NTLM Type1:", r.status_code, len(wa), wa[:80])
    require(r.status_code == 401, "NTLM Type1 should be 401")
    require("NTLM " in wa and len(wa.split("NTLM ")[-1]) > len(NTLM_TYPE1), "Type2 not present or too short")


def ews_reachability():
    # EWS generally expects POST SOAP; here just check rejection is not 404
    r = requests.get(EWS_URL, verify=VERIFY)
    print("EWS GET:", r.status_code)
    require(r.status_code in (200, 401, 405), f"Unexpected EWS code {r.status_code}")


def main():
    try:
        print("== JSON Autodiscover ==")
        ja = json_autodiscover()
        print(json.dumps(ja, indent=2)[:200])
        print("\n== XML Autodiscover ==")
        _ = xml_autodiscover()
        print("OK: XML contains EXCH/EXPR NTLM and MAPI URL")
        print("\n== MAPI Negotiation ==")
        mapi_negotiate()
        print("\n== EWS Reachability ==")
        ews_reachability()
        print("\n✅ Full simulation passed")
    except Exception as e:
        print("\n❌ Simulation failed:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
