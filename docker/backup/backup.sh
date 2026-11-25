#!/bin/sh
# Nightly backup container.
# At BACKUP_HOUR (local time) it writes, into ./backups on the VPS:
#   db-YYYYmmdd-HHMM.dump     pg_dump custom format (restore with pg_restore)
#   files-YYYYmmdd-HHMM.tgz   treasure pictures and slip images
# and deletes backups older than BACKUP_KEEP_DAYS. Copy ./backups off the
# server regularly (see deploy/DEPLOY.md): a backup on the same disk is not enough.
set -eu

KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
HOUR="${BACKUP_HOUR:-03}"

run_backup() {
  stamp="$(date +%Y%m%d-%H%M)"
  umask 077
  # Each step checks itself: `set -e` does not apply inside a function called from `if`.
  pg_dump --format=custom --no-owner --file="/backups/db-${stamp}.dump.part" || return 1
  mv "/backups/db-${stamp}.dump.part" "/backups/db-${stamp}.dump" || return 1
  tar -czf "/backups/files-${stamp}.tgz.part" -C /data media private || return 1
  mv "/backups/files-${stamp}.tgz.part" "/backups/files-${stamp}.tgz" || return 1
  find /backups -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'files-*.tgz' \) -mtime +"${KEEP_DAYS}" -delete
  echo "Backup ${stamp} done"
}

if [ "${1:-}" = "now" ]; then
  run_backup
  exit 0
fi

echo "Backup service started: daily at ${HOUR}:00, keeping ${KEEP_DAYS} days"
while :; do
  today="$(date +%Y%m%d)"
  if [ "$(date +%H)" = "${HOUR}" ] && [ ! -f "/backups/.done-${today}" ]; then
    if run_backup; then
      touch "/backups/.done-${today}"
      find /backups -maxdepth 1 -name '.done-*' -mtime +3 -delete
    else
      echo "Backup FAILED at $(date)" >&2
    fi
  fi
  sleep 300
done
