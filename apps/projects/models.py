import os
import uuid

from django.core.validators import FileExtensionValidator

from .validators import validate_file_size
from django.conf import settings
from django.db import models, transaction

from apps.accounts.models import User

ADMIN, CLIENT, ARTIST = User.Role.ADMIN, User.Role.CLIENT, User.Role.ARTIST


class InvalidTransition(Exception):
    """The requested status change is not part of the workflow."""


class TransitionNotAllowed(Exception):
    """The workflow allows it, but not for this user."""


class Project(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        IN_REVIEW = "in_review", "In review"
        REVISION_REQUESTED = "revision_requested", "Revision requested"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class ProjectType(models.TextChoices):
        EXTERIOR = "exterior", "Exterior visualization"
        INTERIOR = "interior", "Interior visualization"
        ANIMATION = "animation", "Animation / walkthrough"
        LANDSCAPE = "landscape", "Landscape"
        PRODUCT = "product", "Product visualization"

    # current status -> {allowed next status: role that performs it}
    # (assigning an artist is handled by assign(), not by this table)
    S = Status
    TRANSITIONS = {
        S.SUBMITTED: {S.CANCELLED: CLIENT},
        S.ASSIGNED: {S.IN_PROGRESS: ARTIST, S.CANCELLED: CLIENT},
        S.IN_PROGRESS: {S.IN_REVIEW: ARTIST, S.CANCELLED: ADMIN},
        S.IN_REVIEW: {S.REVISION_REQUESTED: CLIENT, S.COMPLETED: CLIENT},
        S.REVISION_REQUESTED: {S.IN_PROGRESS: ARTIST},
    }

    title = models.CharField(max_length=200)
    description = models.TextField()
    project_type = models.CharField(max_length=20, choices=ProjectType.choices)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="client_projects"
    )
    artist = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="artist_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.title} [{self.status}]"

    # ---- workflow ----
    def _is_participant(self, user):
        if user.role == CLIENT:
            return self.client_id == user.id
        if user.role == ARTIST:
            return self.artist_id == user.id
        return False

    def _log(self, old_status, user):
        ProjectStatusLog.objects.create(
            project=self, from_status=old_status, to_status=self.status, changed_by=user
        )
        # Queue the email only after the transaction commits, so the worker never
        # reads a half-saved project. Imported here to avoid a circular import.
        from .tasks import send_status_change_email

        project_id, new_status = self.pk, self.status
        transaction.on_commit(
            lambda: send_status_change_email.delay(project_id, old_status, new_status)
        )

    @transaction.atomic
    def change_status(self, new_status, user):
        required_role = self.TRANSITIONS.get(self.status, {}).get(new_status)
        if required_role is None:
            raise InvalidTransition(f"Cannot move from '{self.status}' to '{new_status}'.")
        if user.role != ADMIN and (user.role != required_role or not self._is_participant(user)):
            raise TransitionNotAllowed("You cannot make this status change on this project.")
        old = self.status
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        self._log(old, user)

    @transaction.atomic
    def assign(self, artist, by_user):
        if self.status not in (self.Status.SUBMITTED, self.Status.ASSIGNED):
            raise InvalidTransition("An artist can only be assigned before work starts.")
        old = self.status
        self.artist = artist
        self.status = self.Status.ASSIGNED
        self.save(update_fields=["artist", "status", "updated_at"])
        self._log(old, by_user)


class ProjectStatusLog(models.Model):
    """Audit trail: who changed which project's status, from what, to what, and when."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="status_logs")
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

# ---------- file paths ----------
def _unique_name(filename):
    return f"{uuid.uuid4().hex}{os.path.splitext(filename)[1].lower()}"


def reference_path(instance, filename):
    return f"projects/{instance.project_id}/references/{_unique_name(filename)}"


def render_original_path(instance, filename):
    return f"projects/{instance.project_id}/renders/original/{_unique_name(filename)}"


def render_thumb_path(instance, filename):
    return f"projects/{instance.project_id}/renders/thumbs/{_unique_name(filename)}"


def render_preview_path(instance, filename):
    return f"projects/{instance.project_id}/renders/previews/{_unique_name(filename)}"


class ReferenceFile(models.Model):
    """Files the client supplies: floor plans, CAD drawings, mood boards."""

    ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "dwg", "dxf", "skp", "zip"]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="reference_files")
    file = models.FileField(
        upload_to=reference_path,
        validators=[FileExtensionValidator(ALLOWED_EXTENSIONS), validate_file_size],
    )
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Render(models.Model):
    """One uploaded version of the artist's work, plus the files generated from it."""

    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="renders")
    version = models.PositiveIntegerField(editable=False)
    original = models.ImageField(
        upload_to=render_original_path,
        width_field="width",
        height_field="height",
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp", "tif", "tiff"]),
            validate_file_size,
        ],
    )
    thumbnail = models.ImageField(upload_to=render_thumb_path, blank=True)
    preview = models.ImageField(upload_to=render_preview_path, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    notes = models.CharField(max_length=500, blank=True)
    processing_status = models.CharField(
        max_length=12, choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING
    )
    processing_error = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["project", "version"], name="unique_render_version")
        ]

    def __str__(self):
        return f"{self.project.title} v{self.version}"


class Comment(models.Model):
    """Feedback thread on a project, optionally pointing at a specific render."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    render = models.ForeignKey(
        Render, on_delete=models.SET_NULL, null=True, blank=True, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]