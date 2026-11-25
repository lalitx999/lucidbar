#!/bin/sh
# Run by the nginx image before it starts (/docker-entrypoint.d).
# Reload every 6 hours in the background so renewed certificates are used.
(
  while :; do
    sleep 21600
    nginx -s reload
  done
) &
