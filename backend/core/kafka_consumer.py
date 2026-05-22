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
import logging
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Message
from django.conf import settings

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
