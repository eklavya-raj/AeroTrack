"""
Kafka consumer helper for AeroTrack.

Subclass :class:`KafkaConsumer` and implement :meth:`process_message`
to handle incoming records.

Usage::

    from core.kafka_consumer import KafkaConsumer

    class TelemetryConsumer(KafkaConsumer):
        def process_message(self, message):
            print(message.value())

    consumer = TelemetryConsumer(
        group_id="telemetry-workers",
        topics=["telemetry"],
    )
    consumer.start()
"""

from __future__ import annotations

import abc
import json
import logging
import time
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Message
from django.conf import settings
import redis

from core.models import FlightLog, LandingArchive



logger = logging.getLogger(__name__)


class KafkaConsumer(abc.ABC):
    """Abstract Kafka consumer with a managed poll loop."""

    def __init__(
        self,
        group_id: str,
        topics: list[str],
        extra_config: dict[str, Any] | None = None,
        poll_timeout: float = 1.0,
    ):
        self.topics = topics
        self.poll_timeout = poll_timeout
        self._running = False

        config: dict[str, Any] = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
        if extra_config:
            config.update(extra_config)

        try:
            self._consumer = Consumer(config)
            logger.info(
                "Kafka consumer initialised (group=%s, topics=%s)",
                group_id,
                topics,
            )
        except Exception:
            logger.exception("Failed to create Kafka consumer")
            raise

    # ------------------------------------------------------------------
    # Abstract hook
    # ------------------------------------------------------------------
    @abc.abstractmethod
    def process_message(self, message: Message) -> None:
        """Handle a single consumed message – implement in subclass."""

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Subscribe and enter the blocking poll loop.

        Call :meth:`stop` from another thread (or a signal handler) to
        break out of the loop gracefully.
        """
        self._consumer.subscribe(self.topics)
        self._running = True
        logger.info("Kafka consumer started – listening on %s", self.topics)

        try:
            while self._running:
                msg: Message | None = self._consumer.poll(
                    timeout=self.poll_timeout,
                )
                if msg is None:
                    continue

                error = msg.error()
                if error:
                    if error.code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            "Reached end of partition %s [%d] @ offset %d",
                            msg.topic(),
                            msg.partition(),
                            msg.offset(),
                        )
                        continue
                    raise KafkaException(error)

                try:
                    self.process_message(msg)
                except Exception:
                    logger.exception(
                        "Error processing message from %s [%d] @ offset %d",
                        msg.topic(),
                        msg.partition(),
                        msg.offset(),
                    )
        except KafkaException:
            logger.exception("Kafka consumer encountered a fatal error")
            raise
        finally:
            self._consumer.close()
            logger.info("Kafka consumer shut down")

    def stop(self) -> None:
        """Signal the poll loop to exit after the current iteration."""
        logger.info("Kafka consumer stop requested")
        self._running = False


class TelemetryConsumer(KafkaConsumer):
    """Consumer that processes flight-telemetry stream and updates Redis + Postgres."""

    def __init__(
        self,
        group_id: str = "telemetry-consumers",
        topics: list[str] | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        if topics is None:
            topics = ["flight-telemetry"]
        
        super().__init__(
            group_id=group_id,
            topics=topics,
            extra_config=extra_config,
        )
        
        redis_url = settings.CACHES["default"]["LOCATION"]
        self.redis_client = redis.Redis.from_url(redis_url)
        logger.info("Connected to Redis at %s", redis_url)

    def process_message(self, message: Message) -> None:
        """Process a single consumed flight telemetry message."""
        try:
            value_bytes = message.value()
            if not value_bytes:
                return

            payload = json.loads(value_bytes.decode("utf-8"))
            icao24 = payload.get("icao24")
            callsign = payload.get("callsign", "").strip() if payload.get("callsign") else ""
            longitude = payload.get("longitude")
            latitude = payload.get("latitude")
            on_ground = payload.get("on_ground", False)
            velocity = payload.get("velocity") or 0.0
            baro_altitude = payload.get("baro_altitude") or 0.0
            vertical_rate = payload.get("vertical_rate")
            squawk = payload.get("squawk")

            if not icao24:
                return

            redis_metadata_key = f"flight:{icao24}:metadata"
            cached_bytes = self.redis_client.get(redis_metadata_key)
            cached_data = json.loads(cached_bytes.decode("utf-8")) if cached_bytes else {}

            max_velocity = max(cached_data.get("max_velocity", 0.0), velocity)
            max_altitude = max(cached_data.get("max_altitude", 0.0), baro_altitude)
            was_on_ground = cached_data.get("on_ground", False)

            payload["max_velocity"] = max_velocity
            payload["max_altitude"] = max_altitude

            flight_log, _ = FlightLog.objects.update_or_create(
                icao24=icao24,
                callsign=callsign,
                defaults={
                    "origin_country": payload.get("origin_country") or "",
                }
            )

            if not was_on_ground and on_ground and cached_bytes:
                LandingArchive.objects.create(
                    flight_log=flight_log,
                    max_velocity=max_velocity,
                    max_altitude=max_altitude,
                    squawk_at_landing=str(squawk).strip() if squawk is not None else None,
                )
                self.redis_client.zrem("flights:active:geo", icao24)
                self.redis_client.delete(redis_metadata_key)
                logger.info("Flight %s landed. Committed archive and cleared active cache.", icao24)
                return

            self.redis_client.setex(
                redis_metadata_key,
                60,
                json.dumps(payload),
            )

            if longitude is not None and latitude is not None and not on_ground:
                self.redis_client.geoadd(
                    "flights:active:geo",
                    (longitude, latitude, icao24)
                )

            alerts = []
            squawk_str = str(squawk).strip() if squawk is not None else ""
            if squawk_str in ["7500", "7600", "7700"]:
                desc = "Hijacking" if squawk_str == "7500" else ("Radio Failure" if squawk_str == "7600" else "General Emergency")
                alerts.append({
                    "type": "squawk",
                    "code": squawk_str,
                    "description": desc,
                })

            if vertical_rate is not None and abs(vertical_rate) > 25.0:
                desc = "Extreme Descent Rate" if vertical_rate < 0 else "Extreme Climb Rate"
                alerts.append({
                    "type": "vertical_rate",
                    "rate": vertical_rate,
                    "description": f"{desc} ({vertical_rate} m/s)",
                })

            for alert in alerts:
                alert_payload = {
                    "icao24": icao24,
                    "callsign": callsign,
                    "timestamp": payload.get("time_position") or int(time.time()),
                    "latitude": latitude,
                    "longitude": longitude,
                    "alert": alert,
                }
                self.redis_client.publish("alerts:active", json.dumps(alert_payload))
                logger.warning("Anomaly alert raised for %s: %s", icao24, alert["description"])

        except json.JSONDecodeError:
            logger.exception("Failed to parse JSON payload from Kafka message")
        except Exception:
            logger.exception("Error processing consumed flight telemetry message")
