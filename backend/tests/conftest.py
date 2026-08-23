import os

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TEST_DATABASE_URL", "postgresql://billio:billio@localhost:5432/billio_test")

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db, limiter as _limiter
from app.models import User, UserSettings


@pytest.fixture(scope="session")
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        _db.create_all()
    yield application
    with application.app_context():
        _db.drop_all()


@pytest.fixture(autouse=True)
def _clean_db(app):
    """Truncate every table before each test so tests are isolated without
    paying the cost of drop_all/create_all per test."""
    with app.app_context():
        with _db.engine.begin() as conn:
            table_names = ", ".join(f'"{t.name}"' for t in _db.metadata.sorted_tables)
            conn.exec_driver_sql(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE;")
        try:
            _limiter.reset()
        except Exception:
            pass
    yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    """Factory fixture: create_user(username=..., password=..., **kwargs) -> (User, raw_password)."""

    def _make(username="testuser", password="Str0ngPass!1", first_name="Test", email=None, is_admin=False, timezone="UTC"):
        from app.utils.security import hash_password

        with app.app_context():
            user = User(
                first_name=first_name,
                username=username,
                email=email,
                password_hash=hash_password(password),
                timezone=timezone,
                is_admin=is_admin,
            )
            _db.session.add(user)
            _db.session.flush()
            _db.session.add(UserSettings(user_id=user.id))
            _db.session.commit()
            user_id = user.id
        return user_id, password

    return _make


@pytest.fixture
def auth_headers(client, make_user):
    """Factory fixture: auth_headers(**user_kwargs) -> (headers_dict, user_id)."""

    def _make(**kwargs):
        username = kwargs.get("username", "testuser")
        password = kwargs.get("password", "Str0ngPass!1")
        make_user(**kwargs)
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.get_json()
        token = resp.get_json()["access_token"]
        user_id = resp.get_json()["user"]["id"]
        return {"Authorization": f"Bearer {token}"}, user_id

    return _make
