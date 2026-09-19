# User Stories

These stories translate the MVP into testable outcomes. `P0` stories protect the end-to-end demo or its security. `P1` stories complete the Must Have experience. Stories outside this file require an explicit scope decision in `mvp-scope.md`.

## Public Visitor and Applicant

### US-A01 — Choose a role (`P0`)

As a visitor, I want a simple choice between applicant, local officer, and central officer so that I know where to begin.

Acceptance criteria:

- The homepage contains exactly those three large role choices; Applicant is visually primary.
- Super Admin is not presented as a public role.
- Thai and English language controls use text, not flags.
- Each choice explains its next action in plain language.

### US-A02 — Classify before signing in (`P0`)

As an accommodation operator, I want to answer classification questions before creating a session so that I receive useful guidance without an authentication barrier.

Acceptance criteria:

- Rooms, maximum guests, and restaurant presence appear one question per screen.
- The page announces “step N of 3” and exposes progress accessibly.
- Positive whole-number validation errors are clear and preserve earlier answers.
- No login is required to obtain a classification result.
- The result is returned by backend evaluation of active database rules.

### US-A03 — Receive a safe ambiguous result (`P0`)

As an operator with 8 rooms and capacity for 36 guests, I want to know that licensing is required without being given an unsupported category.

Acceptance criteria:

- The result is `REQUIRES_LICENSE_REVIEW`.
- The UI says a hotel license is required and category confirmation is needed.
- No Type 1/Type 2 fee, type-specific checklist, or category-specific license is asserted.
- A next step points to the responsible authority or confirmation process.

### US-A04 — Understand required documents (`P0`)

As an applicant, I want a tailored checklist so that I understand what I can prepare and what I must obtain elsewhere.

Acceptance criteria:

- The checklist is generated from database requirements for the confirmed property type.
- Operator-prepared and externally issued items are separated.
- The seeded list is identified as demo guidance pending official validation.
- No checklist array is embedded in Vue components.

### US-A05 — Get external-document guidance (`P1`)

As an applicant, I want to see where and how to obtain an external document so that I do not need to call multiple offices.

Acceptance criteria:

- Available issuing agency, contact, supporting items, approximate time, and applicable local authority are shown.
- Content follows the selected locale with safe fallback.
- Unavailable values are honestly marked unavailable rather than fabricated.

### US-A06 — Authenticate without losing progress (`P0`)

As an applicant who has completed classification, I want my result and answers preserved through login so that I do not repeat work.

Acceptance criteria:

- Authentication occurs only when saving, uploading, or submitting is needed.
- Wizard answers and the server-derived result survive successful login.
- The saved application is assigned to the authenticated applicant, not a client-supplied user ID.
- Invalid or expired preserved state returns the user to a safe review step.

### US-A07 — Upload and replace a document (`P0`)

As an applicant, I want to upload an allowed document and replace it after feedback so that the full review history is preserved.

Acceptance criteria:

- PDF, JPG/JPEG, and PNG are accepted only when extension, MIME, and size validations pass.
- A first upload shows a translated `UPLOADED` state.
- A replacement increments the version and becomes current.
- The prior file and its review remain retained and non-current.
- The applicant cannot upload to another applicant's application.

### US-A08 — Submit only a complete application (`P0`)

As an applicant, I want a final review and a guarded submit action so that I know the application is ready.

Acceptance criteria:

- The review shows property, confirmed classification, required-document completeness, and responsible authority.
- The backend rejects submission if a current required item is missing or otherwise not submittable.
- Accepted submission generates one unique `HTL-YYYY-NNNNN` reference on the backend.
- Repeated requests cannot create duplicate submissions or references.
- Status history and audit data are written with the transition.

### US-A09 — Track status in plain language (`P0`)

As an applicant, I want to see where my application is and whether I need to act so that I do not need to call the authority.

Acceptance criteria:

- Current status, current responsible stage, wait duration, and history are visible.
- A vertical timeline describes submitted, review, and decision stages.
- Raw enum values are not shown as the sole user-facing text.
- The page says either “no action needed” or identifies the documents needing action and provides a direct next step.

### US-A10 — Access an approved reference (`P0`)

As an approved applicant, I want a print-friendly license/reference so that I can retain evidence of the decision.

Acceptance criteria:

- Only the owning applicant (and appropriately authorized staff) can access it.
- It shows the unique license/reference, property, issue and expiry dates, confirmed type, and preserved fee.
- Printing works from HTML without requiring a PDF generator.
- An unapproved application has no license response.

### US-A11 — Ownership isolation (`P0`)

As an applicant, I expect my property, files, and application to remain private from other applicants.

Acceptance criteria:

- List endpoints return only owned records.
- Detail, history, document, upload, submit, and license endpoints reject access to records owned by another applicant.
- The restriction is applied in backend querysets/object permissions and is covered by negative tests.

## Local Officer

### US-L01 — See the local work queue (`P0`)

As a local officer, I want to see only applications assigned to my authority so that I can process my jurisdiction without exposing another jurisdiction's data.

Acceptance criteria:

- Authentication is required before the queue is shown.
- List and detail queries are scoped to the officer's `LocalAuthority` in the backend.
- Guessing another application ID does not disclose whether its data exists.
- Useful status and waiting-time information is visible without a dense dashboard.

### US-L02 — Review a current document version (`P0`)

As a local officer, I want to approve or return the current document version so that the applicant receives specific feedback.

Acceptance criteria:

- The officer can inspect current upload metadata and prior version history.
- Allowed outcomes are `APPROVED`, `REVISION_REQUIRED`, and `REJECTED`.
- Revision and rejection require a non-blank human-readable reason.
- The review records the authenticated officer and server time.
- An officer from another authority is rejected by the backend.

### US-L03 — Request an application revision (`P0`)

As a local officer, I want to return an application with specific document reasons so that the applicant knows exactly what to fix.

Acceptance criteria:

- Only a valid `UNDER_REVIEW → REVISION_REQUIRED` transition is accepted.
- At least one actionable revision reason is available to the applicant.
- Status history and immutable audit entries are created in the same successful operation.
- The applicant's tracking page shows the correction count and action.

### US-L04 — Re-review a resubmission (`P0`)

As a local officer, I want a corrected application to return to my queue so that I can finish the decision.

Acceptance criteria:

- A correction uses a new document version.
- Applicant resubmission follows `REVISION_REQUIRED → RESUBMITTED`.
- Officer review follows `RESUBMITTED → UNDER_REVIEW`.
- Prior document/review/status history remains visible and immutable.

### US-L05 — Approve or reject with accountability (`P0`)

As a local officer, I want to issue the final decision so that the application and records stay consistent.

Acceptance criteria:

- Approval and rejection are allowed only from `UNDER_REVIEW`.
- Rejection requires a human-readable reason.
- Approval creates exactly one license with a fee-schedule reference and fee snapshot.
- The status transition, license, history, and audit data are atomic.
- Retrying approval cannot create a second license.

## Central Officer

### US-C01 — View a province summary (`P0`)

As a central officer, I want aggregate counts so that I can see workload and bottlenecks across Phuket.

Acceptance criteria:

- The summary contains total, waiting review, waiting applicant revision, and approved counts.
- It includes breakdowns by confirmed property type, local authority, and current stage.
- The response is computed from authorized province-level records.
- The UI uses simple counters and tables/bars, not a complex BI dashboard.

### US-C02 — Remain read-only (`P0`)

As a central officer, I should not make an individual decision in the MVP so that local authority responsibility is preserved.

Acceptance criteria:

- Central credentials cannot call local-officer review or decision mutations.
- The central UI exposes no approve, reject, or revision action.
- Backend permission tests cover the restriction.

## Super Admin

### US-S01 — Manage master data (`P1`)

As a super admin, I want to manage changing rules and reference data in Django Admin so that the team does not build a redundant administration frontend.

Acceptance criteria:

- Admin supports users/roles, local authorities, property types/translations, classification rules, document types/translations, requirements, issuing agencies/translations, and fee schedules.
- `REQUIRES_LICENSE_REVIEW` is visible and editable like other classification rules.
- Changeable master data is not duplicated in Vue.
- Audit/history models are read-only where practical.

### US-S02 — Seed a safe demo (`P0`)

As a demo operator, I want one repeatable seed command so that I can prepare the Hackathon environment without manual data entry.

Acceptance criteria:

- The command creates or safely reconciles the four sign-in demo accounts, one inactive analytics-fixture owner, 19 authorities, rules, types, fees, checklist data, agencies, four workflow examples, and 36 aggregate-only draft fixtures distributed across the other authorities.
- Running it again does not create uncontrolled duplicates.
- All personal details are clearly fictional.
- Sample checklist content is labeled non-authoritative.

## Cross-cutting Stories

### US-X01 — Use translated, accessible interaction (`P1`)

As a user, I want readable Thai/English screens that work with keyboard and mobile input so that the service remains usable regardless of device or confidence with technology.

Acceptance criteria:

- UI strings use `vue-i18n` keys for `th` and `en`.
- Master-data translation uses translation rows and a safe fallback.
- Controls have semantic labels, visible focus, large targets, and clear errors.
- Status is communicated with text and structure, not color alone.

### US-X02 — Preserve an audit trail (`P0`)

As an auditor, I want important workflow changes recorded immutably so that I can reconstruct who did what and when.

Acceptance criteria:

- Submission, document review, revision/resubmission, approval, and rejection record server-derived actor and time.
- Relevant entries include object identity, old/new status, and reason.
- Product APIs cannot edit/delete audit entries.
- Failed operations do not leave partial audit or status-history records.
