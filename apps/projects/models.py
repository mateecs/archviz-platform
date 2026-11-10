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