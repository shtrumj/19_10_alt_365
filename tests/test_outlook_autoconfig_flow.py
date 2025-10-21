#!/usr/bin/env python3
"""
End-to-end smoke test for Outlook style auto-configuration.

This script simulates the exact sequence Outlook performs:
1. JSON Autodiscover request
2. MAPI probe (GET/HEAD/empty Basic POST)

It provides fast validation that the key HTTPS endpoints are alive and
return the headers Outlook expects before it proceeds to the NTLM handshake.
"""
import os

import requests

# Silence CERT warnings – this test targets the live server
requests.packages.urllib3.disable_warnings()  # type: ignore

BASE_HOST = os.getenv("AUTOCONFIG_BASE", "https://owa.shtrum.com")
AUTODISCOVER_HOST = os.getenv("AUTOCONFIG_AUTODISCOVER", "https://autodiscover.shtrum.com")
TEST_EMAIL = os.getenv("AUTOCONFIG_EMAIL", "yonatan@shtrum.com")


def assert_www_auth(header_value: str, *needles: str) -> None:
    lowered = header_value.lower()
    for needle in needles:
        if needle.lower() not in lowered:
            raise AssertionError(f"WWW-Authenticate missing '{needle}' -> {header_value}")


def test_autodiscover_json():
    url = (
        f"{AUTODISCOVER_HOST.rstrip('/')}/autodiscover/autodiscover.json/v1.0/{TEST_EMAIL}"
        "?Protocol=AutodiscoverV1&RedirectCount=1"
    )
    resp = requests.get(url, timeout=15, verify=False)
    assert resp.status_code == 200, f"Autodiscover JSON failed: {resp.status_code}"
    assert resp.headers.get("Content-Type", "").startswith("application/json"), resp.headers
    payload = resp.json()
    assert payload, "Autodiscover payload empty"


def test_mapi_probe_sequence():
    target = f"{BASE_HOST.rstrip('/')}/mapi/emsmdb"

    # Outlook GET probe
    get_resp = requests.get(target, timeout=10, verify=False)
    assert get_resp.status_code == 401, f"GET probe expected 401, got {get_resp.status_code}"
    assert_www_auth(get_resp.headers.get("WWW-Authenticate", ""), "Negotiate", "NTLM")

    # Outlook HEAD probe
    head_resp = requests.head(target, timeout=10, verify=False)
    assert head_resp.status_code == 401, f"HEAD probe expected 401, got {head_resp.status_code}"
    assert_www_auth(head_resp.headers.get("WWW-Authenticate", ""), "Negotiate", "NTLM")

    # Empty Basic POST should now also trigger a challenge (no 200 short-circuit)
    basic_token = "Basic eW9uYXRhbkBzaHRydW0uY29tOkdpYiQwbjU3OSE="
    post_resp = requests.post(
        target,
        headers={"Authorization": basic_token, "Content-Type": "application/mapi-http"},
        data=b"",
        timeout=10,
        verify=False,
    )
    assert post_resp.status_code == 401, f"Basic probe expected 401, got {post_resp.status_code}"
    assert_www_auth(post_resp.headers.get("WWW-Authenticate", ""), "Negotiate", "NTLM")
