import base64
import os
import sys

import pytest

sys.path.append(os.path.abspath("."))

pytest.importorskip("fastapi")
pytest.importorskip("passlib")

TEST_EMAIL = "activesync_tester@example.com"
TEST_USERNAME = "activesync_tester"
TEST_PASSWORD = "Passw0rd!"
TEST_DEVICE_ID = "UNITTESTDEVICE123"


def _ensure_user_and_device(SessionLocal, User, ActiveSyncDevice, ActiveSyncState, CryptContext):
    db = SessionLocal()
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    try:
        user = (
            db.query(User)
            .filter((User.email == TEST_EMAIL) | (User.username == TEST_USERNAME))
            .first()
        )
        if not user:
            user = User(
                email=TEST_EMAIL,
                username=TEST_USERNAME,
                full_name="ActiveSync Tester",
                hashed_password=pwd_context.hash(TEST_PASSWORD),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # ensure password known for tests
            user.hashed_password = pwd_context.hash(TEST_PASSWORD)
            db.commit()

        device = (
            db.query(ActiveSyncDevice)
            .filter(
                ActiveSyncDevice.user_id == user.id,
                ActiveSyncDevice.device_id == TEST_DEVICE_ID,
            )
            .first()
        )
        if not device:
            device = ActiveSyncDevice(
                user_id=user.id,
                device_id=TEST_DEVICE_ID,
                device_type="TestDevice",
                is_provisioned=1,
            )
            db.add(device)
            db.commit()
        else:
            device.is_provisioned = 1
            db.commit()

        # Reset folder sync state for collection_id "0"
        state = (
            db.query(ActiveSyncState)
            .filter(
                ActiveSyncState.user_id == user.id,
                ActiveSyncState.device_id == TEST_DEVICE_ID,
                ActiveSyncState.collection_id == "0",
            )
            .first()
        )
        if not state:
            state = ActiveSyncState(
                user_id=user.id,
                device_id=TEST_DEVICE_ID,
                collection_id="0",
                sync_key="0",
                last_synced_email_id=0,
            )
            db.add(state)
        else:
            state.sync_key = "0"
            state.last_synced_email_id = 0
            state.pending_sync_key = None
            state.pending_max_email_id = None
            state.pending_item_ids = None
            state.synced_email_ids = None
        db.commit()
    finally:
        db.close()


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def test_initial_foldersync_returns_wbxml():
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from passlib.context import CryptContext
        from app.database import SessionLocal, User, ActiveSyncDevice, ActiveSyncState
        from app.routers import activesync
    except ModuleNotFoundError as exc:
        pytest.skip(f"Required module not available: {exc}")

    _ensure_user_and_device(SessionLocal, User, ActiveSyncDevice, ActiveSyncState, CryptContext)

    app = FastAPI()
    app.include_router(activesync.router)
    client = TestClient(app)

    body = b"\x03\x01j\x00\x00\x07VR\x030\x00\x01\x01"
    params = {
        "Cmd": "FolderSync",
        "User": TEST_EMAIL,
        "DeviceId": TEST_DEVICE_ID,
        "DeviceType": "iPhone",
    }
    headers = {
        "Authorization": _basic_auth_header(TEST_EMAIL, TEST_PASSWORD),
        "Content-Type": "application/vnd.ms-sync.wbxml",
    }

    response = client.post(
        "/activesync/Microsoft-Server-ActiveSync",
        params=params,
        data=body,
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("Content-Type") == "application/vnd.ms-sync.wbxml"
    assert len(response.content) > 0
