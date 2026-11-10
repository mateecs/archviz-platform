from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.models import User
from .factories import ProjectFactory, UserFactory
from .imaging import add_watermark, make_thumbnail
from .models import Project, Render

pytestmark = pytest.mark.django_db


def make_image(name="render.png", size=(2400, 1600)):
    buf = BytesIO()
    Image.new("RGB", size, (120, 160, 200)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def url(project, part):
    return f"/api/projects/{project.id}/{part}/"


@pytest.fixture
def active_project(client_user, artist_user):
    return ProjectFactory(client=client_user, artist=artist_user, status=Project.Status.IN_PROGRESS)


# ---------- renders ----------
def test_upload_is_processed_into_thumbnail_and_preview(
    active_project, artist_user, as_user, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        res = as_user(artist_user).post(
            url(active_project, "renders"), {"original": make_image(), "notes": "v1"}, format="multipart"
        )
    assert res.status_code == 201, res.data
    assert res.data["version"] == 1 and res.data["width"] == 2400

    render = Render.objects.get(pk=res.data["id"])
    assert render.processing_status == Render.ProcessingStatus.DONE
    with Image.open(render.thumbnail.path) as thumb:
        assert max(thumb.size) == 400
    with Image.open(render.preview.path) as preview:
        assert max(preview.size) == 1600


def test_versions_increment(active_project, artist_user, as_user):
    api = as_user(artist_user)
    for expected in (1, 2):
        res = api.post(url(active_project, "renders"), {"original": make_image()}, format="multipart")
        assert res.data["version"] == expected


def test_render_upload_blocked_unless_in_progress(client_user, artist_user, as_user):
    project = ProjectFactory(client=client_user, artist=artist_user, status=Project.Status.ASSIGNED)
    res = as_user(artist_user).post(url(project, "renders"), {"original": make_image()}, format="multipart")
    assert res.status_code == 403


def test_client_cannot_upload_render(active_project, client_user, as_user):
    res = as_user(client_user).post(url(active_project, "renders"), {"original": make_image()}, format="multipart")
    assert res.status_code == 403


def test_fake_image_is_rejected(active_project, artist_user, as_user):
    fake = SimpleUploadedFile("fake.png", b"this is not an image", content_type="image/png")
    res = as_user(artist_user).post(url(active_project, "renders"), {"original": fake}, format="multipart")
    assert res.status_code == 400


def test_client_only_gets_original_after_completion(active_project, client_user, artist_user, as_user):
    as_user(artist_user).post(url(active_project, "renders"), {"original": make_image()}, format="multipart")
    client_api = as_user(client_user)

    assert client_api.get(url(active_project, "renders")).data["results"][0]["original_url"] is None
    Project.objects.filter(pk=active_project.pk).update(status=Project.Status.COMPLETED)
    assert client_api.get(url(active_project, "renders")).data["results"][0]["original_url"] is not None


def test_outsider_cannot_see_project_content(active_project, as_user):
    outsider = UserFactory(role=User.Role.CLIENT)
    for part in ("files", "renders", "comments"):
        assert as_user(outsider).get(url(active_project, part)).status_code == 404


# ---------- reference files ----------
def test_client_uploads_reference_file(client_user, as_user):
    project = ProjectFactory(client=client_user)
    pdf = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    res = as_user(client_user).post(url(project, "files"), {"file": pdf, "description": "Floor plan"}, format="multipart")
    assert res.status_code == 201


def test_reference_file_rejects_executables(client_user, as_user):
    project = ProjectFactory(client=client_user)
    bad = SimpleUploadedFile("setup.exe", b"MZ...", content_type="application/octet-stream")
    res = as_user(client_user).post(url(project, "files"), {"file": bad}, format="multipart")
    assert res.status_code == 400


# ---------- comments ----------
def test_participants_can_comment(active_project, client_user, artist_user, as_user):
    for user in (client_user, artist_user):
        res = as_user(user).post(url(active_project, "comments"), {"body": "Looks good"}, format="json")
        assert res.status_code == 201
        assert res.data["author"]["id"] == user.id
    assert as_user(client_user).get(url(active_project, "comments")).data["count"] == 2


def test_comment_cannot_reference_another_projects_render(active_project, client_user, as_user):
    foreign = Render.objects.create(project=ProjectFactory(), version=1, original=make_image())
    res = as_user(client_user).post(
        url(active_project, "comments"), {"body": "Hi", "render": foreign.id}, format="json"
    )
    assert res.status_code == 400


# ---------- email ----------
def test_status_change_emails_both_parties(
    active_project, client_user, artist_user, as_user, django_capture_on_commit_callbacks, mailoutbox
):
    with django_capture_on_commit_callbacks(execute=True):
        res = as_user(artist_user).post(url(active_project, "transition"), {"status": "in_review"}, format="json")
    assert res.status_code == 200
    assert len(mailoutbox) == 1
    assert set(mailoutbox[0].to) == {client_user.email, artist_user.email}
    assert "In review" in mailoutbox[0].subject


# ---------- imaging unit tests (no database needed) ----------
def test_watermark_keeps_size_but_changes_pixels():
    img = Image.new("RGB", (800, 600), (30, 30, 30))
    marked = add_watermark(img, "PREVIEW")
    assert marked.size == img.size
    assert marked.tobytes() != img.tobytes()


def test_thumbnail_never_upscales():
    assert make_thumbnail(Image.new("RGB", (100, 80))).size == (100, 80)