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
