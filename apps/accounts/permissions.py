from rest_framework.permissions import BasePermission

from .models import User


class HasRole(BasePermission):
    role = None

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == self.role)


class IsAdminRole(HasRole):
    role = User.Role.ADMIN


class IsClientRole(HasRole):
    role = User.Role.CLIENT