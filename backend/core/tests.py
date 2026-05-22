from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class NearbyFlightsViewTests(APITestCase):

    @patch("core.views.redis.Redis.from_url")
    def test_get_all_active_flights(self, mock_from_url):
        mock_redis = MagicMock()
        mock_from_url.return_value = mock_redis

        mock_redis.zrange.return_value = [b"icao123", b"icao456"]

        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [
            b'{"icao24": "icao123", "callsign": "FLIGHT1", "latitude": 51.5, "longitude": -0.1}',
            b'{"icao24": "icao456", "callsign": "FLIGHT2", "latitude": 52.0, "longitude": -0.2}'
        ]

        url = reverse("nearby-flights")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["icao24"], "icao123")
        self.assertEqual(response.data[1]["icao24"], "icao456")

        mock_redis.zrange.assert_called_once_with("flights:active:geo", 0, -1)
        mock_pipeline.get.assert_any_call("flight:icao123:metadata")
        mock_pipeline.get.assert_any_call("flight:icao456:metadata")

    @patch("core.views.redis.Redis.from_url")
    def test_get_nearby_flights_geofence(self, mock_from_url):
        mock_redis = MagicMock()
        mock_from_url.return_value = mock_redis

        # georadius returns raw results: [[icao_bytes, distance], ...]
        mock_redis.georadius.return_value = [
            [b"icao123", 12.5],
            [b"icao456", 87.2]
        ]

        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [
            b'{"icao24": "icao123", "callsign": "FLIGHT1", "latitude": 51.5, "longitude": -0.1}',
            b'{"icao24": "icao456", "callsign": "FLIGHT2", "latitude": 52.0, "longitude": -0.2}'
        ]

        url = reverse("nearby-flights")
        response = self.client.get(url, {"lat": "51.47", "lon": "-0.45", "radius": "100"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["icao24"], "icao123")
        self.assertEqual(response.data[0]["distance_km"], 12.5)
        self.assertEqual(response.data[1]["icao24"], "icao456")
        self.assertEqual(response.data[1]["distance_km"], 87.2)

        mock_redis.georadius.assert_called_once_with(
            "flights:active:geo",
            -0.45,
            51.47,
            100.0,
            unit="km",
            withdist=True
        )

    def test_invalid_parameters(self):
        url = reverse("nearby-flights")
        response = self.client.get(url, {"lat": "invalid", "lon": "-0.45"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    @patch("core.views.redis.Redis.from_url")
    def test_redis_connection_error(self, mock_from_url):
        mock_from_url.side_effect = Exception("Connection refused")
        url = reverse("nearby-flights")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
