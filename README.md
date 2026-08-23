# Billio

Your bills. Your data. Your control. No bank connections. No email access.

Billio is a bills & subscriptions tracker you enter data into yourself — manually, by describing a bill in plain language, or by uploading a photo. It remembers due dates, sends reminders, tracks payment history accurately over time, and never connects to a bank account or reads your email inbox.

## Stack

- **Backend:** Flask + SQLAlchemy + Alembic (Flask-Migrate), PostgreSQL
- **Frontend:** React (Vite) + Tailwind CSS, installable as a PWA with Web Push
- **Auth:** Supabase Auth — Billio's own `/api/auth/*` endpoints proxy to Supabase's Admin/token REST APIs, so the frontend never talks to Supabase directly. Signup stays email-optional (a server-generated placeholder address is used internally when none is given); see "Auth model" below.
- **AI:** Groq (bill photo/PDF extraction, natural-language entry, assistant, spending-audit explanations) — used only for understanding language/images and explaining numbers the backend already calculated; Groq never performs financial math and never touches SQL directly
- **Object storage:** Supabase Storage (S3-compatible) for uploaded bill photos and PDFs — any other S3-compatible provider (Cloudflare R2, Backblaze B2) also works with only an env var change, see `backend/.env.example`
- **Email:** Resend (password resets, email reminders) — kept fully separate from Supabase's own email features
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
# Edit .env: at minimum set SECRET_KEY, DATABASE_URL, SUPABASE_URL,
# SUPABASE_SERVICE_ROLE_KEY -- auth won't work without a Supabase project
# (see "Setting up Supabase" below). Groq / Resend / Storage / VAPID keys
# are optional for local dev -- every AI/email/storage/push feature
# degrades gracefully and tells the user it's unavailable rather than
# breaking the app if those are unset.

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
export SECRET_KEY=test
python -m pytest -q
```

**Known gap:** the test suite (and its `tests/conftest.py` fixtures) still assume the pre-Supabase local-password auth system and have not been updated for the Supabase Auth migration yet -- they will fail as-is until `make_user`/auth-related tests are rewritten to create real Supabase users (or a mocked `supabase_admin`) instead of hashing a password locally. Everything else the suite covers is still accurate: the recurrence engine's month-length/leap-year/end-of-month edge cases, bill CRUD and the mark-paid/recurrence-generation flow (including idempotency under double-submission), cross-user authorization isolation across every resource type (bills, occurrences, history, settings, feedback, admin), the feedback system (validation, rate limiting, admin-note privacy, audit logging), the deterministic audit engine (Decimal precision, period comparison, duplicate-payment detection, AI-unavailable fallback), Groq output validation/normalization, and bill-image validation.

## Key architectural decisions (things you may want to revisit)

These were genuine judgment calls made while building against the spec, documented here rather than buried in code comments:

1. **Auth model:** signup requires only first name + username + password (no email). An optional, separately-verified email unlocks password-reset-by-email and email reminders. Without a verified email, password reset currently has no self-service path (see "Known gaps" below). Credentials themselves live in Supabase Auth, not this database -- when no email is given, the backend generates a placeholder address (`u_<random>@billio.invalid`, using the RFC 2606-reserved `.invalid` TLD, which is guaranteed to never receive real mail) purely so Supabase has something to key the account on internally; the user never sees it and it's never treated as a real contact address.
2. **No subscription/paywall is built in.** This app is meant to be handed off working and pricing-free -- whoever takes it over adds Stripe (or any other billing) and decides pricing themselves. There's nothing to rip out first.
3. **Occurrence status (upcoming/due today/overdue/paid) is never stored** — it's computed at read time from `due_date` + `is_paid` + the user's timezone, so it can never drift out of sync with the calendar.
4. **The next occurrence of a recurring bill is generated when the current one is marked paid**, not on a fixed calendar schedule independent of payment. The spec explicitly leaves this product decision open ("can be decided by the product team") as long as historical accuracy is preserved, which this satisfies: an unpaid bill stays visibly overdue indefinitely rather than quietly rolling into a "current" unpaid state for a new period.
5. **Editing a bill's amount** only changes occurrences that are unpaid **and** not yet due — anything due today, overdue, or already paid keeps its original snapshot amount.
6. **Cancelling a bill** removes only unpaid, not-yet-due occurrences; anything that already represents a real obligation (due, overdue, or paid) is preserved.
7. **Audit "spending"** is computed from the `payments` table (money actually paid, by `paid_at`), not from bill due dates — this is what lets the audit engine answer "what did I actually pay in August" accurately even if a bill was paid late or early.

## Known gaps / things to decide before shipping to real users

Built honestly rather than silently glossed over:

- **Password reset without an email on file** has no self-service flow yet (by design, since email is optional) — you'll want a support-assisted reset process before launch.
- **Rate limiting storage** defaults to in-process memory (`memory://`), which only works correctly with a single server process. Set `REDIS_URL` before running more than one backend instance.
- **The backend test suite has not been updated for the Supabase Auth migration** (see "Running tests" above) — it still assumes the old local-password system and will fail until it's rewritten against `supabase_admin`.
- **No subscription/billing is built in** — this was intentionally left out so a buyer/new owner can add their own pricing model rather than ripping one out.
- The bundled `docs/PRIVACY_POLICY.md` and `docs/TERMS_OF_SERVICE.md` accurately describe what the app does, but contain bracketed placeholders for business facts (legal entity name, jurisdiction, support email) that only you can supply, and should get a lawyer's review before publishing.

## Setting up Supabase (Auth + Storage)

Billio uses Supabase for two things only: authenticating users, and storing uploaded bill photos/PDFs. It does **not** use Supabase as its main database — that's still the Postgres instance Render manages (`billio-db`).

1. Create a free project at https://supabase.com (free tier is enough to run this app).
2. **Auth credentials:** Project Settings → API. Copy the **Project URL** (→ `SUPABASE_URL`) and the **service_role** secret key (→ `SUPABASE_SERVICE_ROLE_KEY`). Never use the **anon** public key for this — the service_role key is what lets the backend create/verify users, and it must never reach the frontend (it never does in this app; only the backend holds it).
3. In **Authentication → Providers → Email**, you can turn off "Confirm email" if you want (Billio always creates users pre-confirmed via the admin API regardless, so this setting doesn't actually matter for this app, but turning it off avoids Supabase trying to send its own confirmation emails to the placeholder `.invalid` addresses that email-less signups get).
4. **Storage credentials:** Storage → create a new bucket (e.g. `billio-bill-documents`, keep it **private**, not public). Then Storage → Settings → **S3 Access Keys** → create a new key pair. This is a separate credential pair from step 2 — map it to the `S3_*` variables in `backend/.env.example` (the S3 endpoint URL and region are shown on that same Storage Settings page).
5. Put all of the above into Render (see below) or your local `.env`.

## Making your account an admin

There is no hardcoded admin password anywhere in this codebase (an "always the same login overrides everything" admin account would be a real security hole, so it was deliberately built differently): sign up for your own account through the normal app signup screen with your own strong password, then promote that one account from Render's **Shell** tab (or locally):

```bash
flask make-admin your_username
```

That flips `is_admin=True` in the database for that account only. Admin-only routes (the feedback dashboard) then become available to it.

## Deploying to Render

`backend/.python-version` pins the Python version Render builds with to `3.12`. This matters because `psycopg2-binary`'s prebuilt wheel isn't compatible with Render's newer default Python (3.14 as of early 2026) — installing it there causes the backend to crash on startup with `ImportError: ... undefined symbol: _PyInterpreterState_Get`. Don't delete this file unless you've confirmed a newer `psycopg2-binary` release supports whatever Python version you switch to.

1. Push this repo to GitHub/GitLab.
2. In Render, create a new **Blueprint** and point it at the repo — it will read `render.yaml` and create two services: `billio-api` (web) and `billio-frontend` (static site), plus a managed Postgres database (`billio-db`).
3. Render generates `SECRET_KEY` automatically and wires `DATABASE_URL` from the managed database. You still need to fill in, in the Render dashboard, every variable marked `sync: false` in `render.yaml` — see `backend/.env.example` for where to get each one:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` → your Supabase project (see "Setting up Supabase" above) -- **required**, auth won't work without these
   - `CORS_ORIGINS` → your deployed frontend's exact URL (e.g. `https://billio-frontend.onrender.com`)
   - `FRONTEND_BASE_URL` → same URL, used to build links in emails/push
   - `GROQ_API_KEY` → https://console.groq.com
   - `RESEND_API_KEY`, `RESEND_FROM_EMAIL` → https://resend.com (see domain verification below)
   - `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION` → your Supabase Storage bucket (see "Setting up Supabase" above)
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` → generate with `npx web-push generate-vapid-keys`
   - `NOTIFICATION_SCHEDULER_TOKEN` → any long random string you make up yourself (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`) — this protects the hourly reminder endpoint, see below
   - On `billio-frontend`: `VITE_API_BASE_URL` → your deployed backend's URL (e.g. `https://billio-api.onrender.com`)
4. `billio-api`'s start command runs `flask db upgrade` before starting gunicorn on every deploy/restart, so the database schema is created automatically on the first deploy and kept up to date on every later one. (Render's Procfile `release` step and its newer "Pre-Deploy Command" feature both require a paid plan, so this project runs the migration inline in the start command instead, which works on the free tier.)
5. Confirm `billio-api`'s `/healthz` returns `{"status": "ok"}`.

### Hourly reminder scheduler (no Render Cron Job needed)

Render discontinued the free plan for Cron Jobs, so this Blueprint does **not** create one (avoiding an unnecessary ~$1/month minimum charge). Instead, `billio-api` exposes `POST /api/notifications/run-scheduler`, which runs the exact same reminder scan a cron job would, guarded by a constant-time comparison against the `NOTIFICATION_SCHEDULER_TOKEN` you set above. The endpoint is disabled entirely (returns 401) if that token is unset.

Wire up a **free** external scheduler to call it once an hour:

1. Go to a free cron-ping service such as https://cron-job.org (no affiliation — any similar service works) and create an account.
2. Create a new cron job:
   - URL: `https://<your-billio-api-url>.onrender.com/api/notifications/run-scheduler`
   - Method: `POST`
   - Schedule: every hour (e.g. `0 * * * *`)
   - Custom header: `X-Scheduler-Token: <the exact value you set for NOTIFICATION_SCHEDULER_TOKEN>`
3. Save it, trigger one manual test run, and confirm it returns `{"message": "Reminder scan complete.", "stats": {...}}`.

If you'd rather use Render's own Cron Job later (once you're OK with the small monthly cost), add back a `type: cron` service to `render.yaml` running `flask send-reminders` on a `plan: starter` (or higher) schedule — see the git history of this file for the exact block that was removed.

### Resend domain verification (SPF/DKIM)

Emails will fail to send (safely — the app just tells the user email delivery isn't available, per the Groq/email failure-handling requirements) until your sending domain is verified:

1. In the Resend dashboard, go to **Domains → Add Domain** and enter your domain (e.g. `yourdomain.com`).
2. Resend gives you DNS records to add: an **SPF** `TXT` record, a **DKIM** `TXT`/`CNAME` record, and usually a `DMARC` record.
3. Add those records at your DNS provider (Cloudflare, Namecheap, etc.).
4. Wait for DNS propagation (usually minutes, sometimes longer) and click **Verify** in Resend.
5. Set `RESEND_FROM_EMAIL=Billio <noreply@yourdomain.com>` using that verified domain.

(Supabase Storage setup is covered above under "Setting up Supabase" — Cloudflare R2 or Backblaze B2 both still work as drop-in alternatives if you'd rather use one of those; only the `S3_*` env vars change.)

## Feature overview

- **Auth:** Supabase Auth (username + password at the app layer; Supabase issues and verifies the actual access/refresh tokens), login rate limiting, optional verified email for password reset & email reminders, `flask make-admin` for promoting an account after signup (see above) — no subscription/paywall is built in, by design (see "Key architectural decisions").
- **Bills:** manual entry, natural-language entry ("Netflix is $17.99 every month on the 20th"), and photo/PDF upload (camera capture or file upload, single or batch, with duplicate detection; PDFs are rasterized server-side before AI extraction but the original PDF is what's stored) — AI proposals always require explicit user confirmation before anything is saved.
- **Recurrence engine:** month-length/leap-year/end-of-month-safe (see `backend/app/services/recurrence.py` and `backend/tests/test_recurrence.py`).
- **Dashboard:** status system (upcoming → due today → overdue → paid) computed live, "you're all caught up" state, SQL-computed monthly recurring spend.
- **History:** month-by-month browsing with per-month expected/paid/outstanding summaries, filterable, paginated.
- **Reminders:** hourly-safe idempotent scheduler, Web Push (installable PWA) + email, configurable intervals, notification-content privacy setting, deep links from notification → the exact bill.
- **AI assistant & audit:** function-calling assistant scoped to the authenticated user's own data; audit engine does all math in Python `Decimal`/SQL, Groq only explains precomputed figures and its explanations are validated against the real numbers before being shown (falling back to a deterministic summary if it invents anything).
- **Feedback:** persistent in-app feedback bar, admin dashboard with filtering/search/status/internal notes, full authorization isolation, audit-logged admin actions.
- **Account:** CSV export of all bills & history, permanent account deletion (password-confirmed, cascades through all associated data including object storage).

## Security notes

- Every endpoint resolves the authenticated user from a Supabase-issued access token, verified against Supabase's public JWKS on every request (`get_current_user()`); no endpoint accepts or trusts a client-supplied user ID.
- Passwords are never stored, hashed, or seen by this codebase at all -- Supabase Auth owns them entirely. The `SUPABASE_SERVICE_ROLE_KEY` is the one credential that can create/update/delete any Supabase user, so treat it like a master key: it lives only in Render's env vars and your local `.env`, never in git, and is never sent to the frontend.
- All monetary values are `NUMERIC(12,2)` in Postgres and Python `Decimal` in application code — never floats.
- Structured JSON logging never includes passwords, tokens, or full bill contents.
- CORS is an explicit allow-list (`CORS_ORIGINS`), never a wildcard.
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options, HSTS in production, etc.) are set on every response.
