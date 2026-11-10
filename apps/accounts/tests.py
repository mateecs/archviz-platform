# apps/accounts/tests.py
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_register_then_login():
    api = APIClient()
    data = {"username": "sara", "email": "sara@example.com", "password": "S3cure-pass-123", "role": "client"}
    assert api.post("/api/auth/register/", data, format="json").status_code == 201

    res = api.post("/api/auth/token/", {"username": "sara", "password": "S3cure-pass-123"}, format="json")
    assert res.status_code == 200
    assert "access" in res.data and "refresh" in res.data


def test_cannot_register_as_admin():
    data = {"username": "evil", "email": "e@example.com", "password": "S3cure-pass-123", "role": "admin"}
    assert APIClient().post("/api/auth/register/", data, format="json").status_code == 400