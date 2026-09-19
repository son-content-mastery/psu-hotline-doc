# Local officer work queue and review

## Purpose and routes

- Suggested queue route: `/officer/applications`
- Suggested review route: `/officer/applications/:id`
- Authentication: `LOCAL_OFFICER`
- Queue main task: choose the next application in the officer's LocalAuthority.
- Review main task: inspect one application's current documents and record a permitted decision.

LocalAuthority scope is enforced by the backend on list, detail, file access, review, and application-transition endpoints. Frontend routing and hidden controls are usability measures only. A local officer must never receive or view an application belonging to another LocalAuthority.

## Authentication and entry

The homepage staff CTA opens login before any officer data. After a successful Local Officer login, route to the queue. If an authenticated user lacks this role, show a localized neutral authorization message and a safe destination; never render the queue briefly before redirecting.

The header identifies the signed-in role and LocalAuthority in human-readable, localized text. Do not let the officer switch authority in the UI.

## Work queue

### Required content

Show:

- heading `คำขอในพื้นที่รับผิดชอบ` / `Applications in your area`;
- officer's LocalAuthority name;
- simple counts for items waiting for initial review and waiting after resubmission;
- one concise status filter, defaulting to actionable work;
- applications sorted by the backend's queue order, with oldest actionable item first unless the API contract specifies another explicit order.

Each row/card contains only the information needed to choose work:

- application reference number;
- property name or safe identifier;
- localized property type;
- localized current status;
- submitted/resubmitted date;
- waiting duration;
- explicit **ตรวจสอบคำขอ** / **Review application** link.

Do not show applicant personal data in the queue unless operationally necessary. Do not add advanced search, bulk decisions, productivity scoring, or cross-authority filters to the MVP.

### Layout

Desktop may use a semantic table with caption and scoped headers. On small screens, use labelled cards in the same reading order. Do not solve responsiveness by shrinking text or requiring page-level horizontal scrolling.

### Queue states

- Loading: retain heading/authority and state that applications are loading.
- Empty: state that there are no applications matching the selected status, with an option to view all permitted statuses.
- Error: show retry; do not display stale rows as current without their last-updated time.
- Session expired: stop rendering protected data, preserve only a safe return destination, and request login.

## Application review layout

Render one application in this order:

1. breadcrumb/back link to the officer queue;
2. heading with application reference number;
3. prominent current status and waiting duration;
4. property, classification, responsible LocalAuthority, and submission summary;
5. required-document completion/review summary;
6. individual current document versions;
7. status/history context relevant to the decision;
8. application-level decision area.

Applicant contact/identity details appear only when required for the review task. Use safe labels, avoid placing PII in page titles/URLs, and never expose unrelated account fields.

Classification and fee are read-only. If classification data is unresolved or inconsistent, show an explicit integrity warning and prevent approval; the officer cannot silently choose a category through the document-review UI.

## Individual document review

Every required document is reviewed individually. Each item shows:

- localized document name and requirement category;
- current version number and current-file marker;
- filename, upload date/time, and uploader role;
- current localized document status;
- prior versions/history in a collapsed section;
- secure view/download action;
- any earlier officer reason;
- review controls for the current version only.

Opening a document must retain enough context to return to the same review item. Label new-window behavior. The server authorizes every file request; a copied media URL must not bypass access control.

Allowed document outcomes:

| API decision | UI label intent | Reason rule |
| --- | --- | --- |
| `APPROVED` | เอกสารถูกต้อง / Approve document | No reason field; submit the outcome directly |
| `REVISION_REQUIRED` | ขอให้แก้ไขเอกสาร / Request document revision | Human-readable reason required |
| `REJECTED` | ปฏิเสธเอกสาร / Reject document | Human-readable reason required |

Use native radio buttons or three explicit buttons followed by a confirmation form. Selecting approval shows the confirmation action without a reason field and clears any draft reason left from another outcome. Revision and rejection reveal a required reason field; also enforce the rule server-side. The reason label explains that the applicant will see this text. Trim whitespace, retain a rejected server value for correction, and render saved reasons as escaped text.

On confirmation:

- state exactly which document/version and outcome will be recorded;
- prevent duplicate submission while pending;
- announce success and refresh authoritative status;
- keep the officer near the reviewed item;
- show a retryable error without clearing the typed reason;
- handle a stale-version conflict by showing the new current version and requiring a fresh review decision.

An outcome applies to one immutable version. A replacement upload becomes a new version requiring its own review; earlier approval/revision data remains in history.

## Application-level decisions

The backend supplies allowed transitions. Vue displays only allowed actions and cannot set arbitrary status values.

### Request revision

Available when one or more current documents require revision and the workflow permits it. Show affected document count/list and their reasons. Application-level reason is required if the API calls for an overall explanation. Confirmation moves through backend domain logic to `REVISION_REQUIRED` and creates status history/audit records.

### Approve

Available only when:

- every required current document is present and approved;
- classification is resolved;
- the application is in an approvable status;
- the backend returns the transition as allowed.

Before confirming, summarize that approval will finalize the application and generate a licence/reference. After success, show the issued reference or link when returned. Never fabricate fee, expiry, or licence number in Vue.

### Reject

Available only when the backend permits it. A clear, human-readable reason is mandatory and the confirmation states that it will be visible to the applicant. Treat rejection as terminal for the MVP unless backend rules explicitly say otherwise.

Use a confirmation dialog or confirmation section for application-level decisions because they change workflow state. The default focus is safe; destructive rejection must not be the preselected/default action.

## History and audit feedback

Show relevant chronological status/document history in plain language so the officer can understand resubmissions. Do not expose raw AuditLog internals. After a transition, display a timestamp returned by the server; never send or accept a client-generated audit timestamp.

UI success text must say what changed, for example “ขอให้ผู้ยื่นแก้ไขเอกสาร 1 รายการแล้ว,” rather than merely “Success.”

The summary includes the server-provided application status history and human-readable reasons before the document list. If a document review or application decision loses a concurrency race, the page reloads the latest allowed actions and versions while preserving any typed reason or note for the officer to reconsider; it never silently retries a stale decision.

## Permission and integrity failures

- `403`/`404` for a detail uses a neutral localized message and a link back to the permitted queue; never reveal the other authority or applicant.
- If the officer's LocalAuthority assignment is missing, show a configuration error and no applications.
- If the record changes during review, block the stale decision, fetch current state, and explain what changed.
- If a document file cannot be scanned/validated or loaded, do not allow that failure to be mistaken for approval.
- If an API sends an unknown status/transition, show a safe unavailable state and no decision controls.

## Accessibility

- Tables use captions, header scopes, and text status labels.
- Each review action includes the document name/version in its accessible name.
- Outcome controls form a labelled group; reason fields are associated with the selected outcome and their errors.
- Confirmation dialogs follow keyboard focus management; an inline confirmation section is preferred when simpler.
- Success/error changes are announced once and focus moves to useful feedback.
- Status, priority, and waiting duration never rely on color alone.
- File history and document details use native disclosure buttons with exposed expanded state.

## Acceptance criteria

1. A Local Officer sees only applications returned for their assigned LocalAuthority.
2. Direct navigation and file requests for another LocalAuthority fail without data leakage.
3. Queue defaults to actionable work and remains usable as a table on desktop and labelled cards on mobile.
4. Officer reviews each current document version as approved, revision required, or rejected.
5. Approval does not show or send a reason; revision and rejection cannot be submitted without a human-readable reason on both client and server.
6. A new uploaded version is visibly distinct and requires a new review; old review history remains.
7. Approval is unavailable until all required current documents and application conditions pass authoritative checks.
8. All application transitions are backend-controlled and successful decisions create visible history/audit feedback.
9. Raw codes never appear, and unknown/stale states fail safely.
10. Queue, document access, review, confirmation, errors, and returning to context are keyboard accessible.
