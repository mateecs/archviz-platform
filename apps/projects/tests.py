from django.test import TestCase

# Create your tests here.
# apps/projects/tests.py
import pytest

from .factories import ProjectFactory
from apps.projects.models import Project
#from .models import Project

pytestmark = pytest.mark.django_db

URL = "/api/projects/"
PAYLOAD = {"title": "Modern villa", "description": "Exterior day render", "project_type": "exterior"}


def test_client_can_create_project(client_user, as_user):
    res = as_user(client_user).post(URL, PAYLOAD, format="json")
    assert res.status_code == 201
    assert res.data["status"] == "submitted"
    assert res.data["client"]["id"] == client_user.id


def test_artist_cannot_create_project(artist_user, as_user):
    res = as_user(artist_user).post(URL, PAYLOAD, format="json")
    assert res.status_code == 403


def test_client_cannot_see_another_clients_project(client_user, as_user):
    other = ProjectFactory()
    res = as_user(client_user).get(f"{URL}{other.id}/")
    assert res.status_code == 404


def test_client_cannot_set_status_directly(client_user, as_user):
    project = ProjectFactory(client=client_user)
    res = as_user(client_user).patch(f"{URL}{project.id}/", {"status": "completed"}, format="json")
    project.refresh_from_db()
    assert project.status == Project.Status.SUBMITTED


def test_admin_assigns_artist_and_artist_sees_project(admin_user, artist_user, as_user):
    project = ProjectFactory()
    res = as_user(admin_user).post(f"{URL}{project.id}/assign/", {"artist": artist_user.id}, format="json")
    assert res.status_code == 200
    assert res.data["status"] == "assigned"
    assert as_user(artist_user).get(URL).data["count"] == 1


def test_full_workflow_with_revision(client_user, artist_user, admin_user, as_user):
    project = ProjectFactory(client=client_user)

    def move(user, status):
        return as_user(user).post(f"{URL}{project.id}/transition/", {"status": status}, format="json")

    as_user(admin_user).post(f"{URL}{project.id}/assign/", {"artist": artist_user.id}, format="json")
    steps = [
        (artist_user, "in_progress"),
        (artist_user, "in_review"),
        (client_user, "revision_requested"),
        (artist_user, "in_progress"),
        (artist_user, "in_review"),
        (client_user, "completed"),
    ]
    for user, status in steps:
        res = move(user, status)
        assert res.status_code == 200, res.data
        assert res.data["status"] == status
    assert project.status_logs.count() == 7  # 1 assign + 6 transitions


def test_invalid_transition_is_rejected(client_user, as_user):
    project = ProjectFactory(client=client_user)
    res = as_user(client_user).post(f"{URL}{project.id}/transition/", {"status": "in_progress"}, format="json")
    assert res.status_code == 400


def test_wrong_role_cannot_make_transition(client_user, artist_user, as_user):
    project = ProjectFactory(client=client_user, artist=artist_user, status=Project.Status.IN_REVIEW)
    res = as_user(artist_user).post(f"{URL}{project.id}/transition/", {"status": "completed"}, format="json")
    assert res.status_code == 403