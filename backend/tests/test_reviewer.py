import pytest
from fastapi.testclient import TestClient

from app.login import current_user
from app.main import app
from app.registration import RegisteredUser


client = TestClient(app)
dashboard_url = "/api/reviewer/dashboard"


def test_dashboard_requires_login():
    response = client.get(dashboard_url)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [("Applicant", 403), ("Admin", 403), ("Reviewer", 200)],
)
def test_dashboard_checks_role(monkeypatch, role, expected_status):
    user = RegisteredUser(id=1, email="role.test@example.com", role=role)
    monkeypatch.setitem(app.dependency_overrides, current_user, lambda: user)

    response = client.get(dashboard_url)

    assert response.status_code == expected_status
    if role == "Reviewer":
        assert response.json() == user.model_dump()