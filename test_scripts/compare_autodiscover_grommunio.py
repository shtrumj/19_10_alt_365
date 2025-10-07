"""Compare our XML autodiscover response with grommunio's reference implementation."""
from __future__ import annotations

import os
import sys
import requests
import xml.etree.ElementTree as ET

DEFAULT_EMAIL = os.getenv("TEST_EMAIL", "user@example.com")
DEFAULT_BASE = os.getenv("BASE_URL", "https://localhost:8000")
GOM_URL = os.getenv("GROMMUNIO_URL", "https://demo.grommunio.com")
VERIFY = os.getenv("VERIFY_SSL", "1") not in {"0", "false", "False"}

PAYLOAD = f"""<?xml version='1.0' encoding='utf-8'?>
<Autodiscover xmlns='http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006'>
  <Request>
    <EMailAddress>{DEFAULT_EMAIL}</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>
""".strip()


def fetch(url: str) -> ET.Element:
    resp = requests.post(url, data=PAYLOAD, headers={"Content-Type": "text/xml"}, verify=VERIFY, timeout=20)
    resp.raise_for_status()
    return ET.fromstring(resp.text)


def protocols(tree: ET.Element) -> dict[str, dict[str, str]]:
    protos = {}
    for proto in tree.findall('.//{*}Protocol'):
        ptype = proto.findtext('{*}Type')
        if not ptype:
            continue
        protos[ptype] = {child.tag.split('}')[-1]: child.text or '' for child in list(proto)}
    return protos


def main() -> None:
    ours = fetch(f"{DEFAULT_BASE.rstrip('/')}/Autodiscover/Autodiscover.xml")
    grom = fetch(f"{GOM_URL.rstrip('/')}/Autodiscover/Autodiscover.xml")

    ours_protos = protocols(ours)
    grom_protos = protocols(grom)

    keys = set(ours_protos) | set(grom_protos)
    for key in sorted(keys):
        print(f"\nProtocol {key}")
        ours_fields = ours_protos.get(key, {})
        grom_fields = grom_protos.get(key, {})
        all_fields = set(ours_fields) | set(grom_fields)
        for field in sorted(all_fields):
            ours_val = ours_fields.get(field)
            grom_val = grom_fields.get(field)
            if ours_val != grom_val:
                print(f"  {field}: ours='{ours_val}' grom='{grom_val}'")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
