"""Validate Outlook Autodiscover compatibility for SkyShift.Dev.

Usage:
    BASE_URL=https://owa.shtrum.com python test_scripts/test_outlook_autodiscover.py

The script posts the standard Autodiscover XML request and verifies that
critical Outlook protocols (EXCH/EXPR/MobileSync/WEB) are present with the
expected fields. It also checks the JSON Autodiscover variant used by modern
clients.
"""

from __future__ import annotations

import os
import sys
import textwrap
import xml.etree.ElementTree as ET

import requests


DEFAULT_BASE_URL = "https://localhost:8000"
DEFAULT_EMAIL = "user@example.com"


def _bool(value: str | None) -> bool:
    return value is not None and value.lower() in {"true", "on", "yes", "1"}


def fetch_autodiscover_xml(base_url: str, email_address: str, verify_ssl: bool) -> str:
    payload = textwrap.dedent(
        f"""
        <?xml version="1.0" encoding="utf-8"?>
        <Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
          <Request>
            <EMailAddress>{email_address}</EMailAddress>
            <AcceptableResponseSchema>
              http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a
            </AcceptableResponseSchema>
          </Request>
        </Autodiscover>
        """
    ).strip()

    url = f"{base_url.rstrip('/')}/Autodiscover/Autodiscover.xml"
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "text/xml"},
        verify=verify_ssl,
        timeout=15,
    )
    response.raise_for_status()
    return response.text


def validate_xml(xml_text: str) -> None:
    root = ET.fromstring(xml_text)
    protocols = {}
    for proto in root.findall('.//{*}Protocol'):
        proto_type = proto.findtext('{*}Type')
        if proto_type:
            protocols[proto_type] = {child.tag.split('}')[-1]: child.text for child in proto}

    missing = {"EXCH", "EXPR", "MobileSync", "WEB"} - set(protocols)
    if missing:
        raise AssertionError(f"Missing required protocols in XML response: {missing}")

    exch = protocols["EXCH"]
    expr = protocols["EXPR"]

    def require(proto: dict[str, str | None], field: str) -> str:
        value = proto.get(field)
        if value in (None, ""):
            raise AssertionError(f"Protocol {proto.get('Type', 'UNKNOWN')} missing field '{field}'")
        return value

    require(exch, "Server")
    require(exch, "Port")
    require(exch, "SSL")
    require(exch, "LoginName")
    require(exch, "EwsUrl")
    require(exch, "ASUrl")
    require(exch, "MapiHttpServerUrl")
    if not _bool(exch.get("MapiHttpEnabled")):
        raise AssertionError("EXCH protocol must advertise MapiHttpEnabled")

    require(expr, "Server")
    require(expr, "Port")
    require(expr, "SSL")
    require(expr, "LoginName")
    require(expr, "EwsUrl")
    require(expr, "ASUrl")


def validate_json(base_url: str, email_address: str, verify_ssl: bool) -> None:
    url = f"{base_url.rstrip('/')}/autodiscover/autodiscover.json/v1.0/{email_address}"
    response = requests.get(url, verify=verify_ssl, timeout=15)
    response.raise_for_status()
    payload = response.json()

    protocols = {proto["Type"]: proto for proto in payload.get("Protocol", [])}
    for key in ("EXCH", "EXPR"):
        if key not in protocols:
            raise AssertionError(f"JSON autodiscover missing {key} protocol")

    exch = protocols["EXCH"]
    expr = protocols["EXPR"]

    for proto, name in ((exch, "EXCH"), (expr, "EXPR")):
        for field in ("Server", "Port", "SSL", "AuthPackage", "LoginName", "EwsUrl", "ASUrl"):
            if not proto.get(field):
                raise AssertionError(f"{name} JSON autodiscover missing '{field}'")

    if not exch.get("MapiHttpServerUrl"):
        raise AssertionError("JSON EXCH protocol missing MapiHttpServerUrl")


def main() -> None:
    base_url = os.getenv("BASE_URL", DEFAULT_BASE_URL)
    email_address = os.getenv("TEST_EMAIL", DEFAULT_EMAIL)
    verify_ssl = os.getenv("VERIFY_SSL", "1") not in {"0", "false", "False"}

    print(f"Testing autodiscover endpoints at {base_url} for {email_address}")

    xml_text = fetch_autodiscover_xml(base_url, email_address, verify_ssl)
    validate_xml(xml_text)
    print("✔ XML autodiscover passed protocol validation")

    validate_json(base_url, email_address, verify_ssl)
    print("✔ JSON autodiscover passed protocol validation")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - simple CLI tool
        print(f"❌ Autodiscover validation failed: {exc}")
        sys.exit(1)
