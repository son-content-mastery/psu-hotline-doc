# HoTLinE Doc

HoTLinE Doc is a bilingual, guided service for checking accommodation classification, preparing required documents, submitting either a hotel-licence application or a non-hotel accommodation notification, and tracking its review in Phuket. This repository contains the two-day Hackathon MVP.

> The seeded 28-item hotel checklist and 17-item non-hotel notification checklist are based on the document supplied for this project. Classification rules, checklist applicability, authorities, contacts, fees, and official wording still require validation by the responsible government agencies before production use.

The applicant checklist is split into five compact preparation steps with exact overall/per-step progress. Choosing a valid file starts one upload directly, avoiding repeated upload CTAs; photo-based requirements can accept a current bundle of up to ten files, and replacement bundles retain their version history. The central demo includes aggregate fixtures across all 19 configured authorities, with clickable area summaries that never expose individual applications. Approval creates either a fee-bearing hotel licence or a fee-free `ACK-` notification acknowledgement, according to the processing type.

## Architecture

The project is a small monorepo: a Vue 3 single-page application calls a versioned Django REST Framework API, which persists relational data in PostgreSQL. Django owns authentication, authorization, classification, workflow transitions, file validation, history, and audit records. Uploaded demo files use local media storage. Django Admin manages users and changeable master data.

```text
Browser -> Vue 3 SPA -> /api/v1/ REST API -> Django ORM -> PostgreSQL
                                     |
                                     +-> local media storage (MVP)
```

See [system overview](docs/architecture/system-overview.md) and [ERD](docs/database/erd.md).

## Stack

- Frontend: Vue 3, Vite, TypeScript, Vue Router, Pinia, vue-i18n, Tailwind CSS
- Backend: Python, Django, Django REST Framework, drf-spectacular
- Data: PostgreSQL in Docker; SQLite is supported for fast local tests
- Tests: pytest/pytest-django and Vitest
- Development: Docker Compose and environment-based configuration

## Repository structure

```text
.
├── backend/             Django project and domain apps
├── frontend/            Vue application
├── docs/                Project source of truth
├── AGENTS.md            Instructions for coding agents
├── docker-compose.yml   Local PostgreSQL, API, and web services
└── .env.example         Safe development defaults
```

## Prerequisites

Choose either Docker Desktop with Docker Compose, or install Python 3.11+, Node.js 20+, npm, and PostgreSQL 15+ locally.

## Quick start with Docker

```bash
cp .env.example .env
docker compose up --build
```

The backend container applies migrations and seeds idempotent demo data before starting. Open the web app at `http://localhost:5173`, API schema at `http://localhost:8000/api/schema/swagger-ui/`, and Django Admin at `http://localhost:8000/admin/`.

If a default host port is already in use, set `POSTGRES_PORT`, `BACKEND_PORT`, or `FRONTEND_PORT` in `.env`; internal Compose service ports do not change.

Local password-reset email uses Django's console backend and appears in `docker compose logs backend`. If `FRONTEND_PORT` changes, also set `FRONTEND_BASE_URL` to the browser URL so reset links are correct. Gmail SMTP/App Password setup and the planned activation/notification boundary are documented in `docs/infra/deployment.md` and `docs/security/email-identity-notifications.md`; Gmail is an outbound provider here, not Google OAuth.

To run migration or seed commands again:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

## Local development

Copy configuration and install dependencies:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
npm --prefix frontend install
```

Use SQLite for a dependency-light local run, or set the PostgreSQL variables from `.env`:

```bash
export USE_SQLITE=1
python backend/manage.py migrate
python backend/manage.py seed_demo
python backend/manage.py runserver
```

In a second terminal:

```bash
npm --prefix frontend run dev
```

## Tests and checks

```bash
USE_SQLITE=1 .venv/bin/pytest backend
USE_SQLITE=1 .venv/bin/python backend/manage.py check
npm --prefix frontend run test:run
npm --prefix frontend run build
```

## Demo accounts

The `seed_demo` command creates these fictional accounts. The shared demo password is configured by `DEMO_PASSWORD` and defaults to `DemoPass123!` only in local development.

| Role | Email |
|---|---|
| Applicant | `applicant@example.test` |
| Patong local officer | `officer.patong@example.test` |
| Central officer | `central@example.test` |
| Super admin | `admin@example.test` |

Never reuse the demo password or accounts in production.

## Important documentation

- [MVP scope](docs/requirements/mvp-scope.md)
- [Business rules](docs/requirements/business-rules.md)
- [API contract](docs/api/api-contract.md)
- [Authentication and RBAC](docs/security/auth-rbac.md)
- [UX principles](docs/ui/ux-principles.md)
- [Testing plan](docs/testing/test-plan.md)
- [Deployment](docs/infra/deployment.md)

## Data and legal disclaimer

All people, properties, identifiers, phone numbers, uploaded files, and applications in the seed data are fictional. The supplied checklist is implemented for project review but remains labelled non-authoritative until the responsible agencies confirm its completeness, conditional rules, paper-copy requirements, and official wording.
