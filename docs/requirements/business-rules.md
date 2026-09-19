# Business Rules

This document is the authoritative domain behavior for the Hackathon MVP. Codes such as `TYPE_1` are stable machine values; all user-facing labels must be translated.

## 1. Classification Inputs

The classification engine accepts:

| Input | Type | Validation |
| --- | --- | --- |
| `rooms` | integer | Required; positive whole number |
| `max_guests` | integer | Required; positive whole number |
| `has_restaurant` | boolean | Required; `true` or `false`, not a truthy string |

The backend validates and evaluates inputs. Vue may mirror validation for immediate feedback but is not authoritative.

## 2. Classification Outcomes

Classification rules are ordered, active database records. Seed the following rule set and make it editable through Django Admin:

| Evaluation order | Rule code | Condition | Outcome | Type/fee consequence |
| ---: | --- | --- | --- | --- |
| 10 | `OUT_OF_SCOPE` | `rooms > 49` | Current platform does not handle this property; contact the registrar directly | No platform category or fee is asserted |
| 20 | `NOT_HOTEL` | `rooms <= 8 AND max_guests <= 30` | Hotel license not required; continue through the non-hotel accommodation notification pathway | `NON_HOTEL_NOTIFICATION`; no fee or hotel license |
| 30 | `REQUIRES_LICENSE_REVIEW` | `rooms <= 8 AND max_guests > 30` | A hotel license is required, but category confirmation is required | Property type and fee remain unset |
| 40 | `TYPE_1` | `rooms > 8 AND rooms <= 49 AND has_restaurant = false` | Accommodation Type 1 | 10,000 THB; five-year validity |
| 50 | `TYPE_2` | `rooms > 8 AND rooms <= 49 AND has_restaurant = true` | Accommodation Type 2 | 20,000 THB; five-year validity |

Evaluation must be deterministic. Reject configuration that creates indistinguishable active precedence or otherwise detect conflicting matches. The engine selects only the first valid match by explicit priority; it must not rely on database insertion order.

### The 8-room / 36-guest ambiguity

The source brief explicitly says:

- 8 rooms;
- 36 maximum guests; and
- a hotel license is required because guest capacity exceeds the exemption.

The source does **not** say whether this case is Type 1 or Type 2. Restaurant presence cannot safely resolve that omission because the supplied Type 1 and Type 2 definitions both require more than 8 rooms.

Therefore the required outcome is `REQUIRES_LICENSE_REVIEW`. This is a real classification outcome stored in the database, not a frontend special case. The UI must explain that licensing is required and additional confirmation is necessary. It must not show a Type 1/Type 2 fee, claim a type-specific document list is complete, or issue a license until an authorized, documented confirmation assigns a supported property type.

For this MVP, an unresolved application may preserve its classification and contact/responsible-authority guidance, but type-dependent submission is blocked. This avoids inventing a fee or checklist. Resolving this ambiguity for production requires an authoritative policy decision followed by a documentation, rule-data, migration/seed, and test update.

### Required classification tests

- `6 rooms / 24 guests` → `NOT_HOTEL`.
- `8 rooms / 36 guests` → `REQUIRES_LICENSE_REVIEW`.
- `20 rooms / no restaurant` → `TYPE_1`.
- `45 rooms / restaurant` → `TYPE_2`.
- `60 rooms` → `OUT_OF_SCOPE` regardless of restaurant presence.

## 3. Classification Persistence

- Anonymous wizard answers may be held temporarily in client/session state before login.
- The backend revalidates/re-evaluates answers when an authenticated application is created. A client-supplied outcome is never trusted.
- The application stores the rule used and an immutable input/result snapshot sufficient to explain the decision even if rules later change.
- Editing a classification rule affects later evaluations; it must not silently rewrite an existing submitted decision.
- Only outcomes with a confirmed supported processing type may derive a checklist. `TYPE_1` and `TYPE_2` may derive a fee and hotel license; `NON_HOTEL_NOTIFICATION` derives neither.

## 4. Property and Authority Assignment

- A property belongs to one applicant and one responsible `LocalAuthority` for the MVP.
- Phuket administrative addresses use stable province, district, and subdistrict codes imported from a pinned open-source snapshot. Applicants select a subdistrict code; the backend derives and snapshots the Thai province/district/subdistrict names and postal code instead of trusting independently typed values.
- Administrative areas and `LocalAuthority` jurisdictions are different master-data concepts. The system must not infer the responsible authority from a subdistrict unless a separately reviewed jurisdiction mapping is introduced.
- An application is routed using the property's responsible authority as recorded at creation/submission.
- Applicant ownership and responsible authority are server-assigned from authenticated/contextual records, never accepted as unrestricted client authority.
- Changing authority on an already submitted application is an administrative correction that must be audited; it is not a normal applicant edit.
- Local-officer querysets and object permissions must both enforce authority equality.

The 19 required Phuket authorities are master data, never Vue constants:

1. องค์การบริหารส่วนจังหวัดภูเก็ต
2. เทศบาลนครภูเก็ต
3. เทศบาลเมืองกะทู้
4. เทศบาลเมืองป่าตอง
5. เทศบาลตำบลกะรน
6. เทศบาลตำบลรัษฎา
7. เทศบาลตำบลราไวย์
8. เทศบาลตำบลวิชิต
9. เทศบาลตำบลฉลอง
10. เทศบาลตำบลเชิงทะเล
11. เทศบาลตำบลเทพกระษัตรี
12. เทศบาลตำบลศรีสุนทร
13. เทศบาลตำบลป่าคลอก
14. อบต.เกาะแก้ว
15. อบต.เทพกระษัตรี
16. อบต.เชิงทะเล
17. อบต.ไม้ขาว
18. อบต.สาคู
19. อบต.กมลา

Use stable unique codes in addition to official names so display text does not become an identifier.

## 5. Document Requirements

- `PropertyTypeDocumentRequirement` is the source of required document types for a confirmed property type.
- Document types distinguish operator-prepared and externally issued categories.
- External guidance comes from document/agency master data and localized instruction content.
- Checklist completeness is computed from each required type and its current `ApplicationDocument` version; it is not a mutable client-supplied percentage.
- A disabled or newly edited requirement does not silently alter a submitted application's historical checklist. Freeze the applicable requirement set by the time of submission, either with explicit application-requirement rows if implementation adds them or with an equivalent documented snapshot.
- Checklist rows are based on the document supplied for this project but remain non-authoritative; production launch is blocked on confirmation of completeness, applicability, conditional rules, and wording by the responsible agencies. Seeded people, contacts, authorities, and example records remain fictional demonstration data.
- The supplied project checklist is represented as 28 required items for hotel applications (`TYPE_1` and `TYPE_2`) and 17 required items for `NON_HOTEL_NOTIFICATION`.
- Every type/requirement relationship supplies one database-owned preparation step: `APPLICANT`, `PREMISES`, `FACILITIES`, `SAFETY`, or `MANAGER`. `ApplicationRequirement` snapshots that step with the checklist.
- The frontend may translate stable step codes and present them as a non-linear stepper, but it never assigns a document to a step itself.
- Overall and per-step progress are derived from current document bundles. Visiting a step never marks it complete.

Sample demo document types may include แบบคำขอ, หลักฐานยืนยันตัวตน, หลักฐานสิทธิ์ในอาคาร, อ.1, อ.4, อ.5, and หนังสือรับรองการจดทะเบียนนิติบุคคล.

## 6. Upload bundles and document versioning

- Allowed file families are PDF, JPEG, and PNG.
- The backend validates extension, detected/reported MIME consistency, and the configured byte limit. A filename alone never proves type.
- The storage path is generated by the backend and must not permit path traversal.
- A document type declares whether it accepts one file or a bundle of up to ten files. This supports photo evidence without requiring users to merge every image manually.
- A source instruction to prepare two paper sets does not require duplicate digital uploads. One current digital evidence item or bundle represents the requirement; official paper-copy handling remains an agency-validation item before production.
- All attachments uploaded together for one requirement receive the same `max(version) + 1` bundle version and a one-based `attachment_index` within a transaction.
- Exactly one attachment per application/document type/attachment index is current. Replacing a bundle marks every attachment in the former bundle non-current and creates a complete new current bundle atomically.
- Earlier bundles, files, and their reviews are retained; replacement never overwrites them.
- New uploads begin at `UPLOADED`. A replacement for a requested revision does not inherit `APPROVED` from an older version.
- Applicants can upload only to owned, editable applications. Officers do not upload on an applicant's behalf in the MVP.
- Each newly uploaded file may receive one version-bound advisory `DocumentPreflight`. Quality warnings do not change the document status, completeness, submission readiness, or officer decision authority.
- The quality analyzer persists only stable issue codes, analyzer version, result status, and server time. It does not persist raw OCR text, images, thumbnails, extracted identity data, or opaque confidence scores.
- S1B compares transient Thai/English OCR only against controlled document-family markers. A possible mismatch is advisory and cannot reject a document or application; ambiguous shared families such as identity cards and house registrations remain family-level results rather than invented exact classifications.

Document display states:

| State | Meaning |
| --- | --- |
| `MISSING` | No current upload exists for the required type; this may be computed rather than stored |
| `UPLOADED` | Current version awaits review or is eligible for submission |
| `APPROVED` | Officer accepted the current version |
| `REVISION_REQUIRED` | Applicant must upload a replacement; reason is required |
| `REJECTED` | Current version was rejected; reason is required |

## 7. Submission Readiness and Reference Numbers

- A draft becomes `READY_TO_SUBMIT` only when classification is a supported confirmed type, a responsible authority is assigned, required property fields are valid, and every required document has a current version in a submittable state.
- `MISSING`, `REVISION_REQUIRED`, and `REJECTED` required items block initial submission/resubmission. The implementation must document whether initial `UPLOADED` items require pre-approval; for the supplied demo, uploaded current versions are sufficient for initial submission and are then reviewed by the officer.
- Submission eligibility is rechecked on the backend inside the submission transaction.
- Accepted first submission creates a unique `HTL-YYYY-NNNNN` reference using the server year and a concurrency-safe sequence/constraint.
- Reference values are generated only by backend logic and are immutable after assignment.
- Retrying an already accepted submission is idempotent or returns a conflict; it does not create another reference or status event.

## 8. Application Status Model

Stable status codes:

- `DRAFT`
- `READY_TO_SUBMIT`
- `SUBMITTED`
- `UNDER_REVIEW`
- `REVISION_REQUIRED`
- `RESUBMITTED`
- `APPROVED`
- `REJECTED`

Allowed transitions:

| From | To | Actor/event | Conditions |
| --- | --- | --- | --- |
| `DRAFT` | `READY_TO_SUBMIT` | System readiness evaluation | All readiness rules pass |
| `READY_TO_SUBMIT` | `DRAFT` | System readiness evaluation | A required condition ceases to pass before submission |
| `READY_TO_SUBMIT` | `SUBMITTED` | Applicant submits | Ownership and completeness revalidated; reference generated |
| `SUBMITTED` | `UNDER_REVIEW` | Responsible local officer opens/starts review | Same-authority permission |
| `UNDER_REVIEW` | `REVISION_REQUIRED` | Responsible local officer | At least one actionable reason/document revision exists |
| `REVISION_REQUIRED` | `RESUBMITTED` | Applicant resubmits | Required replacements/completeness pass |
| `RESUBMITTED` | `UNDER_REVIEW` | Responsible local officer resumes review | Same-authority permission |
| `UNDER_REVIEW` | `APPROVED` | Responsible local officer | Required current documents accepted; license can be created |
| `UNDER_REVIEW` | `REJECTED` | Responsible local officer | Non-blank human-readable reason |

`APPROVED` and `REJECTED` are terminal in the MVP. Administrative reversal/appeal is out of scope. Vue never sends an arbitrary `status` patch; it invokes named actions. Invalid transitions return a conflict/validation error and create no partial history, audit, or license data.

The UI maps codes to translated human language and computes wait duration from server timestamps. It must not show enum strings as the sole label.

## 9. Reviews, History, and Audit

- A `DocumentReview` targets a specific document version, not just a document type.
- Review outcome, reason, reviewer, and server time are immutable after creation; a new review event is added if policy permits reconsideration.
- Revision and rejection reasons must be trimmed, non-empty, human-readable text.
- Every accepted application status change creates an `ApplicationStatusHistory` row with from/to status, actor, reason where applicable, and server time.
- Important actions also create an `AuditLog`, including submission, document review, revision request, resubmission, approval, rejection, and administrative routing changes.
- Audit actor comes from authentication, `created_at` from the server/database, and object identity from the operated object. Clients cannot set them.
- Domain mutation, history, audit, reference/license creation, and associated status changes are transactionally consistent.
- Audit entries are append-only through the product; no general update/delete API is exposed.

## 10. Fee history and decision-artifact issuance

- Type 1 seed fee: 10,000 THB, five-year validity.
- Type 2 seed fee: 20,000 THB, five-year validity.
- `FeeSchedule` rows use `effective_from` and nullable `effective_to`; a new fee creates a new row rather than editing historical amounts.
- Active periods for the same property type/currency must not overlap.
- The applicable schedule is selected by the documented decision date (for the MVP, approval/issue date) and must be unambiguous.
- Approval creates exactly one `License` per application, with a unique license/reference number, issue and expiry dates, confirmed property type, fee-schedule FK, and amount/currency/validity snapshot.
- Expiry is calculated by backend date logic from the preserved validity. Define leap-day behavior in tests if encountered.
- Editing a later fee schedule cannot change an issued license.
- `NON_HOTEL_NOTIFICATION` has no fee and produces a printable notification acknowledgement with an `ACK-YYYY-NNNNN` number rather than a hotel license. Its fee, validity, and expiry fields remain null.
- `REQUIRES_LICENSE_REVIEW` and `OUT_OF_SCOPE` cannot produce a decision artifact until a supported pathway is assigned.
- Approved hotel licences are eligible for configurable pre-expiry reminders (90, 30, and 7 days by default). Each licence/threshold pair is queued at most once, and a late first scan does not replay thresholds already passed.
- Renewal reminders are informational: they do not extend expiry, create a replacement licence, change application status, or apply to notification acknowledgements. Expired licences remain visible as applicant actions and require contact with the responsible authority.

## 11. Permissions

| Operation | Applicant | Local officer | Central officer | Super admin |
| --- | --- | --- | --- | --- |
| Public classification | Yes | Yes | Yes | Yes |
| Own application read/write | Own only | Read only when same authority | No individual access required for MVP | Admin as configured |
| Upload/submit/resubmit | Own only | No | No | Admin as configured |
| Document/application decision | No | Same authority only | No | Administrative only, not normal flow |
| De-identified completed-case library | No | Read province-wide structured projection | No | FAQ master data in Admin |
| Aggregate summary | No | No | Yes | Yes as configured |
| Master-data management | No | No | No | Django Admin |

All restrictions are enforced in backend querysets/object permissions/domain functions. Frontend hiding is not authorization. Prefer a not-found-style response when that avoids cross-tenant existence disclosure.

## 12. Internationalization and Fallback

- UI copy lives in `frontend/src/locales/th.json` and `en.json`.
- Translatable master data uses child translation rows with unique `(parent_id, language_code)` constraints; do not add a column per language.
- Initial locale selection supports `th` and `en`; language selectors display language names, never flags.
- Master-data lookup attempts requested locale, then Thai (`th`), then a stable code as a last-resort non-empty label. The API should make fallback behavior consistent.
- Adding `my` or `zh` later adds translation rows/files, not schema columns.

## 13. Central Aggregation

- `total_applications` counts the same authorized set as every breakdown.
- “Waiting review” covers submitted/resubmitted/under-review work according to one documented query definition; do not double-count one application in the headline total.
- “Waiting for applicant revision” counts `REVISION_REQUIRED`.
- “Approved” counts `APPROVED`.
- Breakdowns group by confirmed property type, responsible local authority, and current status/stage, including an explicit “unconfirmed” bucket where appropriate.
- Central data is read-only in the MVP and contains only fields necessary for aggregates.
- Average stage waits are derived from application creation/status-history intervals and exclude time after terminal completion.
- “Unusually old” means the current non-terminal stage has not changed for at least `CENTRAL_OVERDUE_THRESHOLD_DAYS` (seven by default). The result is an aggregate count and stage breakdown, not an individual case list.
- Monthly workload counts include only immutable document reviews and terminal approve/reject status events by local officers. Period references are salted and rotate monthly.
- If contributing officers are fewer than `ANONYMOUS_WORKLOAD_MIN_GROUP_SIZE` (minimum/default `3`), suppress all rows and the exact contributor count. Never return identity or authority fields.

## 14. Demo-data and Privacy Rules

- Seed and test data use reserved `.test` emails and obviously fictional names, phone numbers, addresses, identifiers, and files.
- Never place real identity documents or personal data in source control, fixtures, screenshots, or demo uploads.
- Demo accounts are not production credentials and must be changed/disabled outside the local Hackathon environment.

## 15. Case Library

- Only terminal `APPROVED` and `REJECTED` applications enter the derived case search pool.
- Search results are structured reference evidence, not precedent and not an automated decision.
- The public case reference is a stable salted pseudonym; no reverse lookup endpoint is provided.
- Never expose application/property IDs, applicant, property name/address, responsible authority, application reference, document names/content, or free-text reasons in the library.
- Super Admin owns active/order/content changes to bilingual FAQ master data. FAQ keywords are controlled non-empty strings and must not contain personal data.
