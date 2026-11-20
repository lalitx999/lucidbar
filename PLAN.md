# Lucid Society Portal - Rebuild Plan (Django + PostgreSQL)

Status: Draft for review
Date: 2026-11-20
Scope: Full rebuild from scratch. No data is migrated from the old MySQL system.

---

## 1. Goals

1. One stack only: Django renders every page. No separate frontend app, no REST API layer for our own pages.
2. Keep the original look and feel (black and gold, Cinzel + Montserrat, mobile-first single-column card, bottom tab bar).
3. Installable PWA that works well on phones.
4. Fix the security and correctness problems found in the old system.
5. Code follows the project rules in Section 4 (service layer, selectors, Celery for slow work, no N+1 queries).

## 2. Hard constraints

| Constraint | How we meet it |
|---|---|
| Bootstrap 5 from the provided `bootstrap-5.3.8-dist` only | Copied into `static/vendor/bootstrap/`. Themed by overriding Bootstrap CSS variables in our own `lucid.css`. |
| No external CDN | All CSS, JS, fonts and icons are served from our own `static/`. A Content-Security-Policy of `'self'` enforces this in production. |
| No emoji anywhere (UI, messages, emails, Telegram, code comments) | Icons are a self-hosted inline SVG sprite. A test scans templates and locale files for emoji code points and fails the build if any are found. |
| English first | `LANGUAGE_CODE = "en"`. All strings are wrapped in `gettext` from day one, so Thai can be added later as a `.po` file without code changes. |
| OTP by email via Hostinger | Django SMTP backend pointed at Hostinger (`smtp.hostinger.com`, port 465, SSL). |
| Notifications via Telegram only | No Firebase, no web push. In-app inbox ("Whispers") for members, Telegram for staff/admin. |
| Deploy to a new VPS | Docker Compose on the VPS. The user runs deploys and production migrations (rule R0). |

## 3. Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Framework | Django 5.2 LTS | Supported until April 2028. |
| Database | PostgreSQL 17 | |
| Background jobs | Celery 5 + Redis 7 | Email, Telegram, EasySlip calls. Celery Beat for scheduled jobs. |
| Web server | Gunicorn behind Nginx | Nginx serves `/static/` and terminates TLS (Let's Encrypt via certbot). |
| Static files | WhiteNoise as fallback; Nginx in production | `ManifestStaticFilesStorage` for cache-busting (needed for the PWA). |
| Config | `django-environ` | Secrets only in `.env`, never in code. |
| Frontend JS | Vanilla JS (ES modules) + Bootstrap bundle | No build step, no npm. |
| Tests | pytest + pytest-django + factory_boy | |
| Lint/format | ruff | |

Python dependencies are kept small: `django`, `psycopg[binary]`, `django-environ`, `celery`, `redis`, `requests`, `gunicorn`, `whitenoise`, `qrcode`, `Pillow`, and dev-only test tools.

## 4. Coding rules (project standard)

1. **ORM**
   - No bare `objects.all()` in views or templates.
   - Every relation that is displayed uses `select_related()` / `prefetch_related()`.
   - Large lists use `.only()` / `.values()` and pagination.
   - No queries inside loops; use `bulk_create`, `bulk_update`, `update()`.
   - In dev, `django-debug-toolbar` and a test helper (`assertNumQueries`) guard key pages.
2. **Architecture**
   - Business logic lives in `<app>/services/*.py`.
   - Read queries that are more than a one-liner live in `<app>/selectors/*.py`.
   - Views only: parse request, call a service or selector, render or redirect.
   - Models hold fields, constraints and small properties only.
3. **Background work**
   - Sending email, calling Telegram, calling EasySlip run in Celery tasks only, never in the request cycle.
   - Tasks use `requests` with explicit timeouts and retry with backoff.
   - Tasks are idempotent (safe to retry).
4. **Admin and permissions**
   - Django Admin is for the superuser only (technical maintenance).
   - Staff and managers use a custom dashboard built with Django templates + Bootstrap.
   - Every dashboard view is protected by a custom decorator (`@staff_required`, `@manager_required`) built on `user_passes_test` / permissions.
5. **Config and security**
   - Settings split: `config/settings/base.py`, `local.py`, `production.py`.
   - `DEBUG = False` in production, `SECURE_*` headers on, HSTS, secure + HttpOnly cookies, CSRF on every form.

## 5. Project structure

```
new_lucid/
├── manage.py
├── pyproject.toml
├── .env.example
├── docker/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── entrypoint.sh
├── docker-compose.yml            # local dev
├── docker-compose.prod.yml       # VPS
├── config/
│   ├── settings/{base,local,production}.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
├── apps/
│   ├── core/          # base templates, PWA views, decorators, shared utils, emoji check
│   ├── accounts/      # Member model, register, login, email OTP, age gate, profile
│   ├── memberships/   # Seal tiers (Bronze/Gold/Obsidian), prices, benefits
│   ├── payments/      # PromptPay QR, bank info, slip upload, EasySlip verification
│   ├── keys/          # Keys ledger and balance
│   ├── treasures/     # Reward catalog, redemption, member inventory
│   ├── reveal/        # Weekly Chosen draw and prize wheel
│   ├── whispers/      # Member inbox and broadcasts
│   ├── bookings/      # Chamber / table reservations
│   ├── checkin/       # Daily check-in
│   ├── notifications/ # Telegram and email Celery tasks
│   └── dashboard/     # Custom staff/manager dashboard
├── templates/
├── static/
│   ├── vendor/bootstrap/         # from bootstrap-5.3.8-dist
│   ├── fonts/                    # Cinzel, Montserrat (woff2, self-hosted)
│   ├── icons/sprite.svg
│   ├── css/lucid.css
│   ├── js/
│   └── img/                      # logo, posters, PWA icons
├── locale/                       # en now, th later
└── tests/
```

Each app follows the same layout:

```
apps/keys/
├── models.py
├── services/ledger_service.py
├── selectors/ledger_selector.py
├── views.py
├── urls.py
├── forms.py
├── tasks.py          # only if the app has background work
├── admin.py
└── tests/
```

## 6. Data model

All money is stored as integer satang. All timestamps are timezone-aware (`Asia/Bangkok`).

**accounts**
- `Member` (custom user, `AbstractBaseUser + PermissionsMixin`, login by email)
  - email (unique), full_name, username (unique handle), phone + country_code, date_of_birth, nationality
  - status: pending_verification / active / suspended
  - email_verified_at, created_at
- `EmailOTP`: member, purpose (register / login / reset), code_hash, expires_at, attempts, consumed_at

**memberships**
- `SealTier`: code (bronze / gold / obsidian), name, price_satang, period_days, initial_keys, benefits text, sort_order, is_active. Edited from the dashboard; prices are never hardcoded.
- `Membership`: member, tier, starts_at, ends_at, source_payment (nullable for Bronze)

**payments**
- `PaymentIntent`: member, tier, amount_satang, reference code, status (awaiting_slip / verifying / approved / rejected / expired), created_at, expires_at
- `PaymentSlip`: intent, image (private storage), sha256, trans_ref (unique, nullable until verified), provider_response (JSON), verified_at, reject_reason

**keys**
- `KeysAccount`: member (one-to-one), balance (with `CheckConstraint balance >= 0`)
- `KeysEntry`: account, delta, balance_after, reason (signup_bonus / purchase / redeem / checkin / spending / admin_adjust / prize), reference (generic), created_by, created_at

**treasures**
- `Treasure`: name, category, description, image, keys_cost, stock (nullable = unlimited), is_featured, is_active
- `Redemption`: member, treasure, keys_spent, status (ready / handed_over / cancelled), handed_over_by, handed_over_at

**reveal**
- `Epoch`: week number, starts_at, ends_at, status
- `ChosenDraw`: epoch (unique), winner, drawn_by, seed_audit, created_at
- `WheelPrize`: 12 segments with label, value text, weight, is_active
- `WheelSpin`: member, epoch, prize, created_at (unique per member per epoch)

**whispers**
- `Whisper`: member (nullable for broadcast), title, body, is_read, created_at
- `Broadcast`: title, body, audience (all / tier), sent_by, created_at

**bookings**
- `Booking`: member, date, time_slot, guests, note, status (requested / confirmed / declined / cancelled), handled_by

**checkin**
- `CheckIn`: member, date (unique together with member), method (staff_scan), created_by

## 7. Key flows and how they are made safe

**7.1 Registration with email OTP**
1. Member fills the form: name, email, phone with country code, date of birth, nationality, password.
2. Server checks age >= 20 from date of birth. Underage is rejected.
3. Account created as `pending_verification`; `EmailOTP` created with a 6-digit code from `secrets`, stored as a hash, valid 10 minutes.
4. Celery task sends the code via Hostinger SMTP.
5. Member enters the code. Max 5 attempts per code; max 3 codes per 15 minutes per email (rate limit in Redis).
6. On success: account becomes active, Bronze membership and signup keys are granted in one transaction.

**7.2 Seal purchase and slip verification**
1. Member picks Gold or Obsidian. Server creates a `PaymentIntent` with the price from `SealTier`.
2. Pay screen shows the two original tabs: Bank Transfer (account details + copy button + passbook image) and PromptPay QR (tap to enlarge).
3. Member uploads the slip. The view only saves the file, sets status `verifying`, and enqueues a Celery task. The page polls a small status endpoint every few seconds.
4. Task calls EasySlip with `requests` (timeout + retries), checks: amount matches, receiver account matches the configured account, `trans_ref` not used before (unique DB constraint is the final guard).
5. On approval, one `transaction.atomic()` block: mark intent approved, create `Membership`, credit keys. Then a Telegram alert with the slip is queued for staff.
6. On rejection, the member sees the reason and can upload again. Staff can also approve or reject manually from the dashboard.

Slip images are stored outside `static/` and are only served through a permission-checked view.

**7.3 Keys ledger**
All balance changes go through one function, `ledger_service.post_entry()`:
- `transaction.atomic()` + `select_for_update()` on `KeysAccount`
- writes `KeysEntry` and updates `balance` together
- the DB constraint makes a negative balance impossible even if code has a bug

Redeeming treasures, check-ins, prizes and admin adjustments all call this function.

**7.4 Weekly Chosen and the wheel**
- Manager presses "Run draw" for the current epoch. Winner picked with `secrets.SystemRandom` from eligible active members. One draw per epoch (unique constraint).
- The winner can spin once per epoch (unique constraint on `WheelSpin`). The server chooses the prize by weight; the browser only plays the animation to the segment the server returned.
- Prize goes into the member's inventory and inbox; staff get a Telegram alert.

**7.5 Check-in**
The old system trusted GPS coordinates sent by the phone, which are easy to fake. New flow: staff scan the member's QR card at the door from the staff dashboard, which records the check-in and awards keys. One check-in per member per day (unique constraint).

**7.6 Member QR card**
QR encodes a signed token (`django.core.signing`, time-limited), not the raw member ID, so a screenshot cannot be reused forever. Rendered server-side as SVG with the `qrcode` library.

## 8. User interface (keep the original look)

**Theme** (in `static/css/lucid.css`, overriding Bootstrap variables):
- Background `#050505`, app surface `#000000`, card `#161616`, border `#2a2a2a`
- Gold `#D4AF37`, gold dark `#b89025`, gold light `#f5df97`
- Body font Montserrat, display font Cinzel, both self-hosted woff2
- Gold glow utilities (`.glow-gold`, `.text-glow`) and the thin gold scrollbar carried over
- `data-bs-theme="dark"` on `<html>`

**Layout**
- Centered mobile column, max width 448px (same as the old `max-w-md` wrapper), full height (`100dvh`), safe-area padding for iPhone notches.
- Member area: fixed bottom tab bar with five tabs, same order as before: Portal, Keys, Reveal, Treasures, Identity. Reveal tab pulses gold when the member can spin.
- Public area: Welcome, Login, Register, OTP, Choose Seal, Pay, Waiting-for-verification gate. Same sequence as the old onboarding.
- Staff dashboard: same theme, wider layout allowed on tablets/desktop, side navigation.

**Icons**: inline SVG sprite at `static/icons/sprite.svg`, used as `<svg><use href="...#keys"/></svg>`. Line-icon style matching the old Lucide look. No emoji.

**Interactivity** (vanilla JS, no framework):
- Slip status polling
- Wheel spin animation (CSS transform to the server-chosen segment)
- Copy-to-clipboard, image zoom modal (Bootstrap modal), QR enlarge modal
- Install-app prompt

## 9. PWA

- `manifest.webmanifest` served by Django: name, short name, `display: standalone`, `start_url: /portal/`, black background, gold theme color, portrait orientation.
- Proper icons: 192 and 512 px, plus a separate maskable icon and an Apple touch icon (the old manifest reused one logo for all sizes).
- Service worker at `/sw.js` (served from the root path so its scope covers the whole site):
  - Pre-caches the app shell: Bootstrap CSS/JS, `lucid.css`, fonts, sprite, logo, offline page.
  - Static assets: cache-first (safe because file names are hashed by `ManifestStaticFilesStorage`).
  - HTML pages: network-first, with fallback to the offline page.
  - Never caches POST requests, slip uploads, or authenticated pages that show balances (so a member never sees stale keys).
  - Versioned cache name; old caches deleted on activate.
- Custom "Add to Home Screen" banner for Android (`beforeinstallprompt`) and a short instruction sheet for iOS Safari.
- Lighthouse PWA and performance checks are part of the release checklist.

## 10. Staff dashboard (custom, not Django Admin)

Roles (Django Groups):
- **Staff**: scan member QR, record check-in, record spending, hand over redemptions and prizes, view bookings.
- **Manager**: everything Staff can do, plus members (search, suspend), payments (manual approve/reject, view slips), keys adjustments with reason, treasures CRUD, seal tiers and prices, wheel prizes, run the weekly draw, broadcasts, simple reports.
- **Superuser**: Django Admin for maintenance only.

The dashboard has its own login URL, and every view checks role with the custom decorators. All manager actions write an audit log entry.

## 11. Notifications

| Event | Member | Staff (Telegram) |
|---|---|---|
| OTP | Email | - |
| Payment approved / rejected | Inbox + email | Slip photo + member details |
| Redemption | Inbox | Item to prepare |
| Wheel prize | Inbox | Prize to prepare |
| Booking request | Inbox on confirm/decline | Booking details |
| Broadcast | Inbox | - |

All sends are Celery tasks with retries. A failed Telegram message never blocks or breaks the member's action.

## 12. Security checklist

- No secrets in code or in the repo. `.env` git-ignored, `.env.example` committed.
- No hardcoded admin account. Superuser created with `createsuperuser`.
- Session auth with secure, HttpOnly, SameSite=Lax cookies. CSRF on all forms.
- Login and OTP rate limiting (Redis).
- Strict Content-Security-Policy (`default-src 'self'`), HSTS, X-Frame-Options DENY.
- Uploaded slips: type and size checked, re-encoded with Pillow, stored privately.
- Random choices with `secrets`, never `random`.
- Database constraints back up every business rule that matters (unique trans_ref, non-negative balance, one spin per epoch, one check-in per day).
- Personal data (date of birth, phone, slips) handled with Thailand's PDPA in mind: a privacy notice, and a retention policy for slip images (decision needed, see Section 15).

## 13. Deployment (new VPS)

Containers in `docker-compose.prod.yml`: `nginx`, `web` (Gunicorn), `worker` (Celery), `beat` (Celery Beat), `postgres`, `redis`.

- Ubuntu 24.04 LTS, firewall allowing only 22/80/443, SSH key login only.
- TLS with Let's Encrypt.
- Nightly `pg_dump` backup with rotation, copied off the server.
- Logs to stdout, collected by Docker; error alerts sent to the staff Telegram chat.

Following the project rule R0: the user runs the deploy, production migrations and anything touching the production database. The AI prepares scripts and a written runbook.

## 14. Phases

| Phase | Deliverable | Done when |
|---|---|---|
| 0. Foundation | Repo, settings split, Docker dev (Postgres, Redis), Celery wired, Bootstrap + fonts + sprite in static, base template with original theme, emoji-check test | `docker compose up` shows the themed welcome page |
| 1. Accounts | Custom Member, register, age gate, email OTP via Hostinger, login/logout, password reset, profile | A new member can register and verify by email |
| 2. Memberships + Payments | Seal tiers, Choose Seal, Pay screen with two tabs, slip upload, EasySlip task, Telegram alert, manual approve in dashboard | Gold purchase completes end to end with a real slip in test mode |
| 3. Keys + Treasures | Ledger service, Keys page, Treasures catalog, redemption, staff hand-over | Keys cannot go negative under concurrent requests (tested) |
| 4. Reveal + Whispers | Epochs, draw, wheel with animation, inbox, broadcasts | Full weekly cycle works |
| 5. Bookings + Check-in + Identity card | Bookings, signed QR card, staff scan check-in | Staff can scan a card and check in a member |
| 6. Dashboard completion | Members, payments, tiers, prizes, reports, audit log | Manager can run the club without Django Admin |
| 7. PWA + polish | Manifest, service worker, offline page, install prompt, Lighthouse checks | Installs on Android and iOS, passes Lighthouse PWA checks |
| 8. Hardening + Deploy | Security headers, rate limits, backups, runbook, VPS setup | User deploys to the VPS |

Phases 0 to 3 give the core loop (register, pay, earn keys, redeem) and are the first milestone.

## 15. Open questions

1. **Domain name** for the VPS (needed for TLS, the Hostinger mail sender, and the PWA scope).
2. **Hostinger mailbox** to send from (for example `no-reply@<domain>`). Its SPF/DKIM must be set on the domain so OTP emails do not land in spam.
3. **Prices and keys per tier**: confirm Bronze free / 2 keys, Gold 499 THB / 10 keys, Obsidian 990 THB / 30 keys, monthly.
4. **Membership expiry**: when a monthly Seal ends, does the member drop to Bronze automatically?
5. **Wheel prize weights**: are all 12 segments equally likely, or should high-value prizes be rarer?
6. **Slip retention**: how long to keep slip images (for example 12 months) before deleting.
7. **Fonts**: Cinzel and Montserrat (both free under the SIL Open Font License) need their woff2 files added to `static/fonts/`. They can be downloaded once and committed.
8. **Thai language**: add in a later phase after English is complete?
