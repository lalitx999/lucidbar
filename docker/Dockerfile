# syntax=docker/dockerfile:1
# One image for web, Celery worker and Celery beat. The command differs per service.

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Run as a non-root user.
RUN groupadd --system app && useradd --system --gid app --home /app app

ARG REQUIREMENTS=requirements/base.txt
COPY requirements/ requirements/
RUN pip install -r ${REQUIREMENTS}

COPY --chown=app:app . .
RUN chmod +x docker/entrypoint.sh

USER app

EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
