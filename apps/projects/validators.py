# apps/projects/validators.py
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_file_size(file):
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if file.size > limit:
        raise ValidationError(f"File too large. The maximum size is {settings.MAX_UPLOAD_MB} MB.")