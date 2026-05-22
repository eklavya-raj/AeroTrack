"""
Celery application configuration for AeroTrack.

This module creates the Celery app instance and configures it
using Django settings (namespace ``CELERY``).
"""

import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Read config from Django settings; the CELERY namespace means all
# Celery-related settings must be prefixed with ``CELERY_``.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task – prints its own request info."""
    print(f"Request: {self.request!r}")
