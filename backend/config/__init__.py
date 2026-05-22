"""
config package initializer.

Imports the Celery app so it is always loaded when Django starts.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
