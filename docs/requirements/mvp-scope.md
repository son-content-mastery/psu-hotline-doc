# MVP Scope

## Purpose

HoTLinE Doc (ระบบยื่นขอใบอนุญาตประกอบธุรกิจโรงแรมและที่พักแรมแบบออนไลน์) is a guided licensing service for accommodation operators in Phuket. It is not merely an online form. It helps a person understand whether a hotel license is required, identify the applicable category when the supplied rules permit it, prepare the right documents, submit an application to the responsible local authority, respond to corrections, and follow the decision.

This is a two-day Hackathon MVP. Its success criterion is one reliable, understandable end-to-end journey, not production completeness or visual sophistication.

## Outcome and Priority

The MVP must demonstrate:

1. an applicant receives value before signing in;
2. classification and document requirements come from database-managed rules and master data;
3. an authenticated applicant can prepare and submit a complete application;
4. the correct local officer can review it and request a versioned correction;
5. the applicant can see and satisfy that request;
6. approval creates either a printable hotel license with a historical fee snapshot or a non-hotel notification acknowledgement; and
7. province-level totals reflect the result without giving central officers decision authority.

When time is constrained, prioritize correct user flow, end-to-end operation, database/API/permission correctness, simple UX, accessibility, internationalization, and visual polish—in that order.

## In-scope Roles

| Role | MVP responsibility | Scope boundary |
| --- | --- | --- |
| `APPLICANT` | Classify, manage an owned property/application, upload, submit, correct documents, track, print an approved license/reference | May access only owned properties and applications |
| `LOCAL_OFFICER` | Inspect assigned applications and documents; approve, request revision, or reject with a reason | May access only applications in the officer's `LocalAuthority` |
| `CENTRAL_OFFICER` | View province-wide aggregate counts and breakdowns | Cannot decide or mutate individual applications in the MVP |
| `SUPER_ADMIN` | Manage users and master data through Django Admin | Not displayed as a public-homepage role |

## Must-have Capabilities

### M1 — Demo Authentication and RBAC

- Use standard Django authentication and secure password hashing for demo accounts.
- Applicants classify before authentication. Existing classification progress survives the authentication boundary.
- Officers and central officers authenticate before seeing protected pages.
- Keep the authentication boundary replaceable so ThaiID can be integrated later; real ThaiID is not part of the MVP.
- Seed `applicant@example.test`, `officer.patong@example.test`, `central@example.test`, and `admin@example.test` with documented demo-only credentials.
- Enforce owner, local-authority, central-summary, and admin permissions on the backend.
- Provide an accessible show/hide-password control and a generic, throttled, single-use password-reset flow. Local demo delivery may use Django's console email backend; deployed environments require a real mail provider.

### M2 — Guided Classification

- Ask one question on each of three screens: rooms, maximum guests, restaurant presence.
- Show the current step and a large progress indicator.
- Fetch questions/rules from the backend and evaluate using active database rules.
- Return one of `NOT_HOTEL`, `TYPE_1`, `TYPE_2`, `OUT_OF_SCOPE`, or `REQUIRES_LICENSE_REVIEW` as defined in `business-rules.md`.
- The `8 rooms / 36 guests` case must say a license is required but the category needs confirmation. It must not be silently forced into Type 1 or Type 2.
- Make rules editable in Django Admin.

### M3 — Dynamic Document Checklist

- Derive requirements from normalized database relationships, not Vue arrays.
- Separate documents the operator can prepare from documents issued by another organization.
- Show completeness from the current version of each required document.
- Clearly label the supplied project checklist as pending official validation; keep fictional seeded contacts and example records visibly marked as demo data.
- Implement the supplied checklist as 28 items for hotel applications and 17 items for non-hotel accommodation notifications.
- Group each checklist into database-driven applicant, premises, facilities, safety, and—where applicable—manager steps.
- Show exact overall and per-step counts in a non-linear stepper; users may prepare documents in any order and resume at the next incomplete item.

### M4 — External-document Guidance

For externally issued items, show database-managed issuing agency, applicable responsible authority, contact details, required supporting items, and approximate processing time. Missing guidance must be shown as unavailable, never invented.

### M5 — Versioned Document Upload

- Accept only PDF, JPG/JPEG, and PNG within the configured size limit.
- Validate extension, MIME type, and file size on the backend.
- Expose `MISSING`, `UPLOADED`, `APPROVED`, `REVISION_REQUIRED`, and `REJECTED` as translated labels rather than raw codes.
- A replacement creates a new `ApplicationDocument` version and marks the prior version non-current. It never overwrites the prior file or review record.
- Photo/evidence types may accept a bundle of up to ten files. The files share one bundle version and are replaced together while older bundles remain available in history.

### M6 — Validated Submission

- Before submission, show property information, classification, requirement completeness, and responsible authority.
- Reject submission while a current required document is missing or not in a submittable state.
- Generate a unique backend-owned reference such as `HTL-2026-00001` only after an accepted submission.
- Apply the centrally defined transition and write status history plus audit data atomically.

### M7 — Human-readable Tracking

- Make current status, responsible stage, wait duration, history, and required applicant action obvious.
- Use a simple vertical timeline.
- Translate all raw status codes through `vue-i18n`; raw codes are never the only applicant-facing label.
- Show either that no action is needed or a direct correction action with the affected document count.

### M8 — Local-officer Review

- Filter and authorize every officer query by the authenticated officer's `LocalAuthority` on the backend.
- Review document versions individually with `APPROVED`, `REVISION_REQUIRED`, or `REJECTED` outcomes.
- Require a human-readable reason for revision and rejection.
- Allow only valid application transitions through backend domain logic.

### M9 — Immutable Audit Trail

- Record actor, action, object type/id, previous and next status where applicable, reason, and server-generated time for important workflow events.
- Do not expose update/delete behavior for audit entries through product APIs.
- Never accept the audit timestamp or actor identity from the client.

### M10 — Printable Electronic License/Reference

- Approval creates one unique `License` linked to its application.
- Preserve issue/expiry dates, confirmed property type, source fee schedule, and fee amount/currency snapshot.
- Offer a simple print-friendly HTML page. Sophisticated PDF generation is not required.
- Approval of `NON_HOTEL_NOTIFICATION` creates a printable notification acknowledgement without a fee or expiry instead of representing it as a hotel license.

### M11 — Minimal Central Overview

- Show total, waiting review, waiting for applicant revision, and approved counts.
- Break down totals by property type, `LocalAuthority`, and current stage.
- Use counters, simple tables/bars, and an accessible schematic heat grid covering all configured LocalAuthorities including zero-count areas. A geographic boundary map is outside scope until official jurisdiction polygons are validated.
- Treat the central role as read-only aggregation for the MVP.

## Master and Demo Data

The seed mechanism must create:

- the four demo users;
- all 19 Phuket local authorities named in `business-rules.md`;
- property types and translations needed by classification;
- classification rules, including `REQUIRES_LICENSE_REVIEW`;
- Type 1 and Type 2 fee schedules;
- translated mock/demo document types and requirements;
- a non-hotel notification processing type with the supplied 17-item checklist;
- sample issuing agencies and guidance; and
- sample applications in multiple statuses, using fictional data only.

Seeded document types may use examples from the brief—application form, identity evidence, right-to-use-building evidence, อ.1, อ.4, อ.5, and company registration certificate—but the product and documentation must state that the production checklist needs official legal validation.

## Required Happy-path Demo

The primary demo is fixed:

1. Open HoTLinE Doc and choose the applicant role.
2. Classify `20` rooms, `40` guests, no restaurant as Type 1.
3. See the database-derived checklist and authenticate without losing progress.
4. Create the property/application, upload every required document, review, and submit.
5. Receive an `HTL-2026-xxxxx` reference and see “under review” tracking.
6. Sign in as the officer for that application's local authority.
7. Request a revision on one document with a reason.
8. Return as the applicant, see one required action, and upload a new document version.
9. Review again as the officer and approve.
10. See approved tracking and open the printable license/reference.
11. Verify that the central overview totals changed.

The demo is successful only if applicant ownership, officer authority scoping, status history, audit entries, version preservation, and the license fee snapshot are also correct.

## Minimum Acceptance Checks

- `6 rooms / 24 guests` → `NOT_HOTEL` with the non-hotel notification checklist and no hotel fee.
- `8 rooms / 36 guests` → `REQUIRES_LICENSE_REVIEW`, with no invented type.
- `20 rooms / no restaurant` → `TYPE_1`.
- `45 rooms / restaurant` → `TYPE_2`.
- `60 rooms` → `OUT_OF_SCOPE`.
- Incomplete applications cannot submit; complete applications can.
- Applicants cannot read another applicant's application.
- Local officers cannot read or mutate another authority's application.
- Invalid status transitions fail without partial history/audit changes.
- Replacement uploads retain prior versions.
- Revision writes status history and audit entries.
- Approval creates exactly one appropriate decision artifact—hotel license or notification acknowledgement—and the expected aggregate change.
- Master-data translation falls back safely if the requested language is absent.

## Explicitly Out of MVP

Do not implement these until the complete Must Have flow is working:

- full OCR or advanced AI document understanding;
- historical case search;
- advanced analytics or officer productivity reports;
- backup-management UI;
- discussion/chat;
- service-provider marketplace;
- public QR license verification;
- real ThaiID integration;
- cloud/object storage;
- sophisticated PDF generation;
- complete English legal content; or
- Myanmar and Chinese translations.

Future compatibility means keeping clean interfaces and normalized translations—not implementing unused systems now.

## Known MVP Limitations

- Classification and fees reflect only the supplied Hackathon rules, not a comprehensive legal determination.
- `REQUIRES_LICENSE_REVIEW` deliberately remains unresolved because the source brief does not define a category for low-room/high-guest properties.
- The demo checklist is not legally authoritative.
- Local media storage is suitable for a local demo, not a production records system.
- Authentication uses service accounts with verified email for new applicants, not verified citizen identity. Seeded staff/demo accounts remain for the Hackathon environment.
- Central reporting is operational summary data, not a full analytics platform.

## Implemented Extension: Email Activation and Notifications

The bounded authentication extension adds applicant registration, email activation through a link delivered by Gmail SMTP, and a small set of transactional workflow notifications. Gmail is an email transport, not Google OAuth or a replacement for Django authentication. Privileged roles remain administrator-managed and every existing owner/authority boundary still applies.

The model/API/UI, redacted outbox/retry delivery handling, localized templates, and automated acceptance checks are implemented as specified in `docs/security/email-identity-notifications.md`. Password reset uses the same SMTP configuration and remains limited to active, verified accounts.

## Scope-change Rule

A feature enters the MVP only if it is required to complete or protect the happy path, a Must Have acceptance check, or a documented security/accessibility constraint. Otherwise record it as a follow-up rather than expanding the implementation during the Hackathon.
