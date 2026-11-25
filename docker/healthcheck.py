"""
Docker healthcheck for the web container: GET /healthz/ on Gunicorn directly.

It sends the real domain as Host (ALLOWED_HOSTS) and X-Forwarded-Proto=https
(as Nginx does), so Django neither rejects the host nor redirects to https.
"""

import os
import sys
import urllib.request

host = os.environ.get("DOMAIN") or os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")[0]
request = urllib.request.Request(
    "http://127.0.0.1:8000/healthz/", headers={"Host": host.strip(), "X-Forwarded-Proto": "https"}
)
try:
    with urllib.request.urlopen(request, timeout=3) as response:  # noqa: S310 - fixed local URL
        sys.exit(0 if response.status == 200 else 1)
except Exception:  # noqa: BLE001
    sys.exit(1)
