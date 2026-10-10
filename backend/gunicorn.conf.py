"""
Gunicorn settings. Every value can be overridden by an environment variable,
so the same file works on Render, a VPS or in a container.

Start: gunicorn config.wsgi:application -c gunicorn.conf.py

Defaults are sized for a small host (512 MB RAM): 2 workers x 4 threads.
`preload_app` is deliberately off: apps/core/async_utils.py creates a
ThreadPoolExecutor at import time, and threads do not survive a fork.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

worker_class = 'gthread'
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '4'))

# The mobile app's HTTP timeout is 60 s; SMTP is capped at 15 s (EMAIL_TIMEOUT).
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '60'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '5'))

# Recycle workers periodically to bound slow memory growth.
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', '100'))

# Logs to stdout/stderr; the host collects them. The per-request JSON line from
# apps/core/observability.py replaces gunicorn's access log (it has route, timing and
# query counts, and no raw paths). Set GUNICORN_ACCESSLOG=- to turn the access log back on.
accesslog = os.environ.get('GUNICORN_ACCESSLOG') or None
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')

# Keep heartbeat files in RAM when available (avoids slow-disk false timeouts).
worker_tmp_dir = '/dev/shm' if os.path.isdir('/dev/shm') else None
