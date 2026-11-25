#!/usr/bin/env bash
# First TLS certificate for the VPS. Run ONCE, on the VPS, from the repo folder,
# after DNS for $DOMAIN points at this server:
#
#   ./deploy/init-letsencrypt.sh
#
# Nginx cannot start without a certificate, so this script:
#   1. puts a temporary self-signed certificate in the certs volume,
#   2. starts Nginx (and the app behind it),
#   3. asks Let's Encrypt for the real certificate over HTTP (webroot),
#   4. reloads Nginx with it.
# Running certbot means you accept the Let's Encrypt Subscriber Agreement.
set -euo pipefail

ENV_FILE=".env.production"
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE")

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE (copy deploy/env.production.example and fill it in)." >&2
  exit 1
fi
DOMAIN="$(grep -E '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
EMAIL="$(grep -E '^LETSENCRYPT_EMAIL=' "$ENV_FILE" | cut -d= -f2-)"
if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "Set DOMAIN and LETSENCRYPT_EMAIL in $ENV_FILE." >&2
  exit 1
fi

if "${COMPOSE[@]}" run --rm --no-deps --entrypoint sh certbot -c "test -f /etc/letsencrypt/renewal/${DOMAIN}.conf"; then
  echo "A Let's Encrypt certificate for ${DOMAIN} already exists. Nothing to do."
  exit 0
fi

echo "1/4 Temporary self-signed certificate for ${DOMAIN}"
TMP="$(mktemp -d)"
trap 'rm -r -- "${TMP:?}"' EXIT
openssl req -x509 -nodes -newkey rsa:2048 -days 1 -subj "/CN=${DOMAIN}" \
  -keyout "${TMP}/privkey.pem" -out "${TMP}/fullchain.pem" 2>/dev/null
"${COMPOSE[@]}" run --rm --no-deps -v "${TMP}:/dummy:ro" --entrypoint sh certbot -c \
  "mkdir -p /etc/letsencrypt/live/${DOMAIN} && cp /dummy/privkey.pem /dummy/fullchain.pem /etc/letsencrypt/live/${DOMAIN}/"

echo "2/4 Starting Nginx and the app"
"${COMPOSE[@]}" up -d nginx

echo "3/4 Requesting the real certificate"
"${COMPOSE[@]}" run --rm --no-deps --entrypoint sh certbot -c \
  "rm -r -- /etc/letsencrypt/live/${DOMAIN}"
"${COMPOSE[@]}" run --rm --no-deps --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot -d "${DOMAIN}" --email "${EMAIL}" \
  --agree-tos --no-eff-email --non-interactive

echo "4/4 Reloading Nginx"
"${COMPOSE[@]}" exec nginx nginx -s reload
"${COMPOSE[@]}" up -d certbot
echo "Done: https://${DOMAIN}/"
