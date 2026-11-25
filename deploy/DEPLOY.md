# Deploying Lucid to the VPS

This is the runbook for the production server. Following rule R0, **you** run every
step on the server. The scripts here only automate what is written below.

Stack (`docker-compose.prod.yml`): `nginx` (TLS, static files), `web` (Gunicorn),
`worker` (Celery), `beat` (scheduled jobs), `db` (PostgreSQL 17), `redis`, `certbot`
(certificate renewal), `backup` (nightly dumps).

---

## 0. Before you start

- [ ] A domain, for example `lucid.example.com`, with an **A record** pointing at the VPS IP.
- [ ] A Hostinger mailbox to send from, for example `no-reply@<domain>`, with **SPF and DKIM**
      set on the domain (Hostinger panel, Emails, DNS records). Without them OTP emails land in spam.
- [ ] Telegram bot token and staff group chat ID.
- [ ] EasySlip API key (or plan to start with `EASYSLIP_MODE=off`, where managers review every slip).
- [ ] Bank account details and, optionally, the PromptPay ID.
- [ ] A fresh Ubuntu 24.04 VPS (2 GB RAM is enough to start) and your SSH public key on it.

## 1. Harden the server (once)

```bash
ssh root@<server-ip>
git clone https://github.com/lalitx999/lucidbar.git /opt/lucid
sudo bash /opt/lucid/deploy/vps-setup.sh deploy
```

In a **new** terminal, confirm `ssh deploy@<server-ip>` works before closing the root session.
Then give the deploy user the repo:

```bash
sudo chown -R deploy:deploy /opt/lucid
```

Note: Docker publishes ports past `ufw`. Only Nginx publishes ports (80 and 443), and the database and
Redis stay on the internal Docker network. Keep it that way.

## 2. Configure

```bash
cd /opt/lucid
git checkout main            # or the release branch you are deploying
cp deploy/env.production.example .env.production
chmod 600 .env.production
nano .env.production         # fill in every value
```

Generate the secrets on the server, not on a shared machine:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"        # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"        # POSTGRES_PASSWORD
python3 -c "import secrets; print('ops-' + secrets.token_hex(6) + '/')"  # DJANGO_ADMIN_URL
```

Production refuses to start with a short secret key, the default `admin/` path, or `EASYSLIP_MODE=fake`.

## 3. First start

```bash
cd /opt/lucid
chmod +x deploy/*.sh docker/nginx/*.sh
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d db redis
```

Create the tables (R0: you run migrations):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm web python manage.py migrate
```

Get the TLS certificate and start Nginx (also starts `web`):

```bash
./deploy/init-letsencrypt.sh
```

Start everything else:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

## 4. Accounts

Superuser for Django Admin (maintenance only, at `https://<domain>/<DJANGO_ADMIN_URL>`):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm web python manage.py createsuperuser
```

Dashboard accounts (the password is asked for, never typed on the command line):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm web \
  python manage.py create_staff manager@<domain> --name "Club Manager" --phone 8XXXXXXXX --manager
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm web \
  python manage.py create_staff door@<domain> --name "Door Team" --phone 8XXXXXXXX
```

Optional demo catalogue: `python manage.py seed_demo_treasures` (same `run --rm web` prefix).

## 5. Smoke test (about 10 minutes)

- [ ] `https://<domain>/healthz/` returns `{"status": "ok", ...}`.
- [ ] `http://<domain>` redirects to https.
- [ ] Register with a real email: the OTP email arrives (check spam), and the account reaches the portal.
- [ ] `/staff/` as the manager: Overview, Members, Payments open.
- [ ] Buy Gold with a real small transfer (or use `EASYSLIP_MODE=off` and approve it in Payments).
      The Telegram group gets the alert.
- [ ] Identity tab shows the QR. The Door page scans it (a phone camera on Android Chrome, or a handheld scanner).
- [ ] On a phone: "Add to Home Screen" works, and the installed app opens full screen.
- [ ] `docker compose ... logs worker beat` shows no errors, and beat lists its schedule.
- [ ] After the first 03:00 run, `ls -lh backups/` shows a `db-*.dump` and a `files-*.tgz`.

When everything passes, raise `DJANGO_HSTS_SECONDS` to `31536000` and restart `web`.

## 6. Updating

```bash
cd /opt/lucid
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm web python manage.py migrate --plan
# read the plan; take a manual backup first if it changes data:
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backup /backup/backup.sh now
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm web python manage.py migrate
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

The service worker cache updates itself: new static file names produce a new cache version.

**Rollback**: `git checkout <previous-commit>`, then `build` and `up -d` again. If the release ran
migrations that are not backwards compatible, restore the database from the backup taken before it (section 7).

## 7. Backups and restore

The `backup` container writes to `/opt/lucid/backups/` every night at 03:00 (Bangkok time) and keeps
`BACKUP_KEEP_DAYS` days. **Copy them off the server.** From your own computer, for example weekly:

```bash
rsync -av deploy@<server-ip>:/opt/lucid/backups/ ~/lucid-backups/
```

Restore the database (this replaces the current data, so stop the app first):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production stop web worker beat
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_restore --clean --if-exists --no-owner -U lucid -d lucid < backups/db-YYYYmmdd-HHMM.dump
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

Restore pictures and slips:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm -v "$PWD/backups:/backups:ro" \
  --entrypoint sh web -c "tar -xzf /backups/files-YYYYmmdd-HHMM.tgz -C /data"
```

Practise a restore on a spare machine once, before you need it.

## 8. Day to day

| Task | Command (prefix `docker compose -f docker-compose.prod.yml --env-file .env.production`) |
|---|---|
| Status | `ps` |
| Logs | `logs -f --tail=100 web worker` |
| Django shell | `run --rm web python manage.py shell` |
| Manual backup | `run --rm backup /backup/backup.sh now` |
| Restart the app | `restart web worker beat` |

Server errors are also posted to the staff Telegram chat (at most once per 10 minutes per error, with
no personal data).

Scheduled jobs (Celery Beat): unpaid checkouts expire every 15 minutes. Every night, slip images older
than `SLIP_RETENTION_DAYS` are deleted, along with old OTP codes and expired sessions.
