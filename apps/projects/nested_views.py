from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .access import projects_for
from .models import Comment, Project, ReferenceFile, Render
from .nested_serializers import CommentSerializer, ReferenceFileSerializer, RenderSerializer
from .permissions import CanUploadReference, CanUploadRender
from .tasks import process_render


class ProjectScopedMixin:
    """Finds the parent project from the URL, limited to projects this user may see."""

    def get_project(self):
        if not hasattr(self, "_project"):
            self._project = get_object_or_404(
                projects_for(self.request.user), pk=self.kwargs["project_pk"]
            )
        return self._project

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not getattr(self, "swagger_fake_view", False):
            context["project"] = self.get_project()
        return context


class ReferenceFileViewSet(
    ProjectScopedMixin,
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReferenceFileSerializer
    permission_classes = [IsAuthenticated, CanUploadReference]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ReferenceFile.objects.none()
        return self.get_project().reference_files.select_related("uploaded_by")

    def perform_create(self, serializer):
        serializer.save(project=self.get_project(), uploaded_by=self.request.user)


class RenderViewSet(
    ProjectScopedMixin,
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RenderSerializer
    permission_classes = [IsAuthenticated, CanUploadRender]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Render.objects.none()
        return self.get_project().renders.select_related("project", "uploaded_by")

    def perform_create(self, serializer):
        with transaction.atomic():
            # Lock the project row so simultaneous uploads get different version numbers.
            project = Project.objects.select_for_update().get(pk=self.get_project().pk)
            last_version = project.renders.aggregate(m=Max("version"))["m"] or 0
            render = serializer.save(
                project=project, uploaded_by=self.request.user, version=last_version + 1
            )
            # Queue the job only after the row is committed, or the worker may not find it.
            transaction.on_commit(lambda: process_render.delay(render.pk))


class CommentViewSet(
    ProjectScopedMixin,
    mixins.CreateModelMixin, mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Comment.objects.none()
        qs = self.get_project().comments.select_related("author")
        render_id = self.request.query_params.get("render")
        if render_id and render_id.isdigit():
            qs = qs.filter(render_id=render_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(project=self.get_project(), author=self.request.user)