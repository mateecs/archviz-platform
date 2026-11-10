# apps/projects/serializers.py
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    client = UserSerializer(read_only=True)
    artist = UserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id", "title", "description", "project_type", "deadline",
            "status", "client", "artist", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at"]

    def validate_deadline(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("Deadline cannot be in the past.")
        return value


class AssignSerializer(serializers.Serializer):
    artist = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.ARTIST)
    )


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Project.Status.choices)