# HoTLinE Doc

HoTLinE Doc is a bilingual guided service for accommodation operators in Phuket. It helps an applicant check the applicable accommodation category, prepare the database-driven document checklist, submit an application or non-hotel notification, respond to corrections, and track the decision. Local officers review applications within their assigned authority, while central officers see province-level aggregates and privacy-safe structured guidance requests.

This repository contains a two-day Hackathon MVP intended for local demonstration. It is not a production deployment or validated legal guidance.

> The seeded 28-item hotel checklist and 17-item non-hotel notification checklist are based on the document supplied for this project. Classification rules, checklist applicability, authorities, contacts, fees, and official wording still require validation by the responsible government agencies before real use.

## Current MVP

- Public three-step classification with database-managed rules and an explicit `REQUIRES_LICENSE_REVIEW` outcome.
- Applicant registration, email activation, password reset, and protected login. Registration asks only for email, password, confirmation, and consent.
- Phuket province, district, subdistrict, and postal-code selection from a pinned open-source snapshot with server-side import validation; responsible authority remains a separate routing choice.
- Database-driven 28-item hotel and 17-item non-hotel document checklists, grouped into resumable preparation steps with exact progress.
- Direct upload for PDF/JPG/PNG files, multi-file evidence bundles, immutable replacement versions, and backend file validation.
- Advisory image-quality preflight for resolution, exposure, contrast, and possible blur; PDF structure is accepted with an explicit visual-check limitation.
- Local Thai/English OCR checks recognizable document families and reports match, possible mismatch, inconclusive, unavailable, or not-applicable results without storing extracted text.
- Applicant review, submission, correction, resubmission, status history, and print-friendly licence or notification acknowledgement.
- Opaque-token public licence verification with a printable QR code; the public view omits applicant identity, application reference, full address, and fee.
- Authority-scoped officer queue and document review. Approval needs no reason; correction and rejection require a reason visible to the applicant.
- Officer-only searchable library of de-identified completed cases plus bilingual database-managed review FAQs; similar cases remain advisory.
- Read-only central overview with all 19 configured Phuket authorities, accessible area detail, average stage waits, and aggregate unusually-old-work signals.
- Structured local-to-central guidance requests that expose no applicant, property, address, file, application, officer, or authority identity.
- Scheduled, verified PostgreSQL backups with retention plus bilingual maintenance notices managed in Django Admin.
- Monthly rotating pseudonymous officer workload counts with minimum-group suppression; no officer identity or authority is returned.
- Transactional activation, workflow, and configurable licence-expiry reminder email through a PostgreSQL outbox with bounded retry. Gmail SMTP is supported as delivery transport, not Google OAuth.
- Thai and English UI, backend-enforced RBAC, immutable audit records, and automated backend/frontend coverage.

## Architecture

The project is a small modular monorepo. Vue calls a versioned Django REST Framework API; Django owns authentication, authorization, classification, workflow, file validation, history, audit, and aggregate reporting. PostgreSQL is the supported demo database.

```text
Browser -> Vue 3 / Vite -> /api/v1/ -> Django / DRF -> PostgreSQL
                                             |       -> private media volume
                                             |
PostgreSQL email outbox -> email worker -> console or Gmail SMTP
```

Docker Compose runs the four development services:

| Service | Responsibility | Default host port |
| --- | --- | --- |
| `frontend` | Vue/Vite SPA and `/api`/`media` proxy | `5173` |
| `backend` | Django/DRF API, migrations, seed, Admin | `8000` |
| `postgres` | PostgreSQL 16 and persistent application data | `5432` |
| `email-worker` | Outbox polling and bounded delivery retry | None |

See the [system overview](docs/architecture/system-overview.md), [ERD](docs/database/erd.md), and [development deployment guide](docs/infra/deployment.md).

## Stack

- Frontend: Vue 3, Vite, TypeScript, Vue Router, Pinia, vue-i18n, Tailwind CSS
- Backend: Python, Django, Django REST Framework, drf-spectacular
- Data: PostgreSQL 16; SQLite is limited to dependency-light checks and unit-test convenience
- Email: Django email backend plus relational outbox/retry worker
- Tests: pytest/pytest-django, Vitest, and Playwright browser acceptance tests
- Development: Docker Compose with environment-based configuration

## Repository structure

```text
.
├── backend/             Django project, domain code, migrations, seed, and tests
├── frontend/            Vue application, unit tests, and browser tests
├── docker/              Container build and backend entrypoint
├── docs/                Project source of truth
├── AGENTS.md            Human and AI contributor rules
├── docker-compose.yml   PostgreSQL, API, email worker, and frontend services
└── .env.example         Safe local-development placeholders
```

## Local development with Docker Compose

Docker Compose is the primary and supported local workflow. It reproduces the PostgreSQL constraints, transactions, email outbox, media volume, and service boundaries used by the Hackathon demo. You do not need to install Python, Node.js, PostgreSQL, or project dependencies on the host for this path.

### Prerequisites

- Git
- Docker Desktop, or Docker Engine with the Compose v2 plugin

### First start

From the repository root:

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

The backend entrypoint waits for PostgreSQL, applies migrations, and runs the idempotent demo seed when `RUN_DEMO_SEED=true`. The email worker starts only after the backend is healthy.

Open:

- Web app: `http://localhost:5173`
- API documentation: `http://localhost:5173/api/schema/swagger-ui/`
- Django Admin: `http://localhost:5173/admin/`

The browser should normally use the frontend URL; Vite proxies `/api` and protected media requests to Django. If a default host port is busy, change `POSTGRES_PORT`, `BACKEND_PORT`, or `FRONTEND_PORT` in the uncommitted `.env`. When changing the frontend port, also update `FRONTEND_BASE_URL` and `DJANGO_CSRF_TRUSTED_ORIGINS` so activation/reset links and CSRF origins remain correct.

### Daily commands

```bash
docker compose ps
docker compose logs -f backend email-worker frontend
docker compose stop
docker compose start
docker compose down
```

`docker compose down` removes containers and the Compose network but preserves the PostgreSQL and media named volumes. Do not delete volumes unless the local demo data and uploads are intentionally disposable.

Run migrations or restore the known demo records explicitly when needed:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

## Environment and email

Keep `.env` local and never commit it. `.env.example` contains safe placeholders and uses Django's console email backend by default, so no real message is delivered. Inspect local email output with:

```bash
docker compose logs backend email-worker
```

Real Gmail delivery requires a project-controlled Gmail/Workspace address, 2-Step Verification, a Google App Password, matching `DEFAULT_FROM_EMAIL`, and the SMTP backend settings documented in [Development Deployment](docs/infra/deployment.md). Keep `EMAIL_SUPPRESSED_DOMAINS=example.test,example.com,example.org` so seeded/demo recipients never reach SMTP.

The outbox worker is safe to run locally, but do not use real personal addresses for automated suites. Activation and workflow links use the configured trusted `FRONTEND_BASE_URL`.

## Tests and checks

Run the main verification commands in the existing Compose services:

```bash
docker compose exec -T backend pytest -q
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py makemigrations --check --dry-run
docker compose exec -T frontend npm run test:run
docker compose exec -T frontend npm run build
```

These backend tests use Django's in-memory email backend and do not deliver real email.

Create or verify a backup manually (the `backup-worker` also runs on the configured interval):

```bash
docker compose exec -T backend python manage.py create_database_backup
docker compose exec -T backend python manage.py verify_database_backup /app/backups/<file>.dump
```

The serial Playwright acceptance suite runs against a disposable seeded environment. It requires the frontend browser-test dependencies and local Google Chrome:

```bash
npm --prefix frontend install
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run test:e2e
```

Set `PLAYWRIGHT_BASE_URL` to the actual local frontend URL. The suite creates and completes an application; never point it at production or a database containing non-demo work. It reads the demo password from `E2E_DEMO_PASSWORD`, with `DemoPass123!` available only as the local default.

## Optional host-run fallback

If Docker is unavailable, use the host-run instructions in [Development Deployment](docs/infra/deployment.md). The supported fallback still uses PostgreSQL, either from the Compose `postgres` service or a dedicated local instance, and requires Python 3.11+, Node.js 20+, npm, and the repository dependency files.

`USE_SQLITE=1` is intentionally limited to fast unit tests and local code checks. It is not the authoritative demo database and can mask PostgreSQL-specific constraint, transaction, and concurrency behavior. Do not use SQLite for final workflow verification.

## Demo accounts

`seed_demo` creates these fictional, email-verified accounts. The shared local password comes from `DEMO_PASSWORD` and defaults to `DemoPass123!` only for local development.

| Role | Email |
| --- | --- |
| Applicant | `applicant@example.test` |
| Patong local officer | `officer.patong@example.test` |
| Central officer | `central@example.test` |
| Super admin | `admin@example.test` |

Never reuse the demo password or accounts outside the local Hackathon environment.

## Important documentation

- [MVP scope](docs/requirements/mvp-scope.md)
- [Business rules](docs/requirements/business-rules.md)
- [API contract](docs/api/api-contract.md)
- [Authentication and RBAC](docs/security/auth-rbac.md)
- [Email identity and notifications](docs/security/email-identity-notifications.md)
- [UX principles](docs/ui/ux-principles.md)
- [Testing plan](docs/testing/test-plan.md)
- [Development deployment](docs/infra/deployment.md)

## Data, legal, and production disclaimer

All seeded people, properties, identifiers, contact details, uploaded files, and applications are fictional. The checked-in checklist is implemented for project review but remains non-authoritative until responsible agencies confirm its completeness, conditional rules, paper-copy requirements, and official wording.

The repository uses Django and Vite development servers, local media, seeded credentials, and demo configuration. A production deployment requires a separate security, privacy, legal, operations, storage, backup, monitoring, and official-data review.
