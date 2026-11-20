import pytest
from django.template import Context, Template
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_welcome_page_renders_with_theme(client):
    response = client.get(reverse("core:welcome"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "vendor/bootstrap/css/bootstrap.min.css" in html
    assert "css/lucid.css" in html
    assert 'data-bs-theme="dark"' in html
    assert "Lucid Society" in html


def test_welcome_page_sends_strict_csp(client):
    response = client.get(reverse("core:welcome"))

    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_welcome_rejects_post(client):
    response = client.post(reverse("core:welcome"))

    assert response.status_code == 405


def test_welcome_allows_head(client):
    assert client.head(reverse("core:welcome")).status_code == 200


def test_favicon_redirects_to_static_logo(client):
    response = client.get("/favicon.ico")

    assert response.status_code == 301
    assert response["Location"].endswith("img/logo-256.png")


def test_healthz_reports_ok(client):
    response = client.get(reverse("core:healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-cache" in response["Cache-Control"]


def test_icon_tag_renders_sprite_reference():
    html = Template('{% load icons %}{% icon "key" "icon-sm" %}').render(Context())

    assert 'class="icon icon-sm"' in html
    assert "icons/sprite.svg#key" in html
    assert 'aria-hidden="true"' in html


def test_icon_tag_escapes_label():
    html = Template('{% load icons %}{% icon "key" "" "<b>Keys</b>" %}').render(Context())

    assert 'aria-label="&lt;b&gt;Keys&lt;/b&gt;"' in html


def test_celery_ping_task_runs_eagerly():
    from apps.core.tasks import ping

    assert ping.delay().get() == "pong"
