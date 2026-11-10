from django.contrib import admin
from .models import Project, ProjectStatusLog


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