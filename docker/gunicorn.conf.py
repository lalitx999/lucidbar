"""Gunicorn settings for the web container. Only Nginx can reach it (internal Docker network)."""

import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 5)))
threads = int(os.environ.get("GUNICORN_THREADS", 2))
timeout = 60
graceful_timeout = 30
keepalive = 5
max_requests = 1000  # recycle workers to cap slow memory growth
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
# Nginx is the only client; trust its forwarded headers.
forwarded_allow_ips = "*"
