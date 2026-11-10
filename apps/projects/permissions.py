# apps/projects/permissions.py
from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from .models import Project


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