# Anti-overengineering Guardrails

## Decision

HoTLinE Doc is a two-day Hackathon MVP implemented as a straightforward modular monolith. The architecture should be easy to run, inspect, test, and explain during a live demonstration. Every abstraction or dependency must solve a current documented problem.

## Intentionally Not Used

For the Hackathon MVP we intentionally do **not** use:

- microservices;
- event buses;
- CQRS;
- repository/service layers everywhere;
- Kubernetes;
- Redis unless a concrete requirement appears;
- external queue/broker infrastructure;
- complex domain frameworks;
- premature caching; or
- frontend design-system packages.

We also avoid GraphQL, a separate identity service, workflow engines, generic rules-language interpreters, cloud storage, a custom Super Admin frontend, sophisticated PDF generation, and a data warehouse unless the accepted MVP scope changes.

## Preferred Building Blocks

Prefer:

- Django models with database constraints;
- small domain/service functions where business logic deserves extraction;
- DRF serializers, viewsets, and APIViews as appropriate;
- PostgreSQL;
- Django Admin for master data;
- Django's storage interface with local media for the demo;
- Vue composables only when logic is reused;
- straightforward, focused Vue components;
- Pinia only for state that genuinely crosses views/authentication; and
- semantic HTML and modest Tailwind utilities rather than a component suite.

“Simple” does not mean putting all logic in views. Extract a named function when an operation has a transaction boundary, a status transition, multiple invariants, or reuse. Do not wrap routine ORM calls merely to satisfy a pattern.

## Concrete Decisions

| Need | MVP decision | Reconsider only when |
| --- | --- | --- |
| Deployment | One frontend, one Django process, one PostgreSQL database | Independent scaling/deployment is measured and necessary |
| Business rules | Database records plus small explicit evaluators | Rules become numerous/author-authored enough to justify a safe DSL |
| Workflow | Central transition map and named backend actions | The workflow grows into many parallel/long-running branches |
| Audit | Append-only relational rows written in the same transaction | Cross-system audit ingestion becomes a real requirement |
| Files | Django local/media storage abstraction | A production environment requires durable object storage |
| Document preflight | Synchronous Pillow plus local Tesseract/Poppler with one-page/timeout bounds; stable advisory codes only | Measured upload latency needs independent scaling or a reviewed external OCR provider |
| Background work | Database email outbox plus one polling Django worker for approved transactional email; otherwise synchronous requests | Another measured operation needs durable retry or independent scaling |
| Caching | No application cache | Profiling identifies a stable expensive read and invalidation is defined |
| Administration | Django Admin | Non-technical external administrators need a dedicated experience |
| UI components | Semantic local components | Repeated patterns prove a small shared system is valuable |
| Reporting | ORM aggregates, counters, simple tables/bars | Volume/latency or analytical requirements exceed transactional queries |
| Authentication | Standard Django demo auth | ThaiID integration requirements and credentials are available |

## Dependency Gate

Before adding a dependency, answer all of these in the change description:

1. Which current Must Have requirement does it satisfy?
2. Why are platform/framework capabilities insufficient?
3. What setup, security, maintenance, and demo-failure risk does it add?
4. Can it be removed or replaced without changing domain data?
5. Is its license and version compatible with the repository?

If there is no concrete current need, do not add it. `drf-spectacular` is acceptable for OpenAPI because it directly documents the REST contract and remains a small, conventional integration.

## Abstraction Gate

Extract a reusable abstraction when at least one is true:

- the same non-trivial behavior already exists in two places;
- a domain invariant needs one authoritative implementation;
- an operation needs a clear transaction boundary;
- security-sensitive behavior benefits from a named, testable boundary; or
- external infrastructure already in scope needs a narrow adapter.

Do not extract based on a hypothetical second implementation. Prefer duplication of a few obvious presentation lines over a generic component with many flags.

## Examples

Good MVP choices:

- `evaluate_classification(inputs)` reads active ordered rules and returns one result.
- `transition_application(application, action, actor, reason=None)` checks the central map and writes status history/audit atomically.
- A DRF queryset method scopes applications to owner or officer authority.
- A small `DocumentStatusBadge` renders translated text plus a non-color cue in several views.
- One database aggregation query supplies the central summary.

Avoid:

- a generic policy engine for five classification outcomes;
- a command bus and event handlers for a synchronous status update;
- repository interfaces wrapping Django ORM for every model;
- a universal form/schema renderer for three wizard questions;
- a global component library before repeated UI patterns exist;
- Redis to cache a 19-row authority list; or
- an async job just to create a short reference string.

## Scope and Performance Discipline

- Complete the required applicant happy path before optional features.
- Fix demonstrated bottlenecks; do not design for unspecified national scale.
- Use `select_related`, `prefetch_related`, pagination, and indexes based on real query paths before introducing caches.
- Keep central reporting to counters and grouped queries.
- Do not add OCR, AI extraction, notifications, chat, QR verification, or analytics infrastructure as “foundations.” A short documented seam is sufficient.

## Reconsideration Record

If a guardrail must change:

1. write the concrete requirement and evidence;
2. compare the smallest viable alternatives;
3. document operational and migration impact;
4. update this document and `system-overview.md` in the same change; and
5. add tests that justify the new complexity.

The approved email-activation/workflow-notification increment requires delivery only after a committed workflow action and bounded retry when Gmail is unavailable. A relational `EmailOutbox` plus a polling management-command worker was selected over Redis/Celery or a hosted queue: it reuses PostgreSQL, adds no dependency, preserves idempotency, and can be replaced without changing application workflow data. Tests cover commit scoping, duplicate keys, recipient boundaries, retries, and redacted failures.

The approved S1A increment uses Pillow already required for upload verification. It runs one bounded, synchronous advisory analysis before storage and persists only a one-to-one result with stable issue codes.

The separately approved S1B increment uses distro-packaged Tesseract (`tha+eng`) and Poppler rather than a cloud OCR API, new queue, or stored extraction corpus. This adds image size/build-time cost but no Python service dependency, credentials, network calls, or new process. Scanned PDFs are limited to page one and every subprocess has a timeout. Raw OCR output is transient; only controlled family/status metadata joins the existing `DocumentPreflight`. If measured upload latency becomes unacceptable, move this exact analyzer boundary behind the existing relational-job pattern before considering more infrastructure.

Hackathon urgency is not by itself a reason to add infrastructure; it is usually a reason to choose the simplest reliable path.
