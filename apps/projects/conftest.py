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


@pytest.fixture(autouse=True)
def celery_eager():
    """Run Celery tasks immediately in-process, so tests need no Redis or worker."""
    from config.celery import app
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


@pytest.fixture(autouse=True)
def tmp_media(settings, tmp_path):
    """Send uploaded files to a throwaway folder instead of your real media/."""
    settings.MEDIA_ROOT = tmp_path