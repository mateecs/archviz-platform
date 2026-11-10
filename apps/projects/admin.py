from django.contrib import admin
from .models import Comment, Project, ProjectStatusLog, ReferenceFile, Render


class StatusLogInline(admin.TabularInline):
    model = ProjectStatusLog
    extra = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "created_at")
    can_delete = False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "project_type", "status", "client", "artist", "deadline")
    list_filter = ("status", "project_type")
    search_fields = ("title", "client__username", "artist__username")
    inlines = [StatusLogInline]


@admin.register(Render)
class RenderAdmin(admin.ModelAdmin):
    list_display = ("project", "version", "processing_status", "uploaded_by", "created_at")
    list_filter = ("processing_status",)


@admin.register(ReferenceFile)
class ReferenceFileAdmin(admin.ModelAdmin):
    list_display = ("project", "file", "uploaded_by", "created_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("project", "author", "created_at")