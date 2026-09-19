# Development Deployment

This is the source of truth for running the Hackathon MVP. The supported database is PostgreSQL. Docker Compose is the primary developer path; a host-run backend/frontend with either a containerized or locally installed PostgreSQL instance is the fallback.

This document describes a development/demo deployment, not a production certification. Do not expose Django's development server, Vite's development server, seeded demo credentials, or locally served media directly to the internet.

## Runtime shape

```text
Browser
  |
  | http://localhost:5173
  v
frontend (Vite/Vue development server)
  |  proxies /api and /media, preserving cookies/CSRF as same-origin
  v
backend (Django REST Framework, port 8000 inside Compose)
  |  Django ORM
  v
postgres (PostgreSQL, port 5432 inside Compose)

backend -> media_data named volume (MVP uploads)
postgres -> postgres_data named volume
```

Compose service names are part of the developer contract:

| Service | Responsibility | Development port |
| --- | --- | --- |
| `postgres` | PostgreSQL database and health check | `5432` (host exposure may be configurable) |
| `backend` | Django/DRF API, migrations, seed and tests | `8000` |
| `frontend` | Vite/Vue SPA; proxy for `/api` and `/media` | `5173` |

The browser should normally open only `http://localhost:5173`. Vite proxies `/api` and `/media` to `http://backend:8000` inside Compose. This gives the browser a single origin, makes Django session cookies straightforward, and avoids permissive credentialed CORS.

## Prerequisites

Primary path:

- Docker Engine or Docker Desktop with the Compose v2 plugin;
- Git; and
- enough free space for images, a PostgreSQL volume, Node dependencies, and mock uploads.

Local fallback additionally needs:

- Python supported by the backend project (document the exact version in `backend/requirements.txt` or `pyproject.toml`);
- Node.js supported by `frontend/package.json`;
- npm; and
- PostgreSQL, either through the Compose `postgres` service or a local installation.

Use the repository's pinned/declared dependency files. Do not install untracked global packages to make the application work.

## Environment configuration

Copy the committed placeholder file, then change local secrets:

```bash
cp .env.example .env
```

`.env` must be ignored by Git. `.env.example` contains names and safe placeholders only—never a real secret or production credential.

Expected settings:

| Variable | Purpose | Local example/notes |
| --- | --- | --- |
| `POSTGRES_DB` | Database created by the container | `hotline_doc` |
| `POSTGRES_USER` | Local database user | `hotline_doc` |
| `POSTGRES_PASSWORD` | Local database password | Change the placeholder; never reuse in production. |
| `POSTGRES_HOST` | Database hostname used by Django | `postgres` in Compose; `127.0.0.1` for a host-run backend. |
| `POSTGRES_PORT` | Optional host port | `5432` |
| `BACKEND_PORT` | Optional backend host port | `8000`; change it if another local service already uses that port. |
| `FRONTEND_PORT` | Optional frontend host port | `5173`; change it if another local service already uses that port. |
| `DJANGO_SECRET_KEY` | Django signing secret | Unique random local value; production value comes from secret management. |
| `DJANGO_DEBUG` | Debug mode | `true` locally, always `false` in deployed environments. |
| `DJANGO_ALLOWED_HOSTS` | Explicit host allowlist | `localhost,127.0.0.1,backend` locally. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Explicit browser origins if needed | `http://localhost:5173,http://127.0.0.1:5173` locally. |
| `SESSION_COOKIE_SECURE` | HTTPS-only session cookie | `false` only for local HTTP; `true` when deployed. |
| `CSRF_COOKIE_SECURE` | HTTPS-only CSRF cookie | `false` only for local HTTP; `true` when deployed. |
| `MEDIA_ROOT` | Validated upload storage | Container path backed by `media_data`. |
| `MAX_UPLOAD_SIZE_MB` | Upload limit reflected in API/security docs | `10` for the MVP. |
| `DEMO_PASSWORD` | Password assigned by `seed_demo` to demo accounts | Local/demo only; do not enable demo seeding in production. |
| `RUN_DEMO_SEED` | Run the idempotent demo seed from the Compose backend entrypoint | `true` for the Hackathon demo; set `false` outside demo environments. |
| `PASSWORD_RESET_THROTTLE_RATE` | Anonymous reset request/confirmation throttle | `5/hour` locally; review with the deployed cache/proxy strategy. |
| `EMAIL_BACKEND` | Django email delivery backend | Console backend for local demo only; configure an approved SMTP/API backend when deployed. |
| `EMAIL_HOST` | SMTP server hostname | `smtp.gmail.com` for authenticated Gmail SMTP submission. |
| `EMAIL_PORT` | SMTP submission port | `587` with STARTTLS. |
| `EMAIL_USE_TLS` | Upgrade the SMTP connection with STARTTLS | `true` for Gmail on port 587. |
| `EMAIL_USE_SSL` | Use implicit TLS instead of STARTTLS | `false` when `EMAIL_USE_TLS=true`; never enable both. |
| `EMAIL_HOST_USER` | SMTP login name | Full Gmail or Google Workspace email address. |
| `EMAIL_HOST_PASSWORD` | SMTP secret | Google App Password in ignored `.env`/secret storage; never the normal Google password. |
| `EMAIL_TIMEOUT_SECONDS` | SMTP connection timeout | `10` seconds locally; prevents a request from hanging indefinitely. |
| `DEFAULT_FROM_EMAIL` | Sender identity for password-reset mail | Fictional `example.test` sender locally. |
| `FRONTEND_BASE_URL` | Trusted base used to build reset links | `http://localhost:5173`; must match the actual browser origin and must not be derived from request headers. |
| `VITE_API_BASE_URL` | Browser API base | `/api/v1` (relative URL). |
| `VITE_PROXY_TARGET` | Vite's server-side proxy target | `http://backend:8000` in Compose; `http://127.0.0.1:8000` on host. |

The implementation uses the five explicit `POSTGRES_*` variables above; it does not parse `DATABASE_URL`. When `FRONTEND_PORT` is changed, update both `FRONTEND_BASE_URL` and the matching browser origins in `DJANGO_CSRF_TRUSTED_ORIGINS`.

The local console email backend prints password-reset messages and links in `docker compose logs backend`; it does not deliver real email. Do not use it as evidence of production mail delivery.

### Gmail SMTP for real delivery

Gmail SMTP is only the outbound delivery service. Users still authenticate to HoTLinE Doc with Django accounts; this configuration does not add Google OAuth or “Sign in with Google.”

Use a project-controlled test/Workspace mailbox, enable 2-Step Verification, then create a Google App Password. Google requires 2-Step Verification for App Passwords, and the option may be unavailable for managed accounts, security-key-only 2-Step Verification, or Advanced Protection. In those cases, ask the Workspace administrator to approve the [Google SMTP relay](https://support.google.com/a/answer/176600) or another transactional provider. Never enable legacy “less secure apps” and never put the mailbox's normal password in this repository. See Google's official [App Password instructions](https://support.google.com/mail/answer/185833) and [SMTP client settings](https://support.google.com/mail/answer/7104828).

Keep the console backend until both credential values have been replaced in the ignored `.env`. Then use:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=project-mailbox@gmail.com
EMAIL_HOST_PASSWORD=replace-with-16-character-google-app-password
EMAIL_TIMEOUT_SECONDS=10
DEFAULT_FROM_EMAIL=HoTLinE Doc <project-mailbox@gmail.com>
```

Do not add quotes or spaces to the App Password value. Restart the backend so Compose receives the new environment:

```bash
docker compose up -d --force-recreate backend
```

Request a password reset for a non-production account and confirm that the message arrives and its link begins with the configured `FRONTEND_BASE_URL`. This smoke test proves current SMTP delivery only; applicant activation and workflow notifications remain the planned increment in `docs/security/email-identity-notifications.md`.

## First start with Docker Compose

From the repository root:

```bash
cp .env.example .env
docker compose up --build -d
```

Then open:

- SPA: `http://localhost:5173`
- Django Admin: `http://localhost:5173/admin/` if `/admin` is also proxied, otherwise `http://localhost:8000/admin/`
- OpenAPI/schema UI, if enabled: use the backend's documented `/api/schema/` or `/api/docs/` route.

The Compose backend and frontend processes bind to `0.0.0.0` inside their containers. PostgreSQL readiness is checked with `pg_isready`; the backend entrypoint also retries migrations rather than assuming process start means database readiness.

For the local Compose demo, the backend entrypoint applies migrations automatically and runs `seed_demo` when `RUN_DEMO_SEED=true`. Both commands remain safe to run explicitly for verification. `seed_demo` is idempotent: rerunning it updates/ensures the known demo records without duplicating 19 authorities, rules, requirements, fee schedules, four workflow examples, or the 36 inactive-owner analytics fixtures used to make all areas visible in the central overview. Set `RUN_DEMO_SEED=false` anywhere demo accounts and fixtures must not be created.

### Useful lifecycle commands

```bash
docker compose ps
docker compose logs -f backend frontend
docker compose stop
docker compose start
docker compose down
```

`docker compose down` stops/removes containers and the default network but preserves named volumes unless explicitly told otherwise. Deleting volumes destroys the local database and uploads; do that only when intentionally rebuilding from empty data.

## Database migration and seed rules

After pulling a change containing migrations:

```bash
docker compose up -d postgres backend
docker compose exec backend python manage.py migrate
```

To ensure demo records:

```bash
docker compose exec backend python manage.py seed_demo
```

The seed includes only fabricated data:

- `applicant@example.test`
- `officer.patong@example.test`
- `central@example.test`
- `admin@example.test`
- all 19 required Phuket `LocalAuthority` master records;
- property types, translations, classification rules and fee schedules;
- clearly marked mock document requirements/agencies; and
- sample applications in multiple statuses.

The admin user receives Django Admin access. The public homepage still presents only applicant, local officer, and central officer options.

Never run demo seeding against production. A future production master-data import needs separate reviewed data and explicit environment protection.

## Verification commands

Run backend checks and tests:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend pytest
```

Run frontend checks and production build:

```bash
docker compose exec frontend npm test -- --run
docker compose exec frontend npm run build
```

If the repository does not define a Vitest suite yet, `npm test` may be absent; record that explicitly and still run `npm run build`. See `docs/testing/test-plan.md` for the required acceptance and permission checks.

Check migration state and seed repeatability before the demo:

```bash
docker compose exec backend python manage.py showmigrations
docker compose exec backend python manage.py seed_demo
docker compose exec backend python manage.py seed_demo
```

The second seed must complete without duplicates or integrity failures.

## Local fallback A: host backend/frontend, Compose PostgreSQL

This keeps the supported database in Docker while making Python and Node debugging local.

Start only PostgreSQL:

```bash
docker compose up -d postgres
```

Set the host-run backend's `POSTGRES_HOST=127.0.0.1` and `POSTGRES_PORT` to the exposed host port rather than using the Compose-only hostname `postgres`.

Create the Python environment and start Django:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

If the backend uses `pyproject.toml` rather than `requirements.txt`, use its documented locked installation command instead; do not maintain two drifting dependency sources.

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

For this mode, set `VITE_PROXY_TARGET=http://127.0.0.1:8000`. Browse `http://127.0.0.1:5173` consistently rather than switching between `localhost` and `127.0.0.1`, because cookies are host-scoped.

Run host-side tests:

```bash
cd backend
pytest
python manage.py check
```

```bash
cd frontend
npm test -- --run
npm run build
```

## Local fallback B: fully host-run

Use a local PostgreSQL server only when Docker is unavailable.

1. Create a dedicated local role and database named for this project; do not use a production or personal shared database.
2. Put its `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST=127.0.0.1`, and `POSTGRES_PORT` values in the uncommitted `.env`.
3. Run the same Python migration, seed, server, test, and frontend commands from fallback A.
4. Keep `VITE_API_BASE_URL=/api/v1` and proxy to the local Django server so browser session/CSRF behavior remains the same.

SQLite is available only as a dependency-light convenience for fast unit tests and local code checks (`USE_SQLITE=1`). It is not the authoritative demo or deployment database and can mask PostgreSQL constraint, transaction, and concurrency behavior that matters for document versioning, unique references, audit history, and license creation. Final verification must run against PostgreSQL.

## Uploaded media

For the MVP, validated uploads use Django's local/media storage backed by the `media_data` named volume. This choice is intentionally simple.

- Uploaded files are not placed in the frontend public directory or collected static files.
- API/media download views repeat applicant ownership or officer-authority checks; possession of a path is not authorization.
- The backend generates storage names and preserves only a sanitized original name as metadata.
- Replacements create new files/rows; previous versions are retained for authorized audit access.
- A container rebuild does not delete named-volume media.

Object storage is a later substitution behind Django's storage API. It is not required for the Hackathon and must not be added unless credentials, signed URL authorization, retention, and cleanup are deliberately designed.

## Networking and ports

Only the frontend port is required for ordinary browser use. Exposing backend `8000` and PostgreSQL `5432` to the host is a development convenience and should be bound to the local machine or disabled where not needed. PostgreSQL is never exposed publicly.

Internal communication uses Compose DNS names:

- backend to database: `postgres:5432`
- frontend proxy to backend: `backend:8000`

Browser JavaScript must not call `http://backend:8000`; that hostname exists only inside Compose. It calls relative `/api/v1/...` URLs through Vite.

## Production delta (not implemented by this MVP)

A real deployment requires a separate reviewed plan. At minimum it would replace development servers and address:

- a production WSGI/ASGI server and HTTPS reverse proxy;
- `DEBUG=false`, strict hosts/origins, secure cookies, HSTS, CSP and security-header review;
- managed secrets and credential rotation;
- managed PostgreSQL backups, restore tests, least-privilege credentials and encrypted connections;
- durable private file/object storage, malware-scanning decision, retention/deletion, and authorized downloads;
- `collectstatic` and immutable frontend asset delivery;
- migration orchestration with one migration job per release;
- centralized sanitized logs, monitoring and alerting;
- Thai privacy/legal review and official validation of classifications, document checklists, agencies, contacts, fees and license wording; and
- removal/disablement of demo accounts and `seed_demo`.

Kubernetes, Redis, async queues, microservices, event buses, and cloud object storage are not required to run the Hackathon MVP.

## Troubleshooting

### Backend cannot connect to PostgreSQL

- Confirm `docker compose ps` reports `postgres` healthy.
- Inside Compose, confirm the database hostname is `postgres`, not `localhost`.
- On a host-run backend, confirm it is `127.0.0.1` and the configured host port.
- Verify database/user/password values match without printing the password into logs or chat.

### Login works but unsafe requests fail CSRF

- Load `/api/v1/auth/me/` first and confirm a CSRF cookie is set.
- Confirm the SPA sends credentials and `X-CSRFToken`.
- Use one browser host consistently (`localhost` or `127.0.0.1`).
- Confirm requests use the Vite `/api` proxy and that trusted origins are explicit.

Do not disable CSRF or switch to permissive CORS as a workaround.

### Uploaded files disappear after rebuild

- Confirm `MEDIA_ROOT` is mounted to the `media_data` named volume.
- Confirm the upload was accepted, rather than rejected during validation.
- Do not use a container-layer path or frontend public directory as durable media storage.

### Seed data is duplicated

`seed_demo` is required to use stable codes/emails and update-or-create semantics where appropriate. Fix the seed command and its tests; do not manually edit around duplicate authorities/rules in a shared demo database.
