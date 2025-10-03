#!/usr/bin/env python3
"""
MAPI/HTTP Negotiation Tests

Validates that the server advertises proper authentication schemes and
responds with the expected challenges for probe requests.

Checks:
 1) GET /mapi/emsmdb returns 401 with WWW-Authenticate: Negotiate, NTLM
 2) HEAD /mapi/emsmdb returns 401 with WWW-Authenticate: Negotiate, NTLM
 3) Empty Basic POST returns 401 with WWW-Authenticate: Negotiate, NTLM
 4) NTLM Type 1 POST returns 401 with a NTLM Type 2 challenge
"""
import os
import sys
import requests

BASE_URL = os.environ.get("MAPI_BASE", "https://owa.shtrum.com")
TARGET = f"{BASE_URL}/mapi/emsmdb"

# NTLM Type 1 (negotiate) token (generic)
NTLM_TYPE1 = "TlRMTVNTUAABAAAAB4IIAAAAAAAAAAAAAAAAAAAAAAA="


def assert_header_contains(headers, name, *needles):
    value = headers.get(name)
    if value is None:
        raise AssertionError(f"Missing header {name}")
    for n in needles:
        if n.lower() not in value.lower():
            raise AssertionError(f"Header {name} missing '{n}': {value}")


def test_get_probe():
    r = requests.get(TARGET, verify=False)
    print("GET status:", r.status_code)
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    assert_header_contains(r.headers, "WWW-Authenticate", "Negotiate", "NTLM")
    assert r.headers.get("Content-Type") == "application/mapi-http"


def test_head_probe():
    r = requests.head(TARGET, verify=False)
    print("HEAD status:", r.status_code)
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    assert_header_contains(r.headers, "WWW-Authenticate", "Negotiate", "NTLM")


def test_empty_basic_post():
    r = requests.post(
        TARGET,
        headers={
            "Authorization": "Basic eW9uYXRhbkBzaHRydW0uY29tOkdpYiQwbjU3OSE=",
            "Content-Type": "application/mapi-http",
        },
        data=b"",
        verify=False,
    )
    print("Empty Basic POST status:", r.status_code)
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    assert_header_contains(r.headers, "WWW-Authenticate", "Negotiate", "NTLM")


def test_ntlm_type1_probe():
    r = requests.post(
        TARGET,
        headers={
            "Authorization": f"NTLM {NTLM_TYPE1}",
            "Content-Type": "application/mapi-http",
        },
        data=b"",
        verify=False,
    )
    print("NTLM Type1 POST status:", r.status_code)
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    # Expect a server NTLM Type 2 token in the header (longer blob)
    wa = r.headers.get("WWW-Authenticate", "")
    if "NTLM " not in wa:
        raise AssertionError(f"Expected NTLM challenge in WWW-Authenticate, got: {wa}")
    token = wa.split("NTLM ")[-1].strip()
    print("Type2 token length:", len(token))
    assert len(token) > len(NTLM_TYPE1), "Type2 challenge should be longer than Type1 negotiate"


def main():
    try:
        test_get_probe()
        test_head_probe()
        test_empty_basic_post()
        test_ntlm_type1_probe()
        print("\nAll negotiation tests passed")
    except Exception as e:
        print("\nTest failed:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
