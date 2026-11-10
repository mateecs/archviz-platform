# config/celery.py
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")  # reads CELERY_* settings
app.autodiscover_tasks()  # finds tasks.py inside each installed app