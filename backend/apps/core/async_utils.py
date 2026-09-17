"""
apps/core/async_utils.py
------------------------
Minimal, dependency-free background-task helper.

This project has no Celery/RQ — that's a deliberate, separate decision for
later (see the Sept 2026 scalability audit). For slow I/O that shouldn't
block the request/response cycle (e.g. sending an OTP email over SMTP),
submit the call to this shared thread pool instead of calling it inline.

NOT a replacement for a real task queue: submitted work runs in-process and
is lost if the worker process restarts mid-flight. Fine for best-effort
notification sends; do not use for anything that must be durable or
retried across deploys/process restarts.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger('apps.core.async_utils')

# A handful of workers is enough for occasional email/notification sends —
# this is not meant to absorb high-throughput background work.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='hh-bg')


def run_in_background(func, *args, **kwargs):
    """
    Submit func(*args, **kwargs) to the shared background thread pool and
    return immediately (returns the Future, mainly for tests).

    Nothing calls .result() on the returned Future in normal operation, so
    any exception raised by func would otherwise be silently discarded —
    this logs it instead.
    """
    future = _executor.submit(func, *args, **kwargs)

    def _log_if_failed(f):
        exc = f.exception()
        if exc is not None:
            logger.error(
                "Background task %s failed: %s",
                getattr(func, '__name__', func), exc, exc_info=exc,
            )

    future.add_done_callback(_log_if_failed)
    return future
