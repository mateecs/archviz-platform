# apps/projects/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter

from .nested_views import CommentViewSet, ReferenceFileViewSet, RenderViewSet
from .views import ProjectViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")

urlpatterns = router.urls + [
    path("projects/<int:project_pk>/files/",
         ReferenceFileViewSet.as_view({"get": "list", "post": "create"})),
    path("projects/<int:project_pk>/files/<int:pk>/",
         ReferenceFileViewSet.as_view({"get": "retrieve"})),
    path("projects/<int:project_pk>/renders/",
         RenderViewSet.as_view({"get": "list", "post": "create"})),
    path("projects/<int:project_pk>/renders/<int:pk>/",
         RenderViewSet.as_view({"get": "retrieve"})),
    path("projects/<int:project_pk>/comments/",
         CommentViewSet.as_view({"get": "list", "post": "create"})),
]