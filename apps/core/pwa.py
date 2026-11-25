"""
Progressive Web App pieces: the web manifest and the service worker.

The service worker is rendered from a template so it can list the hashed
static file names produced by ManifestStaticFilesStorage. Its cache version
is a hash of that list, so a deploy that changes any listed asset installs
a fresh cache and deletes the old one.
"""

import hashlib

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

# Bump when the service worker logic itself changes.
SW_REVISION = "1"

APP_SHELL = [
    "vendor/bootstrap/css/bootstrap.min.css",
    "vendor/bootstrap/js/bootstrap.bundle.min.js",
    "css/lucid.css",
    "icons/sprite.svg",
    "img/logo-256.png",
    "img/pwa/icon-192.png",
    "js/pwa.js",
]
# Cached only once the files exist (see static/fonts/README.md).
OPTIONAL_ASSETS = ["fonts/Montserrat-Variable.woff2", "fonts/Cinzel-Variable.woff2"]


def precache_urls() -> list[str]:
    paths = APP_SHELL + [p for p in OPTIONAL_ASSETS if finders.find(p)]
    return [static(p) for p in paths]


def cache_version(urls: list[str]) -> str:
    digest = hashlib.sha256("\n".join([SW_REVISION, *urls]).encode()).hexdigest()
    return digest[:12]


def manifest() -> dict:
    return {
        "id": "/portal/",
        "name": settings.SITE_NAME,
        "short_name": "Lucid",
        "description": settings.SITE_TAGLINE,
        "start_url": "/portal/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#000000",
        "theme_color": "#000000",
        "lang": "en",
        "icons": [
            {"src": static("img/pwa/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": static("img/pwa/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {
                "src": static("img/pwa/maskable-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
        "shortcuts": [
            {"name": "Keys", "url": reverse("keys:keys")},
            {"name": "Identity card", "url": reverse("accounts:identity")},
            {"name": "VIP Chamber", "url": reverse("bookings:chamber")},
        ],
    }
