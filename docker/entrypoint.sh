#!/bin/sh
# Container entrypoint. Waits for PostgreSQL, then runs the given command.
# Migrations are NOT run automatically: in production the operator runs them
# explicitly (project rule R0). In local dev, set DJANGO_AUTO_MIGRATE=1.
set -e

python - <<'PY'
import os, sys, time
import psycopg
import environ

url = environ.Env().db_url_config(os.environ["DATABASE_URL"])
for attempt in range(30):
    try:
        psycopg.connect(
            host=url["HOST"], port=url["PORT"] or 5432, dbname=url["NAME"],
            user=url["USER"], password=url["PASSWORD"], connect_timeout=2,
        ).close()
        break
    except psycopg.OperationalError:
        print("Waiting for PostgreSQL...", flush=True)
        time.sleep(1)
else:
    sys.exit("PostgreSQL is not reachable.")
PY

if [ "${DJANGO_AUTO_MIGRATE:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
