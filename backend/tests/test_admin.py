from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import admin
from app.login import current_user
from app.main import app
from app.registration import RegisteredUser


client = TestClient(app)
users_url = "/api/admin/users"


@pytest.fixture
def db_connect(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(admin.psycopg, "connect", connect)
    return connect


def test_signed_out_user_cannot_list_users(db_connect):
    response = client.get(users_url)

    assert response.status_code == 401
    db_connect.assert_not_called()


@pytest.mark.parametrize("role", ["Applicant", "Reviewer"])
def test_non_admin_cannot_list_users(monkeypatch, db_connect, role):
    user = RegisteredUser(id=1, email="user@example.com", role=role)
    monkeypatch.setitem(app.dependency_overrides, current_user, lambda: user)

    response = client.get(users_url)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"
    db_connect.assert_not_called()


def test_admin_can_list_users(monkeypatch, db_connect):
    user = RegisteredUser(id=1, email="admin@example.com", role="Admin")
    monkeypatch.setitem(app.dependency_overrides, current_user, lambda: user)

    connection = db_connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        (1, "admin@example.com", "Admin"),
        (2, "applicant@example.com", "Applicant"),
    ]

    response = client.get(users_url)

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "email": "admin@example.com", "role": "Admin"},
        {"id": 2, "email": "applicant@example.com", "role": "Applicant"},
    ]


@pytest.mark.parametrize(("role", "status"), [(None, 401), ("Applicant", 403), ("Reviewer", 403)])
def test_role_edit_requires_admin(monkeypatch, db_connect, role, status):
    if role:
        actor = RegisteredUser(id=1, email="actor@example.com", role=role)
        monkeypatch.setitem(app.dependency_overrides, current_user, lambda: actor)
    assert client.patch(users_url + "/2/role", json={"role": "Reviewer"}).status_code == status
    db_connect.assert_not_called()


def test_admin_changes_role(monkeypatch, db_connect):
    actor = RegisteredUser(id=1, email="admin@example.com", role="Admin")
    monkeypatch.setitem(app.dependency_overrides, current_user, lambda: actor)
    connection = db_connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [(1, "Admin"), (2, "Applicant")]
    connection.execute.return_value.fetchone.return_value = (2, "other@example.com", "Reviewer")
    response = client.patch(users_url + "/2/role", json={"role": "Reviewer"})
    assert response.status_code == 200
    assert response.json()["role"] == "Reviewer"
    assert connection.execute.call_args.args[1] == ("Reviewer", 2)


def test_admin_self_demotion_blocked(monkeypatch, db_connect):
    actor = RegisteredUser(id=1, email="admin@example.com", role="Admin")
    monkeypatch.setitem(app.dependency_overrides, current_user, lambda: actor)
    assert client.patch(users_url + "/1/role", json={"role": "Applicant"}).status_code == 409
    db_connect.assert_not_called()
