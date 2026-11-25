# Lucid Society Portal

Members portal for Lucid Society, built with Django 5.2 + PostgreSQL. One stack: Django renders every page.
See [PLAN.md](PLAN.md) for the full rebuild plan.

## Requirements

- Python 3.12+
- PostgreSQL 17, Redis 7 (local install or Docker)

## Local setup (without Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements/dev.txt
cp .env.example .env          # then set DJANGO_SECRET_KEY and DATABASE_URL
createdb lucid
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

In local development Celery tasks run in-process (`CELERY_TASK_ALWAYS_EAGER=True`), so OTP emails
print in the runserver console and no worker is needed. To test with a real worker, set
`CELERY_TASK_ALWAYS_EAGER=False` in `.env` and start one (second terminal):

```bash
.venv/bin/celery -A config worker --loglevel=info
```

## Docker (VPS only)

Docker is used for the VPS deployment, not for local development.

**Production:** follow [deploy/DEPLOY.md](deploy/DEPLOY.md). It covers server hardening, the
`docker-compose.prod.yml` stack (Nginx, Gunicorn, Celery worker and beat, PostgreSQL, Redis, certbot,
nightly backups), TLS, accounts (`manage.py create_staff`), updates, and restore.

### Compose file

```bash
cp .env.example .env          # set POSTGRES_PASSWORD and DJANGO_SECRET_KEY
docker compose up --build
```

The site runs at http://localhost:8000. Postgres is exposed on `127.0.0.1:5433` for local tools.

## Tests and lint

```bash
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The test suite also enforces project rules: no emoji, no external CDN references, no inline styles.

## Settings

| Module | Use |
|---|---|
| `config.settings.local` | Development (default for `manage.py`) |
| `config.settings.test` | Test suite (set in `pyproject.toml`) |
| `config.settings.production` | VPS (default for `wsgi.py`) |

## Project rules (short version)

- Business logic in `apps/<app>/services/`, complex reads in `apps/<app>/selectors/`, thin views.
- Email, Telegram and EasySlip calls only in Celery tasks.
- No hardcoded secrets; everything comes from `.env`.
- Bootstrap and all assets are self-hosted under `static/`. No CDN, no emoji.
