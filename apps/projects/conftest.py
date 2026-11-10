# conftest.py 
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.projects.factories import UserFactory


@pytest.fixture
def as_user():
    """Returns an API client that is logged in as the given user."""
    def _make(user):
        api = APIClient()
        api.force_authenticate(user=user)
        return api
    return _make


@pytest.fixture
def client_user(db):
    return UserFactory(role=User.Role.CLIENT)


@pytest.fixture
def artist_user(db):
    return UserFactory(role=User.Role.ARTIST)


@pytest.fixture
def admin_user(db):
    return UserFactory(role=User.Role.ADMIN, is_staff=True)