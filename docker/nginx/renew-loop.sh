#!/bin/sh
# Certbot container: try to renew twice a day (renews only when close to expiry).
trap exit TERM
while :; do
  certbot renew --webroot -w /var/www/certbot --quiet
  sleep 12h &
  wait "$!"
done
