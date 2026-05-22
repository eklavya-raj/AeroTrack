"""
Root URL configuration for AeroTrack.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    """Lightweight health-check endpoint – no DB hit."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    # ── API routes ──────────────────────────────────────────────
    path("api/health/", health_check, name="health-check"),
    path("api/", include("core.urls")),
    path("api/", include("users.urls")),
]
