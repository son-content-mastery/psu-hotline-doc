# Authentication and RBAC

This document defines the MVP security boundary for HoTLinE Doc. Backend checks are authoritative. Frontend route guards and hidden buttons are usability features only and must never be treated as authorization.

## Security objectives

The MVP must:

1. prevent one applicant from reading or changing another applicant's data;
2. prevent a local officer from discovering or accessing applications outside their `LocalAuthority`;
3. limit central officers to province-wide aggregates, with no individual decisions;
4. restrict master-data and user administration to Django Admin;
5. validate untrusted uploads before making them available;
6. make workflow decisions and important changes traceable through server-created, immutable audit entries; and
7. keep credentials, session identifiers, file paths, and personal data out of client storage and logs.

The Hackathon uses fabricated people, contact details, addresses, and files only. Demo data must be visibly recognizable as mock data and must use reserved addresses such as `example.test`.

## Identity and session strategy

The MVP uses Django's authentication system, secure password hashing, and server-side sessions. It does not implement JWTs and never stores a password, access token, or session identifier in browser storage.

### Browser session flow

1. The SPA calls `GET /api/v1/auth/me/` during bootstrap. The response describes the current user or anonymous state and sets/refreshes Django's CSRF cookie.
2. Login posts email and password to `/api/v1/auth/login/` with the CSRF header.
3. A successful login rotates the session key and sets an `HttpOnly` session cookie.
4. Every mutating request includes credentials and sends the CSRF cookie value in `X-CSRFToken`.
5. Logout flushes the server-side session and expires its cookie.

Password recovery is a separate anonymous, CSRF-protected flow. The request endpoint always returns the same accepted response, sends mail only for an active account with a usable password, and is throttled. Reset links are built from configured `FRONTEND_BASE_URL`, use Django's signed single-use token mechanism, expire according to Django settings, and become invalid after the password changes. New passwords pass the configured Django validators. The application never returns a reset token in an API response.

Applicant self-registration and email activation are implemented as anonymous, CSRF-protected, throttled API actions backed by signed single-use tokens and a database email outbox. Gmail SMTP delivers the activation link, but Gmail is not the identity provider and Google OAuth is not implied. Verification is separate from administrative account disablement; self-registration can create only `APPLICANT`, while officer, central, and admin accounts remain administrator-managed. The complete lifecycle, notification matrix, privacy rules, and acceptance checks are in `email-identity-notifications.md`.

Cookie policy:

| Cookie | `HttpOnly` | `SameSite` | `Secure` | Notes |
| --- | --- | --- | --- | --- |
| Session | Yes | `Lax` | Yes outside local HTTP | Never readable by Vue. |
| CSRF | No | `Lax` | Yes outside local HTTP | Read only to populate `X-CSRFToken`; it is not an authentication token. |

Sessions have a finite, environment-configured lifetime. The initial production-like default is an eight-hour absolute lifetime. Login and privilege changes rotate or invalidate affected sessions. Local development may disable `Secure` cookies because it uses HTTP, but deployed environments may not.

The Vite development server proxies `/api` and `/media` to Django. This keeps browser traffic same-origin and avoids broad CORS rules. If a later deployment intentionally uses separate origins, allowed origins and CSRF trusted origins must be explicit; wildcard credentialed CORS is forbidden.

### Authentication protections

- Login errors do not reveal whether an email exists.
- Login is throttled by account identifier and source address. Throttle values are configuration, not frontend behavior.
- Disabled users cannot authenticate.
- Demo passwords are provided through setup/seed configuration and are never production secrets.
- Passwords are hashed by Django's configured password hashers and are never logged.
- Password-reset requests do not reveal whether an email exists. Reset tokens are single-use, time-limited, absent from API/log payloads, and sent only through the configured email backend.
- `DEBUG` is false and HTTPS is required outside local/demo development.
- `GET` endpoints do not change workflow state. State-changing operations use `POST` or `PATCH` plus CSRF protection.

## Classification before authentication

Anonymous visitors may fetch classification questions and evaluate answers. Classification progress is kept in Pinia and browser `sessionStorage` so the login redirect does not lose the three answers. It contains no trusted authorization decision and should contain no personal data.

After login, application creation sends the original answers. Django evaluates active database rules again and records the server result. The backend ignores any client-supplied property-type code, fee, outcome, or rules version as an authority. This prevents modified browser state from selecting a cheaper or incorrect category.

## Roles

The application role is a controlled server-side value:

- `APPLICANT`
- `LOCAL_OFFICER`
- `CENTRAL_OFFICER`
- `SUPER_ADMIN`

`is_staff`/`is_superuser` and the application role are not mass-assignable through public APIs. `SUPER_ADMIN` operates through Django Admin; it is not shown as a public homepage role and does not require a parallel SPA dashboard.

### Permission matrix

| Capability | Applicant | Local officer | Central officer | Super admin |
| --- | --- | --- | --- | --- |
| Public classification/master data | Yes | Yes | Yes | Yes |
| Create application | Own | No | No | Admin maintenance only |
| Read/update applicant application | Own only | No through applicant API | No | Django Admin |
| Upload/replace documents | Own only, permitted state | No | No | Django Admin |
| Review document | No | Same authority only | No | Django Admin |
| Advance/reject application | No | Same authority only, valid transition | No | Django Admin |
| Read individual license | Own | Same authority when operationally needed | No | Django Admin |
| Province aggregate summary | No | No | Yes, aggregates only | Django Admin |
| Manage users/master data/rules/fees | No | No | No | Django Admin |

Permission checks require both the correct role and the correct object scope. A role alone never grants access to every object of that type.

## Object-level scoping

### Applicant ownership

All applicant application querysets begin with an ownership constraint equivalent to `owner=request.user`. The same constraint must be repeated for:

- application detail and update;
- requirements and history;
- current and historical document metadata;
- document upload/replacement;
- protected file download; and
- license lookup/printing data.

Nested URLs do not prove ownership. Both the parent application and nested document/license relationship are checked. An applicant who guesses another ID receives `404 NOT_FOUND`, not `403`, so the response does not confirm that the object exists.

### Local-authority boundary

A `LOCAL_OFFICER` account must have exactly one active `LocalAuthority` assignment for the MVP. Every officer queryset begins with the equivalent of:

```text
application.responsible_authority == request.user.local_authority
```

This restriction applies to queue counts, searches, detail views, documents, downloads, reviews, application actions, exports if later added, and any indirect lookup. Request parameters may narrow this queryset but never broaden it. An unassigned officer is denied access; the code must not interpret a missing authority as "all authorities."

`Application.responsible_authority` is the workflow scope used by every officer query. While an application is still an applicant-owned draft, an explicit property-authority edit updates that snapshot together with the property. Once submitted, the responsible authority stays stable; changing it then requires an explicit future administrative workflow with an audit entry.

### Central boundary

`CENTRAL_OFFICER` can call only aggregate reporting endpoints in the MVP. Summary queries group across Phuket without returning applicant identity, exact address, files, free-text review reasons, or application detail links. Central officers cannot reuse local-officer endpoints and cannot approve, reject, or request revision.

### Admin boundary

Django Admin requires `is_staff`, relevant Django model permissions, and the `SUPER_ADMIN` role used by this project. Production-like deployments should use individual admin accounts, not a shared credential. Audit and status-history records are read-only in Admin; corrections are represented by a new event rather than rewriting history. Admin changes to email, role, authority, active state, or verification state create immutable audit events and invalidate that user's active server-side sessions. Changing an email clears verification and queues a new activation message.

### Enforcement pattern

Use both:

1. a scope-filtered queryset before lookup; and
2. an object-level permission check before an action.

Serializers expose explicit field allowlists. They do not accept ownership, role, authority assignment, status, document version, `is_current`, reviewer, audit actor/timestamp, reference number, fee snapshot, or license number from a client.

## Workflow integrity

Allowed application transitions are defined once in backend domain logic. Vue cannot set `status` through an ordinary patch.

```text
DRAFT -> READY_TO_SUBMIT -> SUBMITTED -> UNDER_REVIEW
UNDER_REVIEW -> APPROVED | REJECTED | REVISION_REQUIRED
REVISION_REQUIRED -> RESUBMITTED -> UNDER_REVIEW
```

The backend may combine `READY_TO_SUBMIT` with submit validation in one transaction, but it must preserve the same business rule: submission is impossible while a required document is missing.

Each successful transition creates an `ApplicationStatusHistory` row and an `AuditLog` row in the same database transaction. The server supplies `actor` and `created_at`. Revision and rejection require a non-blank, human-readable reason. Failed or concurrent transitions create no partial history. Approval atomically creates one license and snapshots the effective fee.

Audit records have no public create, update, or delete endpoint. Database and Admin permissions must prevent routine edits. Logs record identifiers and action context, not uploaded file contents, passwords, cookies, or unnecessary personal data.

## Upload security

Uploads are untrusted, even when submitted by an authenticated applicant.

### MVP allowlist

| Type | Extensions | Declared/detected MIME |
| --- | --- | --- |
| PDF | `.pdf` | `application/pdf` |
| JPEG | `.jpg`, `.jpeg` | `image/jpeg` |
| PNG | `.png` | `image/png` |

Maximum size is 10 MiB per file. It is enforced during request handling before expensive parsing and again by serializer/domain validation where practical.

### Validation sequence

1. Reject a missing or empty file.
2. Enforce the 10 MiB limit without loading an unbounded file into memory.
3. Normalize and validate the final extension against the allowlist.
4. Compare the client-declared MIME type with a server-detected signature; do not trust `Content-Type` alone.
5. Parse/verify images with a maintained image library and reject truncated, malformed, or decompression-bomb images. Apply a conservative pixel-count limit.
6. Validate the PDF signature and structure with a maintained parser. Reject malformed or password-protected PDFs because officers must be able to inspect them.
7. Generate a storage name (for example, a UUID); never use the submitted filename as a filesystem path. Store a sanitized original filename only as display metadata.
8. Create the database record only after validation. If storage or database work fails, clean up the incomplete artifact.

File content must never be executed or interpreted as HTML. Storage is under a dedicated media root, separate from static assets and application source. Direct media URLs are not authorization: downloads pass through an authenticated, scope-checked view (or, after a future storage migration, a short-lived signed URL issued only after that check). Responses use an allowlisted `Content-Type`, safe `Content-Disposition`, and `X-Content-Type-Options: nosniff`.

### Versioning

A replacement creates a new `ApplicationDocument` version. Within one transaction the backend locks the current set, calculates the next version, marks the prior row non-current, and marks the new row current. Prior files and reviews remain available to authorized users for audit. Concurrent uploads must not produce duplicate version numbers or two current rows.

Document review targets a specific version. An officer cannot review a superseded version as current. A revision upload returns to `UPLOADED`; it does not inherit approval from the earlier file.

### Explicit MVP limitation

Antivirus/content-disarm scanning is not implemented for the Hackathon unless a concrete scanner is added and verified. The validation and storage boundary must leave one backend hook for future scanning before a file becomes downloadable. Production launch requires a threat review and a decision on malware scanning, retention, quarantine, and deletion.

### Advisory quality preflight (S1A)

After authoritative type/safety validation, the upload service performs a bounded synchronous quality check with the already-decoded bytes. Images are checked for low resolution, extreme exposure, low contrast, and a conservative possible-blur signal. Valid PDFs receive an explicit limited result because this batch does not render pages or run OCR. Results are version-bound advisory metadata: they never make a file authentic, approve it, or block submission. No pixels, thumbnails, extracted text, identity values, or analyzer metrics are copied into PostgreSQL or logs. Disabling `DOCUMENT_QUALITY_PREFLIGHT_ENABLED` stores no result for later uploads.

### Bounded document-family OCR (S1B)

The local backend image includes Tesseract with Thai/English language data and Poppler. Text PDFs use their embedded text first; scanned PDFs render only page one, and images use the validated upload bytes through a private temporary file. Every subprocess uses an argument list without a shell, suppresses document-derived stderr/stdout from logs, has a configurable 1–60 second timeout, and cleans temporary files automatically. OCR text exists only in process memory long enough to compare controlled family markers; it is never stored, returned, placed in audit/email data, or logged. The persisted result is only status, a controlled family code, analyzer version, and server time. Engine failure is `UNAVAILABLE`, weak evidence is `INCONCLUSIVE`, and visual/photo evidence is `NOT_APPLICABLE`; all fail open to human review.

## Data, logs, and secrets

- Configuration and secrets come from environment variables; `.env` is ignored and `.env.example` contains placeholders only.
- Database credentials, `SECRET_KEY`, provider credentials, and production origins are never committed.
- API errors do not include stack traces or raw exceptions outside local debug mode.
- Access logs avoid request bodies for authentication and upload endpoints and do not log cookies or CSRF headers.
- Free-text reasons may contain personal information; show them only to the owner, same-authority officers, and authorized admins.
- Local media and PostgreSQL use persistent development volumes. Access to the Docker host still protects those files; this is not a public cloud security design.
- Database backups, retention/deletion policy, encryption-at-rest requirements, and breach processes must be decided before production. They are not silently claimed by the MVP.

## Future ThaiID integration point

Real ThaiID integration is deliberately outside the MVP critical path. It should replace or supplement *authentication* without rewriting application ownership, RBAC, classification, or workflow code.

### Proposed boundary

Keep Django `User` as the internal principal and introduce a small external-identity mapping only when integration begins:

```text
ExternalIdentity
- user_id
- provider_code        # e.g. THAI_ID
- provider_subject     # stable provider subject, not a display identifier
- created_at
- last_authenticated_at
UNIQUE(provider_code, provider_subject)
```

An authentication adapter/backend owns provider redirects, callback verification, claim mapping, and account linking. Views and domain services continue to use `request.user`; they do not depend on ThaiID SDK objects or claims.

## Public Licence Verification

Public verification is the only anonymous route that reads an issued decision artifact. Lookup uses a random UUID token, never the sequential licence number. The response is allow-listed to artifact status/number, property display name/type, issuing authority, and issue/expiry dates. It must not expose applicant identity, application reference, exact address, fee, uploaded files, reasons, or audit history. The QR endpoint encodes only the frontend verification URL and returns a generated SVG; it never accepts arbitrary QR content.

### Expected protocol safeguards

The final choice depends on official ThaiID documentation and approval available at integration time. If the supported flow is OpenID Connect/OAuth 2.0, use Authorization Code flow with PKCE and:

- exact redirect-URI allowlisting;
- cryptographically random, one-time `state` and `nonce` bound to the initiating browser session;
- issuer, audience, signature, expiry, and nonce validation using current provider metadata/keys;
- server-side code exchange; provider tokens never enter browser storage;
- minimal scopes and minimal claim retention;
- explicit behavior for cancellation, unavailable provider, duplicate subject, and account-link conflict; and
- secret/key rotation and provider outage handling.

Never infer `LOCAL_OFFICER`, `CENTRAL_OFFICER`, `SUPER_ADMIN`, `is_staff`, or a `LocalAuthority` assignment from an identity-provider claim without a separately controlled administrative provisioning rule. External authentication proves identity; local RBAC grants application authority.

### Migration approach

1. Retain password login for approved demo/test accounts while developing the adapter.
2. Add the provider callback behind a feature flag and a separate URL namespace.
3. Link a verified provider subject to one internal user through an explicit, audited process; do not match silently on display name or an unverified email.
4. Run ownership and RBAC tests unchanged against both authentication methods.
5. Decide whether applicants become ThaiID-only only after accessibility, support, privacy, consent, logout, and recovery flows are validated.

No mock ThaiID button should imply a real government integration or certification.

## Required security tests

At minimum, automated tests must prove:

- applicant A receives `404` for applicant B's application, document metadata, file, history, and license;
- a Patong officer receives `404` for another authority's application and document;
- a central officer cannot retrieve or mutate individual applications;
- ordinary patches cannot set protected fields or status;
- missing/incorrect CSRF fails on authenticated unsafe requests;
- invalid workflow transitions leave status, history, audit, and license unchanged;
- revision/rejection without a reason fails;
- invalid, oversized, mismatched, malformed, and path-like upload names are rejected;
- replacement creates a new version while the previous version remains unchanged;
- approval creates one license and one audit/history transition under concurrent/retry conditions; and
- audit timestamps and actors always come from the server.

See `docs/testing/test-plan.md` for human-readable acceptance cases.
