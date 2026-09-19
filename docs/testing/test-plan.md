# Test Plan

This plan defines the minimum evidence required for the HoTLinE Doc Hackathon MVP. It is intentionally centered on business rules, permissions, workflow integrity, and the end-to-end demo rather than broad UI snapshot coverage.

## Test approach

- Backend domain rules and API permissions are automated with `pytest` and `pytest-django`.
- Important frontend state/translation behavior may use Vitest; the complete role flows also receive a manual browser smoke test.
- Tests use a temporary PostgreSQL test database where available so constraints and transaction behavior match the supported database.
- Seeded names, emails, phone numbers, addresses, and files are synthetic. No real personal data is permitted in fixtures, screenshots, or failure output.
- Freeze or assert around time where waiting duration, effective fee dates, expiry, or year-based reference numbers matter.
- Each test creates its own data or uses deterministic factories. A test must not depend on ordering or mutations from a previous case.

The documented commands are:

```bash
docker compose exec backend pytest
docker compose exec backend python manage.py check
docker compose exec frontend npm test -- --run
docker compose exec frontend npm run build
```

If frontend tests are not present, record that fact and run the production build plus the manual smoke tests. Do not report a command as passing unless it was actually run.

## Required human-readable cases

### TC-01 — Exempt small accommodation

**Layer:** Backend unit/API; public classification UI smoke test.

**Given** active classification rules and answers of 6 rooms, 24 maximum guests, with either restaurant answer  
**When** the visitor evaluates the wizard  
**Then** the outcome is `NOT_HOTEL`, `requires_license` is false, the supported processing type is `NON_HOTEL_NOTIFICATION`, the 17-item notification checklist is available, and no hotel fee is invented.

### TC-02 — Eight rooms but capacity exceeds exemption

**Layer:** Backend unit/API; public classification UI smoke test.

**Given** answers of 8 rooms and 36 maximum guests  
**When** classification is evaluated  
**Then** the result says a hotel license is required, uses `REQUIRES_LICENSE_REVIEW`, leaves property type and fee unresolved, and tells the user that classification confirmation is needed. It must not silently choose Type 1 or Type 2.

### TC-03 — Type 1 classification

**Layer:** Backend unit/API.

**Given** 20 rooms, 40 maximum guests, and no restaurant  
**When** classification is evaluated  
**Then** the result is `TYPE_1` with the effective database fee of THB 10,000 and five-year validity. Changing the database rule/fee in the test changes the result without a frontend-code change.

### TC-04 — Type 2 classification

**Layer:** Backend unit/API.

**Given** 45 rooms and a restaurant  
**When** classification is evaluated  
**Then** the result is `TYPE_2` with the effective database fee of THB 20,000 and five-year validity.

### TC-05 — Out-of-scope accommodation

**Layer:** Backend unit/API; public classification UI smoke test.

**Given** 60 rooms  
**When** classification is evaluated  
**Then** the outcome is `OUT_OF_SCOPE`, the response recommends contacting the registrar, and application creation/submission does not pretend the MVP can process it.

### TC-06 — Anonymous progress survives authentication safely

**Layer:** Frontend integration/manual plus backend API.

**Given** an anonymous visitor has completed the three classification answers  
**When** they are asked to log in and successfully authenticate  
**Then** the answers remain available from Pinia/`sessionStorage`, application creation sends those answers, and Django evaluates current rules again. A tampered client-supplied outcome/property type/fee is ignored or rejected.

### TC-07 — Missing required documents block submission

**Layer:** Backend API.

**Given** an applicant-owned Type 1 draft with at least one required document missing  
**When** the owner calls the submit action  
**Then** the API returns `409 MISSING_REQUIRED_DOCUMENTS` with missing document type IDs; status remains unchanged; no reference, status-history row, or audit transition is created.

### TC-08 — Complete application can be submitted

**Layer:** Backend API.

**Given** all required document types have a valid current upload for an applicant-owned draft and classification is resolved  
**When** the owner confirms and submits  
**Then** submission succeeds, a unique backend-generated reference matching `HTL-<year>-<sequence>` is assigned, status becomes `SUBMITTED`, and exactly one status-history and audit entry is created. A retry does not create a second reference or duplicate transition.

### TC-09 — Applicant ownership is enforced everywhere

**Layer:** Backend permission/API.

**Given** applicants A and B and an application owned by A  
**When** B guesses the application or nested resource IDs and attempts detail, patch, requirements, history, document list/upload/download, submit, or license access  
**Then** every request returns `404 NOT_FOUND`, no data about A is returned, and no state changes.

### TC-10 — Officer cannot cross a LocalAuthority boundary

**Layer:** Backend permission/API.

**Given** a Patong officer and an application assigned to another Phuket authority  
**When** the officer searches, filters, opens, downloads a document from, reviews, requests revision for, approves, or rejects that application  
**Then** it never appears in the queue and direct requests return `404 NOT_FOUND`; no review, history, audit, status, or license row changes. A same-authority application remains accessible.

### TC-11 — Replacement creates a document version

**Layer:** Backend domain/API.

**Given** document type X has current version 1 and is open for replacement  
**When** the owner uploads a valid replacement  
**Then** a distinct version 2 bundle is created, version 2 attachments alone are current and `UPLOADED`, version 1 attachments and reviews remain unchanged and non-current, and no bytes are overwritten. A multi-file photo bundle preserves one-based attachment positions, and two concurrent replacements cannot yield duplicate current attachment positions.

### TC-12 — Upload validation rejects unsafe input

**Layer:** Backend API/security.

**Given** an uploadable applicant application  
**When** the owner sends each of: an executable renamed `.pdf`, mismatched MIME/signature, unsupported extension, malformed image/PDF, password-protected PDF, empty file, file over 10 MiB, and path-like original filename  
**Then** each invalid file is rejected with the documented `400`, `413`, or `415` error, nothing is made current or downloadable, and no server path is derived from the original name. Valid PDF, JPG/JPEG, and PNG controls succeed.

### TC-13 — Revision creates history and audit evidence

**Layer:** Backend domain/API plus applicant tracking smoke test.

**Given** a same-authority officer is reviewing an application and has marked one current document `REVISION_REQUIRED` with a reason  
**When** the officer requests application revision with a human-readable reason  
**Then** application status becomes `REVISION_REQUIRED`, the applicant action flag becomes true, and exactly one status-history plus one immutable audit row records actor, from/to status, reason, and server time. The tracking UI shows a translated message and revision CTA, not raw status alone. After the applicant uploads all requested new versions, the submit action moves the case to `RESUBMITTED`, preserves its original reference/first-submission time, records `resubmitted_at`, and creates the corresponding history/audit transition. The first new officer review then moves it to `UNDER_REVIEW`; simply opening the detail never changes status.

### TC-14 — Revision/rejection reasons are mandatory

**Layer:** Backend API.

**Given** a reviewable same-authority application/document  
**When** the officer submits document revision, document rejection, application revision, or application rejection with a missing/blank reason  
**Then** the API returns `400 REASON_REQUIRED` and creates no review, transition, history, or audit record. Approval may omit a reason.

### TC-15 — Invalid status transitions are rejected

**Layer:** Backend domain/API.

**Given** representative applications in `DRAFT`, `REVISION_REQUIRED`, `APPROVED`, and `REJECTED`  
**When** a caller attempts transitions not in the centralized transition map—for example approving a draft, resubmitting an approved case, or rejecting an approved/license-issued case  
**Then** the API returns `409 INVALID_STATUS_TRANSITION`; application, history, audit, documents, and license are unchanged. An ordinary `PATCH` containing `status` is also rejected.

### TC-16 — Approval creates one historically accurate license

**Layer:** Backend domain/API; printable page smoke test.

**Given** a same-authority officer, a reviewable application whose required current documents are all approved, and an effective fee schedule  
**When** the officer approves  
**Then** status becomes `APPROVED`; one hotel licence artifact is created with a unique number, issued/expiry dates, property type, fee schedule reference, and fee amount snapshot; history and audit are created atomically. Later editing/expiring the fee schedule does not change the license snapshot. The owner can open a usable print view; a second approval cannot create another artifact. A `NON_HOTEL_NOTIFICATION` approval instead creates one `ACK-` acknowledgement with null fee/expiry and no fee-schedule requirement.

### TC-17 — Approval fails safely when prerequisites are incomplete

**Layer:** Backend API.

**Given** an application with a missing/unapproved required document, or with no effective fee schedule  
**When** its same-authority officer tries to approve  
**Then** the API returns `409 DOCUMENTS_NOT_APPROVED` or `409 FEE_SCHEDULE_NOT_FOUND`; it creates no partial license, status, history, or audit change.

### TC-18 — Central summary aggregates correct counts

**Layer:** Backend query/API.

**Given** deterministic applications across multiple property types, authorities, and every relevant status  
**When** a central officer loads the summary  
**Then** total applications, waiting review (`SUBMITTED` + `UNDER_REVIEW` + `RESUBMITTED`), waiting for applicant revision (`REVISION_REQUIRED`), approved, and breakdowns by property type, authority, and current stage equal hand-calculated values. Empty data returns zero/empty groups. No individual applicant, address, file, or reason is returned.

### TC-19 — Central and local roles cannot exchange powers

**Layer:** Backend permission/API.

**Given** one central and one local officer  
**When** the central user attempts an officer detail/decision endpoint and the local user requests the province summary  
**Then** both receive `403 PERMISSION_DENIED` (or scoped `404` for object lookup), and no state changes. Central access remains aggregate-only.

### TC-20 — Translation fallback is safe

**Layer:** Backend API plus frontend i18n unit/smoke test.

**Given** a master entity has Thai but no requested English translation  
**When** a request uses `Accept-Language: en`  
**Then** the API returns the Thai value and `translation_fallback: true`; if Thai is also absent it returns a stable code, never `null`, an exception, or a fabricated translation. User-interface statuses are rendered through `vue-i18n` and do not show raw values such as `UNDER_REVIEW`.

### TC-21 — Session, CSRF, and role bootstrap

**Layer:** Backend security/API plus browser smoke test.

**Given** an anonymous browser  
**When** it calls `/auth/me/`, logs in, performs an unsafe request, and logs out  
**Then** `/auth/me/` provides the CSRF cookie, valid credentials rotate/create an `HttpOnly` session, correct `X-CSRFToken` succeeds, missing/wrong CSRF fails, `/auth/me/` reports the authenticated role/authority accurately, logout invalidates the session, and subsequent protected calls return `401`. Invalid login never reveals whether an email exists.

### TC-22 — Database-driven checklist and guidance

**Layer:** Backend API.

**Given** Type 1, Type 2, and non-hotel notification have normalized document requirements, including external-agency documents and database-owned preparation steps  
**When** applications request their requirements  
**Then** hotel pathways expose 28 items and non-hotel notification exposes 17; each receives only active requirements for its server-derived type, grouped into steps and operator-prepared/external sections. External guidance returns only fields available in master data—missing supporting items or processing time remain absent rather than fabricated. Editing master data changes the API result without changing Vue code, and the legal-validation disclaimer remains visible.

### TC-23 — Audit fields are server-controlled and immutable

**Layer:** Backend model/API/Admin security.

**Given** a valid transition  
**When** a client attempts to submit actor, `created_at`, from/to status, or later edit/delete the audit row  
**Then** client values are ignored/rejected; actor and time come from the authenticated request/server clock; no public write endpoint exists; routine Django Admin access treats audit/history as read-only.

### TC-24 — Password recovery is generic and single-use

**Layer:** Backend security/API plus frontend form smoke test.

**Given** one active account and one unknown email  
**When** each requests a reset  
**Then** both receive the same `202` response, only the active account receives a configured email, the token can set a validator-compliant password exactly once, reuse/expiry fails safely, and requests are CSRF-protected and throttled. The login UI supports show/hide password without disabling paste or autocomplete.

### TC-25 — Dashboard grouping and area overview remain aggregate and accessible

**Layer:** Backend API, Vitest, and browser smoke test.

**Given** applicant applications in actionable, in-progress, and completed states and central aggregates across configured authorities  
**When** the applicant or central officer opens their overview  
**Then** applicant identity/action grouping, property type, responsible authority, and document progress are readable; all 19 configured authority rows are returned including zero counts when present; the heat grid shows exact text values and a non-geographic disclaimer; activating a tile opens only aggregate totals/type/stage detail with keyboard focus moved to its heading; and neither view relies on color alone or exposes another applicant's data.

### TC-26 — Step progress and multi-file evidence bundles

**Layer:** Backend API, Vitest, and browser smoke test.

**Given** an application checklist whose requirements span multiple database-owned steps and a photo type allowing multiple files  
**When** the applicant opens compact steps in a non-sequential order and selects two valid photographs together  
**Then** overall and per-step completed/required/action counts equal server state; opening a step does not change completion; file selection starts one bundle upload without a repeated upload-selected CTA; both files share one bundle version with distinct attachment indexes; replacing the item retains the prior bundle; and the UI announces progress with text in addition to the progress bar.

## Primary end-to-end demo acceptance

Run this in a fresh seeded environment after automated tests:

1. Open `/`, choose the applicant role, and complete classification with 20 rooms, 40 guests, no restaurant.
2. Confirm Type 1 and a database-generated checklist are shown before login.
3. Log in as `applicant@example.test`; confirm the classification answers are preserved.
4. Create the application, choose the seeded Patong authority, upload valid mock files for every requirement, review, and submit.
5. Record the generated `HTL-2026-xxxxx` reference and confirm tracking shows a translated officer-review state and waiting duration.
6. Log in as `officer.patong@example.test`; confirm the application appears and another authority's fixture does not.
7. Mark one document for revision with a reason and request application revision.
8. Return as the applicant; confirm one actionable revision is obvious, then upload a new version.
9. Resubmit, review the new current version as the officer, approve all required documents, and approve the application.
10. Return as the applicant; confirm approved tracking and open the print-friendly license/reference.
11. Log in as `central@example.test`; confirm summary totals and breakdowns reflect the transition, with no decision controls or individual personal data.

Capture failures and exact commands/output in the final verification notes. Do not mark this acceptance case complete based only on unit tests.

## Exit criteria

The Hackathon MVP is ready to demo only when:

- TC-01 through TC-26 pass at their stated layers or any explicit, justified manual-only exceptions are recorded;
- the full end-to-end demo acceptance succeeds on a clean seeded database;
- Django system checks, backend tests, and the frontend production build pass;
- permission failures have been exercised with at least two applicants and two different local authorities;
- migrations and `seed_demo` work from a clean PostgreSQL database; and
- this plan and the API/security documents still describe the implemented behavior.
