from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from celery import shared_task
from PIL import Image, UnidentifiedImageError

from . import imaging
from .models import Project, Render


def _mark_failed(render, message):
    render.processing_status = Render.ProcessingStatus.FAILED
    render.processing_error = message
    render.save(update_fields=["processing_status", "processing_error"])


@shared_task(bind=True, max_retries=3)
def process_render(self, render_id):
    render = Render.objects.filter(pk=render_id).first()
    if render is None:
        return  # deleted before the worker got to it

    render.processing_status = Render.ProcessingStatus.PROCESSING
    render.save(update_fields=["processing_status"])

    try:
        with render.original.open("rb") as f:
            img = imaging.load_rgb(f)
        thumb = imaging.make_thumbnail(img)
        preview = imaging.make_preview(img, getattr(settings, "WATERMARK_TEXT", "PREVIEW"))

        render.thumbnail.save(f"{render.pk}.jpg", ContentFile(imaging.to_jpeg_bytes(thumb, 85)), save=False)
        render.preview.save(f"{render.pk}.jpg", ContentFile(imaging.to_jpeg_bytes(preview, 80)), save=False)
        render.processing_status = Render.ProcessingStatus.DONE
        render.processing_error = ""
        render.save(update_fields=["thumbnail", "preview", "processing_status", "processing_error"])
    except (UnidentifiedImageError, Image.DecompressionBombError, ValueError):
        # The file itself is bad; retrying will never fix that.
        _mark_failed(render, "The uploaded file could not be processed as an image.")
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _mark_failed(render, "Image processing failed. Please upload the file again.")
            raise
        raise self.retry(exc=exc, countdown=5 * 2 ** self.request.retries)  # 5s, 10s, 20s


@shared_task
def send_status_change_email(project_id, old_status, new_status):
    project = Project.objects.select_related("client", "artist").filter(pk=project_id).first()
    if project is None:
        return
    recipients = {u.email for u in (project.client, project.artist) if u and u.email}
    if not recipients:
        return

    old_label = Project.Status(old_status).label
    new_label = Project.Status(new_status).label
    send_mail(
        subject=f"[ArchViz] {project.title}: {old_label} to {new_label}",
        message=(
            f"The status of project '{project.title}' changed from "
            f"'{old_label}' to '{new_label}'.\n\nLog in to the platform to see the details."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=sorted(recipients),
    )