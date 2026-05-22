import logging
import signal
import sys
from django.core.management.base import BaseCommand
from core.kafka_consumer import TelemetryConsumer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Starts the Kafka telemetry consumer to ingest flight positions and sync to Redis/PostgreSQL."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Initializing Telemetry Consumer..."))
        
        try:
            consumer = TelemetryConsumer()
        except Exception as exc:
            logger.exception("Failed to initialize TelemetryConsumer")
            self.stdout.write(self.style.ERROR(f"Initialization failed: {exc}"))
            sys.exit(1)

        # Set up signal handling for graceful shutdown
        def handle_shutdown(signum, frame):
            self.stdout.write(self.style.WARNING(f"\nReceived signal {signum}. Shutting down consumer..."))
            consumer.stop()

        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        self.stdout.write(self.style.SUCCESS("Starting Telemetry Consumer loop... Press Ctrl+C to exit."))
        try:
            consumer.start()
            self.stdout.write(self.style.SUCCESS("Telemetry Consumer loop terminated gracefully."))
        except Exception as exc:
            logger.exception("Unexpected error in consumer execution loop")
            self.stdout.write(self.style.ERROR(f"Fatal consumer error: {exc}"))
            sys.exit(1)
