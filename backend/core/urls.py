"""
URL configuration for the ``core`` app.

Register viewsets with the router below; URL patterns are
automatically generated.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from core.views import NearbyFlightsView

router = DefaultRouter()

urlpatterns = [
    path("flights/nearby/", NearbyFlightsView.as_view(), name="nearby-flights"),
    path("", include(router.urls)),
]
