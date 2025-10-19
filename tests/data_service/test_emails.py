from app.database import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _create_user(email: str) -> int:
    with SessionLocal() as db:
        user = User(
            username=email.split("@")[0],
            email=email,
            hashed_password=pwd_context.hash("password"),
            full_name="Recipient User",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def test_create_email(client):
    recipient_id = _create_user("recipient@example.com")
    payload = {
        "subject": "Hello",
        "body": "Hi there",
        "recipient_id": recipient_id,
        "is_external": False,
    }
    response = client.post("/internal/emails", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["subject"] == payload["subject"]
    assert data["recipient_id"] == recipient_id
    assert data["is_external"] is False


def test_list_emails(client):
    recipient_id = _create_user("recipient2@example.com")
    for idx in range(2):
        payload = {
            "subject": f"Message {idx}",
            "recipient_id": recipient_id,
            "is_external": False,
        }
        resp = client.post("/internal/emails", json=payload)
        assert resp.status_code == 201
    list_resp = client.get(f"/internal/emails?recipient_id={recipient_id}")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 2
    subjects = {item["subject"] for item in items}
    assert "Message 0" in subjects and "Message 1" in subjects
