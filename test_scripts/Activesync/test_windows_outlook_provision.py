"""Simple smoke test that exercises the ActiveSync Provision flow with
Windows Outlook style query parameters.

This mirrors the minimal grommunio provision handshake:
 1. OPTIONS call (optional, primes auth)
 2. Initial Provision command (no PolicyKey sent) -> expect X-MS-PolicyKey
 3. Provision acknowledgement with returned PolicyKey -> server should mark
device as provisioned

The test simply asserts we do not get 500/449 and that the device is persisted
with a non-zero policy key, which Outlook requires to proceed to FolderSync.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

# Allow running from repository root
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.database import SessionLocal, ActiveSyncDevice  # noqa: E402


EAS_BASE_URL = os.getenv(
    "EAS_URL", "https://owa.shtrum.com/Microsoft-Server-ActiveSync"
)
EAS_USER = os.getenv("EAS_USER", "yonatan@shtrum.com")
EAS_PASSWORD = os.getenv("EAS_PASSWORD", "Gib$0n579!")
TEST_DEVICE_ID = os.getenv("EAS_TEST_DEVICE", "TEST-WINDOWS-OUTLOOK")
TEST_DEVICE_TYPE = os.getenv("EAS_TEST_DEVICE_TYPE", "WindowsOutlook15")

INITIAL_PROVISION_XML = """<?xml version='1.0' encoding='utf-8'?>
<Provision xmlns='Provision'>
  <Policies>
    <Policy>
      <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
    </Policy>
  </Policies>
</Provision>
"""

ACK_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
<Provision xmlns='Provision'>
  <Status>1</Status>
  <Policies>
    <Policy>
      <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
      <PolicyKey>{policy_key}</PolicyKey>
      <Status>1</Status>
    </Policy>
  </Policies>
</Provision>
"""


def _call(session: requests.Session, params: dict, body: str | bytes = b"", **extra_headers) -> requests.Response:
    headers = {"Content-Type": "application/xml"}
    headers.update(extra_headers)
    resp = session.post(EAS_BASE_URL, params=params, data=body, headers=headers)
    return resp


def _ensure_device_cleanup() -> None:
    """Remove previous state for deterministic runs."""
    db = SessionLocal()
    try:
        device = (
            db.query(ActiveSyncDevice)
            .filter(
                ActiveSyncDevice.user_id.isnot(None),
                ActiveSyncDevice.device_id == TEST_DEVICE_ID,
            )
            .first()
        )
        if device:
            db.delete(device)
            db.commit()
    finally:
        db.close()


def fetch_device() -> Optional[ActiveSyncDevice]:
    db = SessionLocal()
    try:
        return (
            db.query(ActiveSyncDevice)
            .filter(ActiveSyncDevice.device_id == TEST_DEVICE_ID)
            .first()
        )
    finally:
        db.close()


def main() -> None:
    _ensure_device_cleanup()

    session = requests.Session()
    session.auth = HTTPBasicAuth(EAS_USER, EAS_PASSWORD)

    # Step 1: OPTIONS sanity check (optional but mirrors real clients)
    opt = session.options(EAS_BASE_URL)
    print("OPTIONS status:", opt.status_code)

    base_params = {
        "DeviceId": TEST_DEVICE_ID,
        "DeviceType": TEST_DEVICE_TYPE,
    }

    # Step 2: initial Provision request - expect a non-zero X-MS-PolicyKey
    initial = _call(session, {"Cmd": "Provision", **base_params}, body=INITIAL_PROVISION_XML)
    print("Initial Provision status:", initial.status_code)
    policy_key = initial.headers.get("X-MS-PolicyKey")
    if not policy_key or policy_key == "0":
        raise SystemExit(f"Server did not return a usable PolicyKey (got {policy_key!r})")

    # Step 3: acknowledgement echoing PolicyKey -> should succeed
    ack_body = ACK_TEMPLATE.format(policy_key=policy_key)
    ack = _call(
        session,
        {"Cmd": "Provision", **base_params},
        body=ack_body,
        **{"X-MS-PolicyKey": policy_key},
    )
    print("Provision ACK status:", ack.status_code)
    if ack.status_code >= 400:
        raise SystemExit(f"Provision ACK failed with status {ack.status_code}")

    # Verify device persisted
    device = fetch_device()
    if not device:
        raise SystemExit("No ActiveSync device record persisted for test device")
    print(
        "Device record:",
        device.device_id,
        device.device_type,
        device.policy_key,
        device.is_provisioned,
    )
    if device.policy_key in (None, "", "0"):
        raise SystemExit("Device policy key not persisted")
    if device.is_provisioned != 1:
        raise SystemExit("Device not marked as provisioned")

    print("Provision smoke test completed successfully")


if __name__ == "__main__":
    main()
