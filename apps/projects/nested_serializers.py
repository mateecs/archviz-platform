from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from .models import Comment, Project, ReferenceFile, Render


class ReferenceFileSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = ReferenceFile
        fields = ["id", "file", "description", "uploaded_by", "created_at"]
        read_only_fields = ["created_at"]


class RenderSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    original_url = serializers.SerializerMethodField()

    class Meta:
        model = Render
        fields = [
            "id", "version", "original", "original_url", "thumbnail", "preview",
            "width", "height", "notes", "processing_status", "processing_error",
            "uploaded_by", "created_at",
        ]
        read_only_fields = [
            "version", "thumbnail", "preview", "width", "height",
            "processing_status", "processing_error", "created_at",
        ]
        extra_kwargs = {"original": {"write_only": True}}

    def get_original_url(self, obj):
        request = self.context["request"]
        can_see_original = (
            request.user.role in (User.Role.ADMIN, User.Role.ARTIST)
            or obj.project.status == Project.Status.COMPLETED
        )
        if not can_see_original or not obj.original:
            return None
        return request.build_absolute_uri(obj.original.url)


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "render", "author", "body", "created_at"]
        read_only_fields = ["created_at"]

    def validate_render(self, render):
        if render is not None and render.project_id != self.context["project"].id:
            raise serializers.ValidationError("This render does not belong to this project.")
        return render