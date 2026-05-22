"""
Celery tasks for the ``core`` app.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sample_task(self, payload: dict | None = None):
    """A sample background task.

    Replace this with real business logic. The ``bind=True`` parameter
    gives access to ``self`` so you can call ``self.retry()`` on failure.

    Args:
        payload: Arbitrary JSON-serialisable data to process.

    Returns:
        A dict summarising the result.
    """
    logger.info("sample_task started with payload=%s", payload)

    try:
        # ── Replace with actual work ──────────────────────────
        result = {"processed": True, "payload": payload}
        # ──────────────────────────────────────────────────────
    except Exception as exc:
        logger.exception("sample_task failed, retrying…")
        raise self.retry(exc=exc)

    logger.info("sample_task completed: %s", result)
    return result
