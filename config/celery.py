"""Celery application. Tasks are discovered from every installed app's tasks.py."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("lucid")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
