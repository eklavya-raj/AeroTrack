import json
import logging
import redis
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


class NearbyFlightsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            redis_url = settings.CACHES["default"]["LOCATION"]
            redis_client = redis.Redis.from_url(redis_url)
        except Exception:
            logger.exception("Failed to connect to Redis")
            return Response(
                {"error": "Redis connection error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        lat_str = request.query_params.get("lat")
        lon_str = request.query_params.get("lon")
        radius_str = request.query_params.get("radius", "100")

        try:
            if lat_str is not None and lon_str is not None:
                lat = float(lat_str)
                lon = float(lon_str)
                radius = float(radius_str)

                raw_results = redis_client.georadius(
                    "flights:active:geo",
                    lon,
                    lat,
                    radius,
                    unit="km",
                    withdist=True
                )

                icao24_dists = {}
                for item in raw_results:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        icao_decoded = item[0].decode("utf-8")
                        icao24_dists[icao_decoded] = item[1]

                icao24_list = list(icao24_dists.keys())
            else:
                icao_bytes = redis_client.zrange("flights:active:geo", 0, -1)
                icao24_list = [x.decode("utf-8") for x in icao_bytes]
                icao24_dists = {}

            if not icao24_list:
                return Response([])

            pipe = redis_client.pipeline()
            for icao24 in icao24_list:
                pipe.get(f"flight:{icao24}:metadata")
            metadata_list = pipe.execute()

            flights = []
            for icao24, cached_bytes in zip(icao24_list, metadata_list):
                if cached_bytes:
                    try:
                        flight_data = json.loads(cached_bytes.decode("utf-8"))
                        if icao24 in icao24_dists:
                            flight_data["distance_km"] = icao24_dists[icao24]
                        flights.append(flight_data)
                    except Exception:
                        continue

            return Response(flights)

        except ValueError:
            return Response(
                {"error": "Invalid coordinates or radius parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            logger.exception("Error querying active flights")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
