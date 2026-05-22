"""
URL configuration for the ``users`` app.

Register viewsets with the router below; URL patterns are
automatically generated.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
]
