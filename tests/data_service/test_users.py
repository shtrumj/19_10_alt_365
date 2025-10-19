from app.database import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _create_user(email: str = "user@example.com") -> User:
    with SessionLocal() as db:
        user = User(
            username="user1",
            email=email,
            hashed_password=pwd_context.hash("password"),
            full_name="Test User",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def test_get_user_by_email(client):
    user = _create_user()
    response = client.get(f"/internal/users/by-email?email={user.email}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["email"] == user.email
    assert data["username"] == user.username


def test_get_user_not_found(client):
    response = client.get("/internal/users/by-email?email=missing@example.com")
    assert response.status_code == 404
