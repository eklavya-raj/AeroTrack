"""
Kafka producer helper for AeroTrack.

Usage::

    from core.kafka_producer import KafkaProducer

    producer = KafkaProducer()
    producer.produce("telemetry", key="flight-42", value={"alt": 35000})
    producer.flush()
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests


from confluent_kafka import Producer
from django.conf import settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Thin wrapper around :class:`confluent_kafka.Producer`."""

    def __init__(self, extra_config: dict[str, Any] | None = None):
        config: dict[str, Any] = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        }
        if extra_config:
            config.update(extra_config)

        try:
            self._producer = Producer(config)
            logger.info(
                "Kafka producer initialised (servers=%s)",
                config["bootstrap.servers"],
            )
        except Exception:
            logger.exception("Failed to create Kafka producer")
            raise

    # ------------------------------------------------------------------
    # Delivery report callback
    # ------------------------------------------------------------------
    @staticmethod
    def _delivery_report(err, msg):
        """Called once per message to indicate delivery result."""
        if err is not None:
            logger.error(
                "Kafka delivery failed for %s [%s]: %s",
                msg.topic(),
                msg.key(),
                err,
            )
        else:
            logger.debug(
                "Kafka message delivered to %s [%s] @ offset %s",
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_and_produce_flights(self, topic_name: str = "flight-telemetry") -> None:
        """Fetch flight data from OpenSky API and produce to Kafka."""
        url = "https://opensky-network.org/api/states/all"
        try:
            logger.info("Fetching state vectors from OpenSky API: %s", url)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            states = data.get("states", [])

            if not states:
                logger.info("No states returned by OpenSky API")
                return

            logger.info("Fetched %d state vectors from OpenSky API", len(states))
            for state in states:
                if len(state) < 12:
                    continue

                payload = {
                    "icao24": state[0],
                    "callsign": state[1].strip() if state[1] else None,
                    "origin_country": state[2],
                    "longitude": state[5],
                    "latitude": state[6],
                    "baro_altitude": state[7],
                    "on_ground": state[8],
                    "velocity": state[9],
                    "true_track": state[10],
                    "vertical_rate": state[11],
                    "squawk": state[14] if len(state) > 14 else None
                }
                self.produce(
                    topic=topic_name,
                    key=payload["icao24"],
                    value=payload,
                )

            self.flush()
            logger.info("Successfully produced %d flight states to topic: %s", len(states), topic_name)

        except Exception:
            logger.exception("Error gathering telemetry data")

    def produce(
        self,
        topic: str,
        key: str,
        value: dict[str, Any] | str | bytes,
    ) -> None:
        """Serialise *value* as JSON (if needed) and enqueue for delivery."""
        if isinstance(value, dict):
            value = json.dumps(value).encode("utf-8")
        elif isinstance(value, str):
            value = value.encode("utf-8")

        try:
            self._producer.produce(
                topic=topic,
                key=key.encode("utf-8") if isinstance(key, str) else key,
                value=value,
                callback=self._delivery_report,
            )
            # Trigger any available delivery-report callbacks.
            self._producer.poll(0)
        except BufferError:
            logger.warning(
                "Kafka local queue is full (%d messages awaiting delivery); "
                "flushing…",
                len(self._producer),
            )
            self._producer.flush()
            # Retry once after flush.
            self._producer.produce(
                topic=topic,
                key=key.encode("utf-8") if isinstance(key, str) else key,
                value=value,
                callback=self._delivery_report,
            )
        except Exception:
            logger.exception("Failed to produce message to topic %s", topic)
            raise

    def flush(self, timeout: float = 10.0) -> int:
        """Block until all outstanding messages are delivered (or *timeout*)."""
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            logger.warning(
                "%d Kafka message(s) still in queue after flush timeout", remaining
            )
        return remaining


if __name__ == "__main__":
    import os
    import sys
    import time
    import django

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.append(backend_dir)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    logger.info("Initializing flight telemetry ingestion...")
    try:
        producer = KafkaProducer()
    except Exception:
        logger.exception("Failed to initialize telemetry producer")
        sys.exit(1)

    logger.info("Starting flight telemetry ingestion loop (interval=10s)...")
    try:
        while True:
            producer.fetch_and_produce_flights()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Telemetry ingestion stopped by user.")
    except Exception:
        logger.exception("Fatal error in telemetry ingestion loop")
        sys.exit(1)
