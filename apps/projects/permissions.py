from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import User
from .models import Project

CLOSED = (Project.Status.COMPLETED, Project.Status.CANCELLED)


class CanEditProject(BasePermission):
    message = "Only the owning client can edit a project, and only before an artist is assigned."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == User.Role.ADMIN:
            return True
        return (
            user.role == User.Role.CLIENT
            and obj.client_id == user.id
            and obj.status == Project.Status.SUBMITTED
        )


class CanUploadReference(BasePermission):
    message = "Only the project's client (or an admin) can add files, and only while the project is open."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        project = view.get_project()
        if project.status in CLOSED:
            return False
        user = request.user
        return user.role == User.Role.ADMIN or (
            user.role == User.Role.CLIENT and project.client_id == user.id
        )


class CanUploadRender(BasePermission):
    message = "Only the assigned artist (or an admin) can upload renders, and only while the project is in progress."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        project = view.get_project()
        if project.status != Project.Status.IN_PROGRESS:
            return False
        user = request.user
        return user.role == User.Role.ADMIN or (
            user.role == User.Role.ARTIST and project.artist_id == user.id
        )