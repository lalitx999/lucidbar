"""Static checks of the production deploy files (Docker is never run locally)."""

import os
import stat
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _compose():
    return yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text())


def test_only_nginx_publishes_ports():
    services = _compose()["services"]

    published = {name for name, svc in services.items() if svc.get("ports")}

    assert published == {"nginx"}


def test_slips_are_never_mounted_into_nginx():
    nginx_volumes = " ".join(_compose()["services"]["nginx"]["volumes"])

    assert "private" not in nginx_volumes
    assert "static:/srv/static:ro" in nginx_volumes


def test_production_services_use_production_settings_and_no_auto_migrate():
    services = _compose()["services"]

    for name in ("web", "worker", "beat"):
        env = services[name]["environment"]
        assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.production", name
        assert env.get("DJANGO_AUTO_MIGRATE", "0") != "1", name  # rule R0


def test_all_expected_services_exist():
    assert set(_compose()["services"]) >= {"nginx", "web", "worker", "beat", "db", "redis", "certbot", "backup"}


def test_nginx_template_routes():
    conf = (ROOT / "docker/nginx/templates/lucid.conf.template").read_text()

    assert "/.well-known/acme-challenge/" in conf
    assert "location /media/treasures/" in conf
    assert "location /media/ {\n        return 404;" in conf
    assert "${DOMAIN}" in conf
    assert "X-Real-IP" in (ROOT / "docker/nginx/templates/proxy_params.inc").read_text()


def test_docker_image_excludes_secrets_and_private_files():
    ignored = (ROOT / ".dockerignore").read_text().split()

    for entry in (".env", ".env.*", "private", "backups", ".git"):
        assert entry in ignored


def test_scripts_are_executable():
    for rel in (
        "deploy/init-letsencrypt.sh",
        "deploy/vps-setup.sh",
        "docker/entrypoint.sh",
        "docker/nginx/reload-loop.sh",
    ):
        mode = os.stat(ROOT / rel).st_mode
        assert mode & stat.S_IXUSR, rel


def test_env_example_lists_production_essentials():
    text = (ROOT / "deploy/env.production.example").read_text()

    for key in ("DOMAIN=", "DJANGO_SECRET_KEY=", "DJANGO_ADMIN_URL=", "POSTGRES_PASSWORD=", "EMAIL_HOST_PASSWORD="):
        assert key in text
    # No real secrets committed: every secret line is empty in the example.
    for line in text.splitlines():
        if line.startswith(("DJANGO_SECRET_KEY=", "POSTGRES_PASSWORD=", "EMAIL_HOST_PASSWORD=", "TELEGRAM_BOT_TOKEN=")):
            assert line.endswith("="), line
