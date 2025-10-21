#!/usr/bin/env python3
"""
monitor_activesync_auth.py

Quick test script to try authenticating to an ActiveSync endpoint using:
 - HTTP Basic auth (requests)
 - NTLM (requests + requests-ntlm) -- optional, only attempted if requests_ntlm is installed

Notes / safety:
 - Storing plaintext credentials in files is unsafe. Prefer passing via environment variables
   or prompt when running interactively.
 - This script will attempt an OPTIONS request first (commonly accepted by IIS) then a POST.
 - Some servers require a valid ActiveSync WBXML POST body; for a pure auth check OPTIONS is often sufficient.
 - Replace ENDPOINT below with your target if different.

Usage:
  python monitor_activesync_auth.py
  OR:
  AUTH_USER=yonatan@shtrum.com AUTH_PASS='Gib$0n579!' python monitor_activesync_auth.py

If you really want to hard-code the credentials, you can edit the DEFAULT_USERNAME / DEFAULT_PASSWORD
variables below (not recommended).
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from typing import Tuple

try:
    import requests
except Exception:
    print("This script requires the 'requests' package. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)

# optional NTLM support
try:
    from requests_ntlm import HttpNtlmAuth  # type: ignore
    _HAS_NTLM = True
except Exception:
    _HAS_NTLM = False

# -------------------------
# Default configuration
# -------------------------
ENDPOINT = "https://owa.shtrum.com/Microsoft-Server-ActiveSync"

# Preferred ways to provide credentials:
# 1) Environment variables AUTH_USER and AUTH_PASS
# 2) Command-line args --user / --password
# 3) Prompt on stdin (interactive)
#
# For safety we do NOT hardcode credentials here. If you want to, edit the DEFAULT_* below (NOT recommended).
DEFAULT_USERNAME = None  # e.g. "yonatan@shtrum.com"
DEFAULT_PASSWORD = None  # e.g. "Gib$0n579!"


# -------------------------
# Helpers
# -------------------------
def read_credentials_from_env_or_defaults() -> Tuple[str, str]:
    """
    Returns (username, password). Order of precedence:
      1. env vars AUTH_USER / AUTH_PASS
      2. DEFAULT_USERNAME / DEFAULT_PASSWORD in file
      3. interactive prompt
    """
    user = os.environ.get("AUTH_USER") or DEFAULT_USERNAME
    pwd = os.environ.get("AUTH_PASS") or DEFAULT_PASSWORD

    if user and pwd:
        return user, pwd

    # If running non-interactive and credentials not provided -> error
    if not sys.stdin.isatty():
        raise RuntimeError("Credentials not provided via env and input is not interactive.")

    # interactive prompt fallback
    if not user:
        user = input("ActiveSync username: ").strip()
    if not pwd:
        # don't echo password
        try:
            import getpass
            pwd = getpass.getpass("ActiveSync password: ")
        except Exception:
            pwd = input("ActiveSync password (no getpass available): ")

    return user, pwd


def small_report(resp: requests.Response) -> str:
    """Return a small textual report for a requests.Response"""
    b = []
    b.append(f"HTTP {resp.status_code} {resp.reason}")
    b.append(f"URL: {resp.url}")
    # print a few important headers if present
    for h in ("WWW-Authenticate", "Set-Cookie", "Server", "Server", "X-Powered-By"):
        if h in resp.headers:
            b.append(f"{h}: {resp.headers[h]}")
    # first chunk of body (text)
    try:
        body = resp.text
        if len(body) > 1000:
            body_snip = body[:1000] + "...(truncated)"
        else:
            body_snip = body
        b.append("--- response body snippet ---")
        b.append(body_snip)
    except Exception:
        b.append("(response body not decodable as text)")
    return "\n".join(b)


# -------------------------
# Auth attempts
# -------------------------
def try_options_basic(endpoint: str, username: str, password: str, verify: bool = True, timeout: float = 10.0) -> requests.Response:
    """
    Try an HTTP OPTIONS request using Basic auth. Many IIS servers will respond to OPTIONS
    and this is a lightweight way to verify auth.
    """
    session = requests.Session()
    session.auth = (username, password)
    headers = {
        "User-Agent": "Python-ActiveSync-Test/1.0",
        "Accept": "*/*",
    }
    resp = session.options(endpoint, headers=headers, timeout=timeout, verify=verify)
    return resp


def try_post_basic(endpoint: str, username: str, password: str, verify: bool = True, timeout: float = 10.0) -> requests.Response:
    """
    Try a POST using Basic auth. This sends an empty POST body with a typical ActiveSync User-Agent.
    Servers that require a valid WBXML body may still respond 400/415 etc; for auth purpose 401 is relevant.
    """
    session = requests.Session()
    session.auth = (username, password)
    headers = {
        "User-Agent": "Python-ActiveSync-Test/1.0",
        # Content-Type sometimes expected for ActiveSync; using generic content type for test
        "Content-Type": "application/octet-stream",
        "Accept": "*/*",
    }
    # often ActiveSync clients send specific query parameters - but for pure auth check this is fine.
    resp = session.post(endpoint, headers=headers, data=b"", timeout=timeout, verify=verify)
    return resp


def try_post_basic_with_auth_header(endpoint: str, username: str, password: str, verify: bool = True, timeout: float = 10.0) -> requests.Response:
    """
    Manually construct an Authorization: Basic header and POST. Equivalent to session.auth but sometimes simpler to inspect.
    """
    creds = f"{username}:{password}"
    b64 = base64.b64encode(creds.encode("utf-8")).decode("ascii")
    headers = {
        "User-Agent": "Python-ActiveSync-Test/1.0",
        "Content-Type": "application/octet-stream",
        "Accept": "*/*",
        "Authorization": f"Basic {b64}",
    }
    resp = requests.post(endpoint, headers=headers, data=b"", timeout=timeout, verify=verify)
    return resp


def try_ntlm(endpoint: str, username: str, password: str, verify: bool = True, timeout: float = 10.0) -> requests.Response:
    """
    Try NTLM authentication if requests-ntlm is installed.
    Note: For NTLM you usually use username in 'DOMAIN\\user' or 'user@domain' forms depending on server.
    """
    if not _HAS_NTLM:
        raise RuntimeError("requests-ntlm not installed (pip install requests-ntlm)")

    session = requests.Session()
    session.auth = HttpNtlmAuth(username, password, session)
    headers = {
        "User-Agent": "Python-ActiveSync-Test/1.0",
        "Accept": "*/*",
    }
    # Trying an OPTIONS first (NTLM can require handshake; requests-ntlm handles it)
    resp = session.options(endpoint, headers=headers, timeout=timeout, verify=verify)
    return resp


# -------------------------
# Main CLI
# -------------------------
def main() -> None:
    ap = argparse.ArgumentParser(prog="monitor_activesync_auth.py", description="Try authenticating to an ActiveSync endpoint (Basic and NTLM attempts).")
    ap.add_argument("--endpoint", "-e", help="ActiveSync endpoint URL", default=ENDPOINT)
    ap.add_argument("--user", "-u", help="Username (overrides env/default)", default=None)
    ap.add_argument("--password", "-p", help="Password (overrides env/default). If omitted, will prompt.", default=None)
    ap.add_argument("--no-verify-tls", action="store_true", help="Disable TLS certificate verification (for lab/self-signed).")
    ap.add_argument("--timeout", type=float, default=15.0, help="Request timeout seconds")
    ap.add_argument("--try-ntlm", action="store_true", help="Also attempt NTLM auth if requests-ntlm is installed")
    ap.add_argument("--retry", type=int, default=1, help="How many times to retry each attempt on network errors")
    args = ap.parse_args()

    # get credentials
    username = args.user
    password = args.password
    if not username or not password:
        try:
            env_user, env_pass = read_credentials_from_env_or_defaults()
            # don't overwrite if CLI provided
            if not username:
                username = env_user
            if not password:
                password = env_pass
        except Exception as ex:
            print("ERROR while obtaining credentials:", ex, file=sys.stderr)
            sys.exit(2)

    verify = not args.no_verify_tls
    endpoint = args.endpoint

    print("=== ActiveSync auth tester ===")
    print(f"Endpoint: {endpoint}")
    print(f"User: {username}")
    print(f"TLS verify: {verify}")
    print(f"NTLM attempt enabled: {args.try_ntlm and _HAS_NTLM}")
    print()

    # small helper for retries
    def attempt_with_retries(func, *fargs, tries=args.retry):
        last_exc = None
        for i in range(tries):
            try:
                return func(*fargs)
            except Exception as e:
                last_exc = e
                print(f"Attempt {i+1}/{tries} failed: {e}")
                time.sleep(0.5)
        raise last_exc

    # 1) Try OPTIONS with Basic
    print("-> Trying OPTIONS with Basic auth ...")
    try:
        resp = attempt_with_retries(try_options_basic, endpoint, username, password, verify, args.timeout)
        print(small_report(resp))
    except Exception as e:
        print("OPTIONS Basic attempt failed:", e)

    print("\n-> Trying POST with Basic auth (requests.Session auth)...")
    try:
        resp = attempt_with_retries(try_post_basic, endpoint, username, password, verify, args.timeout)
        print(small_report(resp))
    except Exception as e:
        print("POST Basic attempt failed:", e)

    print("\n-> Trying POST with manual Authorization header (Basic)...")
    try:
        resp = attempt_with_retries(try_post_basic_with_auth_header, endpoint, username, password, verify, args.timeout)
        print(small_report(resp))
    except Exception as e:
        print("POST + header attempt failed:", e)

    # 2) Try NTLM if requested and available
    if args.try_ntlm:
        if not _HAS_NTLM:
            print("\nNOTE: requests-ntlm not installed. Install with: pip install requests-ntlm")
        else:
            print("\n-> Trying NTLM (OPTIONS) ...")
            try:
                resp = attempt_with_retries(try_ntlm, endpoint, username, password, verify, args.timeout)
                print(small_report(resp))
            except Exception as e:
                print("NTLM attempt failed:", e)

    # Guidance for interpreting results
    print("\n=== Interpretation help ===")
    print(" - 200 / 204 : request succeeded (may still be an application-level response).")
    print(" - 401 : authentication required / credentials rejected (for Basic/Negotiate).")
    print(" - 403 : forbidden (might indicate auth succeeded but resource forbidden, or other policy).")
    print(" - WWW-Authenticate header (if present) helps: e.g. 'Negotiate', 'NTLM', 'Basic' indicates supported schemes.")
    print("\nIf you get 401 but see 'WWW-Authenticate: Negotiate' or 'NTLM', the server prefers Windows integrated auth.")
    print("If testing over TLS with a self-signed cert, use --no-verify-tls to bypass cert verification (lab only).")


if __name__ == "__main__":
    main()
