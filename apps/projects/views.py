from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsAdminRole, IsClientRole
from .models import InvalidTransition, Project, TransitionNotAllowed
from .permissions import CanEditProject
from .serializers import AssignSerializer, ProjectSerializer, StatusChangeSerializer
from .access import projects_for


class ProjectViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # for API docs generation
            return Project.objects.none()
        qs = projects_for(self.request.user).select_related("client", "artist")
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_permissions(self):
        if self.action == "create":
            classes = [IsAuthenticated, IsClientRole]
        elif self.action == "assign":
            classes = [IsAuthenticated, IsAdminRole]
        elif self.action in ("update", "partial_update"):
            classes = [IsAuthenticated, CanEditProject]
        else:
            classes = [IsAuthenticated]
        return [cls() for cls in classes]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

    @action(detail=True, methods=["post"], serializer_class=AssignSerializer)
    def assign(self, request, pk=None):
        project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            project.assign(serializer.validated_data["artist"], request.user)
        except InvalidTransition as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(ProjectSerializer(project, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], serializer_class=StatusChangeSerializer)
    def transition(self, request, pk=None):
        project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            project.change_status(serializer.validated_data["status"], request.user)
        except InvalidTransition as exc:
            raise ValidationError({"status": str(exc)})
        except TransitionNotAllowed as exc:
            raise PermissionDenied(str(exc))
        return Response(ProjectSerializer(project, context=self.get_serializer_context()).data)