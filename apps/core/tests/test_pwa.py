import json
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from PIL import Image

from apps.core import pwa

PWA_DIR = Path(settings.BASE_DIR) / "static" / "img" / "pwa"


def test_manifest_is_installable(client):
    response = client.get(reverse("core:manifest"))

    assert response["Content-Type"] == "application/manifest+json"
    data = json.loads(response.content)
    assert data["display"] == "standalone"
    assert data["start_url"].startswith("/portal/")
    assert data["scope"] == "/"
    sizes = {(i["sizes"], i["purpose"]) for i in data["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= sizes


@pytest.mark.parametrize(
    ("name", "size"),
    [("icon-192.png", 192), ("icon-512.png", 512), ("maskable-512.png", 512), ("apple-touch-icon.png", 180)],
)
def test_icon_files_have_the_right_size(name, size):
    with Image.open(PWA_DIR / name) as img:
        assert img.size == (size, size)
        assert img.mode == "RGB"  # no transparency: iOS would show it on black anyway


def test_service_worker_headers_and_content(client):
    response = client.get(reverse("core:service_worker"))
    body = response.content.decode()

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert response["Cache-Control"] == "no-cache"
    assert response["Service-Worker-Allowed"] == "/"
    assert reverse("core:offline") in body
    for url in pwa.precache_urls():
        assert f'"{url}"' in body
    assert 'request.method !== "GET"' in body  # never touches POSTs


def test_service_worker_does_not_cache_pages():
    template = (Path(settings.BASE_DIR) / "templates" / "pwa" / "sw.js").read_text()
    navigate_block = template.split('request.mode === "navigate"')[1]

    assert "cache.put" not in navigate_block


def test_missing_fonts_are_not_precached():
    urls = pwa.precache_urls()

    for optional in pwa.OPTIONAL_ASSETS:
        found = (Path(settings.BASE_DIR) / "static" / optional).exists()
        assert any(optional.split("/")[-1].split(".")[0] in u for u in urls) == found


def test_cache_version_changes_with_assets():
    assert pwa.cache_version(["/a.css"]) != pwa.cache_version(["/b.css"])
    assert pwa.cache_version(["/a.css"]) == pwa.cache_version(["/a.css"])


@pytest.mark.django_db
def test_offline_page_has_no_personal_data(client, make_member):
    member = make_member(full_name="Private Person")
    client.force_login(member)

    html = client.get(reverse("core:offline")).content.decode()

    assert "You are offline" in html
    assert "Private Person" not in html and member.handle not in html


def test_every_page_links_manifest_and_worker(client):
    html = client.get(reverse("core:welcome")).content.decode()

    assert reverse("core:manifest") in html
    assert 'data-sw="/sw.js"' in html
    assert "apple-touch-icon" in html


@pytest.mark.django_db
def test_portal_has_hidden_install_banner(client, make_member):
    client.force_login(make_member())

    html = client.get(reverse("core:portal")).content.decode()

    assert 'id="install-banner"' in html and "install-banner lucid-card d-none" in html
