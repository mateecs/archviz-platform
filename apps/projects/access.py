# apps/projects/access.py
from apps.accounts.models import User

from .models import Project


def projects_for(user):
    qs = Project.objects.all()
    if user.role == User.Role.CLIENT:
        qs = qs.filter(client=user)
    elif user.role == User.Role.ARTIST:
        qs = qs.filter(artist=user)
    return qs  # admins see everything