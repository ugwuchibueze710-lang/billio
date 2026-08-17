# Billio

Your bills. Your data. Your control. No bank connections. No email access.

Billio is a bills & subscriptions tracker you enter data into yourself — manually, by describing a bill in plain language, or by uploading a photo. It remembers due dates, sends reminders, tracks payment history accurately over time, and never connects to a bank account or reads your email inbox.

## Stack

- **Backend:** Flask + SQLAlchemy + Alembic (Flask-Migrate), PostgreSQL
- **Frontend:** React (Vite) + Tailwind CSS, installable as a PWA with Web Push
- **AI:** Groq (bill photo extraction, natural-language entry, assistant, spending-audit explanations) — used only for understanding language/images and explaining numbers the backend already calculated; Groq never performs financial math and never touches SQL directly
- **Object storage:** Cloudflare R2 (S3-compatible) for uploaded bill photos
- **Email:** Resend (password resets, email reminders)
- **Hosting target:** Render (see `render.yaml`)

## Project layout

```
billio/
  backend/           Flask API, SQLAlchemy models, Alembic migrations, pytest suite
  frontend/          React + Vite + Tailwind PWA
  docs/              Standalone privacy policy & terms of service
  render.yaml         Render Blueprint describing all three services
```

## Local development

### Prerequisites

- Python 3.11+
- Node 18+
- PostgreSQL 14+ running locally

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

createdb billio_dev   # or: psql -c "CREATE DATABASE billio_dev;"

cp .env.example .env
# Edit .env: at minimum set SECRET_KEY, JWT_SECRET_KEY, DATABASE_URL.
# Groq / Resend / R2 / VAPID keys are optional for local dev -- every
# AI/email/storage/push feature degrades gracefully and tells the user
# it's unavailable rather than breaking the app if those are unset.

export FLASK_APP=wsgi.py
flask db upgrade        # applies the initial schema migration

flask run --port 5001
```

The API is now at `http://localhost:5001`. Health check: `GET /healthz`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # set VITE_API_BASE_URL=http://localhost:5001
npm run dev
```

Open `http://localhost:5173`.

### Running tests

```bash
cd backend
source venv/bin/activate
createdb billio_test   # a separate database from billio_dev
export FLASK_ENV=testing
export TEST_DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/billio_test
export SECRET_KEY=test JWT_SECRET_KEY=test
python -m pytest -q
```

73 tests cover: the recurrence engine's month-length/leap-year/end-of-month edge cases, auth (signup, login, password change/reset, token revocation), bill CRUD and the mark-paid/recurrence-generation flow (including idempotency under double-submission), cross-user authorization isolation across every resource type (bills, occurrences, history, settings, feedback, admin), the feedback system (validation, rate limiting, admin-note privacy, audit logging), the deterministic audit engine (Decimal precision, period comparison, duplicate-payment detection, AI-unavailable fallback), Groq output validation/normalization, and bill-image validation.

## Key architectural decisions (things you may want to revisit)

These were genuine judgment calls made while building against the spec, documented here rather than buried in code comments:

1. **Auth model:** signup requires only first name + username + password (no email). An optional, separately-verified email unlocks password-reset-by-email and email reminders. Without a verified email, password reset currently has no self-service path (see "Known gaps" below).
2. **Occurrence status (upcoming/due today/overdue/paid) is never stored** — it's computed at read time from `due_date` + `is_paid` + the user's timezone, so it can never drift out of sync with the calendar.
3. **The next occurrence of a recurring bill is generated when the current one is marked paid**, not on a fixed calendar schedule independent of payment. The spec explicitly leaves this product decision open ("can be decided by the product team") as long as historical accuracy is preserved, which this satisfies: an unpaid bill stays visibly overdue indefinitely rather than quietly rolling into a "current" unpaid state for a new period.
4. **Editing a bill's amount** only changes occurrences that are unpaid **and** not yet due — anything due today, overdue, or already paid keeps its original snapshot amount.
5. **Cancelling a bill** removes only unpaid, not-yet-due occurrences; anything that already represents a real obligation (due, overdue, or paid) is preserved.
6. **Audit "spending"** is computed from the `payments` table (money actually paid, by `paid_at`), not from bill due dates — this is what lets the audit engine answer "what did I actually pay in August" accurately even if a bill was paid late or early.

## Known gaps / things to decide before shipping to real users

Built honestly rather than silently glossed over:

- **Password reset without an email on file** has no self-service flow yet (by design, since email is optional) — you'll want a support-assisted reset process before launch.
- **Rate limiting storage** defaults to in-process memory (`memory://`), which only works correctly with a single server process. Set `REDIS_URL` before running more than one backend instance.
- **HEIC image support**: validated and accepted, but Pillow's HEIC decode support depends on system libraries (`libheif`) being present in the deployment image — verify this on your Render build image, or convert HEIC client-side before upload if it's not available.
- The bundled `docs/PRIVACY_POLICY.md` and `docs/TERMS_OF_SERVICE.md` accurately describe what the app does, but contain bracketed placeholders for business facts (legal entity name, jurisdiction, support email) that only you can supply, and should get a lawyer's review before publishing.

## Deploying to Render

1. Push this repo to GitHub/GitLab.
2. In Render, create a new **Blueprint** and point it at the repo — it will read `render.yaml` and create three services: `billio-api` (web), `billio-reminder-scheduler` (cron, hourly), and `billio-frontend` (static site), plus a managed Postgres database.
3. Render generates `SECRET_KEY`/`JWT_SECRET_KEY` automatically and wires `DATABASE_URL` from the managed database. You still need to fill in, in the Render dashboard, every variable marked `sync: false` in `render.yaml` — see `backend/.env.example` for where to get each one:
   - `CORS_ORIGINS` → your deployed frontend's exact URL (e.g. `https://billio-frontend.onrender.com`)
   - `FRONTEND_BASE_URL` → same URL, used to build links in emails/push
   - `GROQ_API_KEY` → https://console.groq.com
   - `RESEND_API_KEY`, `RESEND_FROM_EMAIL` → https://resend.com (see domain verification below)
   - `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME` → your Cloudflare R2 bucket
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` → generate with `npx web-push generate-vapid-keys`
   - On `billio-frontend`: `VITE_API_BASE_URL` → your deployed backend's URL (e.g. `https://billio-api.onrender.com`)
4. The first deploy runs `flask db upgrade` automatically via the `release` step in `backend/Procfile` (Render's Python runtime respects this).
5. Confirm `billio-api`'s `/healthz` returns `{"status": "ok"}` and the reminder cron job has a green run in the Render dashboard.

### Resend domain verification (SPF/DKIM)

Emails will fail to send (safely — the app just tells the user email delivery isn't available, per the Groq/email failure-handling requirements) until your sending domain is verified:

1. In the Resend dashboard, go to **Domains → Add Domain** and enter your domain (e.g. `yourdomain.com`).
2. Resend gives you DNS records to add: an **SPF** `TXT` record, a **DKIM** `TXT`/`CNAME` record, and usually a `DMARC` record.
3. Add those records at your DNS provider (Cloudflare, Namecheap, etc.).
4. Wait for DNS propagation (usually minutes, sometimes longer) and click **Verify** in Resend.
5. Set `RESEND_FROM_EMAIL=Billio <noreply@yourdomain.com>` using that verified domain.

### Cloudflare R2 setup

1. In the Cloudflare dashboard, go to **R2 → Create bucket**, name it (e.g. `billio-bill-documents`).
2. Go to **R2 → Manage API Tokens → Create API Token**, grant it Object Read & Write on that bucket, and copy the Access Key ID / Secret Access Key.
3. Your `S3_ENDPOINT_URL` is `https://<account-id>.r2.cloudflarestorage.com` (account ID is shown in the R2 dashboard).

## Feature overview

- **Auth:** username + password (Argon2id hashing), JWT access/refresh tokens, per-account `token_version` so a password change or logout instantly invalidates every previously issued token, login rate limiting, optional verified email for password reset & email reminders.
- **Bills:** manual entry, natural-language entry ("Netflix is $17.99 every month on the 20th"), and photo upload (single or batch, with duplicate detection) — AI proposals always require explicit user confirmation before anything is saved.
- **Recurrence engine:** month-length/leap-year/end-of-month-safe (see `backend/app/services/recurrence.py` and `backend/tests/test_recurrence.py`).
- **Dashboard:** status system (upcoming → due today → overdue → paid) computed live, "you're all caught up" state, SQL-computed monthly recurring spend.
- **History:** month-by-month browsing with per-month expected/paid/outstanding summaries, filterable, paginated.
- **Reminders:** hourly-safe idempotent scheduler, Web Push (installable PWA) + email, configurable intervals, notification-content privacy setting, deep links from notification → the exact bill.
- **AI assistant & audit:** function-calling assistant scoped to the authenticated user's own data; audit engine does all math in Python `Decimal`/SQL, Groq only explains precomputed figures and its explanations are validated against the real numbers before being shown (falling back to a deterministic summary if it invents anything).
- **Feedback:** persistent in-app feedback bar, admin dashboard with filtering/search/status/internal notes, full authorization isolation, audit-logged admin actions.
- **Account:** CSV export of all bills & history, permanent account deletion (password-confirmed, cascades through all associated data including object storage).

## Security notes

- Every endpoint resolves the authenticated user from the verified JWT (`get_current_user()`); no endpoint accepts or trusts a client-supplied user ID.
- All monetary values are `NUMERIC(12,2)` in Postgres and Python `Decimal` in application code — never floats.
- Structured JSON logging never includes passwords, tokens, or full bill contents.
- CORS is an explicit allow-list (`CORS_ORIGINS`), never a wildcard.
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options, HSTS in production, etc.) are set on every response.
