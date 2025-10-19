import os
import sys
from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Configure database URL before importing application modules
ROOT_DIR = Path(__file__).resolve().parents[1].parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

POSTGRES_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/email_system",
)
os.environ["DATABASE_URL"] = POSTGRES_URL

from app.database import SessionLocal
from data_service.main import app


def _wait_for_db(timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                return
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError("Database not ready for tests") from last_error


@pytest.fixture(scope="session")
def client() -> TestClient:
    _wait_for_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def cleanup_tables():
    with SessionLocal() as db:
        db.execute(text("TRUNCATE TABLE email_attachments CASCADE"))
        db.execute(text("TRUNCATE TABLE emails CASCADE"))
        db.execute(text("TRUNCATE TABLE users CASCADE"))
        db.commit()
