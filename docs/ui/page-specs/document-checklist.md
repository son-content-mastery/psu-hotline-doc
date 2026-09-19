# Dynamic document checklist and uploads

## Purpose and route

- Suggested public route: `/classification/requirements`
- Suggested authenticated route: `/applications/:id/documents`
- Authentication: public for viewing requirements; required to save a draft, upload, replace, or submit.
- Main task: understand and complete the documents required for this classified property.

The list is generated from database relationships for the evaluated property type. Vue must not contain document arrays, issuing-agency lists, LocalAuthority lists, or rules that decide which document is required.

## Preconditions

The page requires a supported evaluated pathway: Type 1, Type 2, or `NON_HOTEL_NOTIFICATION` for a `NOT_HOTEL` result. If classification is missing, stale, unresolved (`REQUIRES_LICENSE_REVIEW`), or out of scope, do not guess a checklist. Return the applicant to the relevant result with a localized explanation.

Because the seeded checklist is demo data and has not been established as legally complete, show a visible notice near the heading:

> รายการเอกสารนี้เป็นข้อมูลตัวอย่างสำหรับการสาธิต ต้องตรวจสอบกับหน่วยงานที่รับผิดชอบก่อนใช้งานจริง

Provide the equivalent English UI string. Do not phrase the demo checklist as official or exhaustive.

## Public checklist anatomy

Before login, show:

1. heading `รายการเอกสารที่ต้องเตรียม` / `Documents to prepare`;
2. classification summary and an **แก้ไขคำตอบ** / **Edit answers** link;
3. demo/legal-completeness notice;
4. a count such as “ต้องเตรียมทั้งหมด 7 รายการ”;
5. a preparation-step overview followed by the two document-origin sections below;
6. one primary CTA `เข้าสู่ระบบเพื่อบันทึกและอัปโหลดเอกสาร` / `Sign in to save and upload`;
7. plain text explaining that classification and this checklist will be preserved after login.

The public view is useful on its own: document names, descriptions, preparation guidance, and external issuing guidance are readable without authentication. It contains no upload controls and no applicant data.

## Required sections

Requirements are first organized by their database-provided preparation step:

1. `APPLICANT` — applicant and business;
2. `PREMISES` — premises and right to use;
3. `FACILITIES` — rooms and facilities;
4. `SAFETY` — safety and compliance; and
5. `MANAGER` — hotel manager, omitted when a pathway has no manager documents.

The authenticated UI presents these as a compact non-linear step rail rather than five large repeated cards. Each step shows one numbered/check icon, a short localized title, and an exact completed/required count. Selected, completed, and incomplete states use shape, text, and color together. A user may open any step because evidence can arrive in a different order. The active step is represented in the URL query, and changing a step moves keyboard focus to its heading.

Always group requirements by their database-provided category in this order:

1. `เอกสารที่ผู้ประกอบการเตรียมเองได้` / `Documents you can prepare yourself`
2. `เอกสารที่ต้องขอจากหน่วยงานอื่น` / `Documents issued by other organizations`

If a section has no requirements, show a localized empty statement rather than hiding the category in a way that looks like a loading failure. Requirement order follows API/master-data order.

Each item displays:

- localized document name;
- short purpose or description;
- required/optional text (the MVP submission gate uses required items only);
- preparation instructions or supporting items when supplied;
- status text when viewing an authenticated application;
- one action appropriate to its current state.

Example demo types may include แบบคำขอ, หลักฐานยืนยันตัวตน, หลักฐานสิทธิ์ในอาคาร, อ.1, อ.4, อ.5, and a company registration certificate. These are rendered from API records, never duplicated as component constants.

## External-document guidance

For each document issued by another organization, show database-driven guidance in an expandable details region or a simple detail panel:

- issuing agency;
- responsible LocalAuthority, where applicable;
- contact information;
- supporting items needed to request it;
- approximate processing time;
- instructions or source note, when available.

Do not fabricate a missing field. Render “ไม่พบข้อมูล กรุณาติดต่อหน่วยงานที่รับผิดชอบ” / “Information unavailable; contact the responsible agency” when essential guidance is absent. Phone numbers and URLs use semantic links, with a visible destination. Expansion is operated by a native button and exposes its expanded state.

## Authenticated checklist anatomy

After login and draft creation, preserve the same classification and list position where practical. Add:

1. application/property identifier using mock/demo-safe data;
2. completion summary: required count, completed count, and missing/revision count in text;
3. a localized status and action for every requirement;
4. an upload or replacement flow for one evidence item at a time, allowing a multi-file bundle only where master data permits it;
5. no more than one page-level primary action at a time: next step or review before submission; previous step remains secondary.

The completion card shows exact completed/required counts, an action-required count, and a supplementary percentage progress bar. The bar uses a completion color distinct from the selected-step and primary-action colors. Each compact step shows its exact count, while an accessible label supplies the full not-started/in-progress/complete wording. A step becomes complete only from server-computed current evidence status; opening or leaving a step never changes progress.

Do not equate “uploaded” with “approved.” A file can be present while waiting for review or while a later officer review requests revision.

## Document statuses

Never expose raw codes. Required display semantics are:

| API code | Thai text intent | Applicant action |
| --- | --- | --- |
| `MISSING` | `○ ยังไม่ได้อัปโหลด` | Upload |
| `UPLOADED` | `✓ อัปโหลดแล้ว รอเจ้าหน้าที่ตรวจสอบ` | View current file; replace only when workflow permits |
| `APPROVED` | `✓ เอกสารผ่านการตรวจสอบ` | View file/version; no correction required |
| `REVISION_REQUIRED` | `! ต้องแก้ไขเอกสาร` | Read reason and upload a replacement |
| `REJECTED` | `× เอกสารถูกปฏิเสธ` | Read reason and follow the application-level guidance |

Color and symbols supplement the localized text. For revision/rejection, show the officer's human-readable reason adjacent to the status and associate it with the replacement control. Sanitize/display it as text, never as trusted HTML.

## Upload and replacement flow

Each uploadable item exposes one clearly labelled outlined control: **เลือกไฟล์และอัปโหลด** / **Choose and upload**, or **เปลี่ยนไฟล์และอัปโหลดใหม่** / **Replace and upload**. Selecting valid files starts upload immediately; there is no repeated second “upload selected files” CTA. Show next to the control:

- accepted extensions: `.pdf`, `.jpg`, `.jpeg`, `.png`;
- accepted MIME types as configured by the backend;
- maximum file size from configuration/API;
- the document name and, for replacement, the current version and officer reason.

Requirements:

- native file picker is always available; drag-and-drop is optional and never required;
- single-file items accept one file; photo/evidence-bundle items accept at most ten files, each within the configured limit;
- show selected filename and size during upload;
- perform client checks for fast feedback, but treat server MIME, extension, and size validation as authoritative;
- during upload, show textual progress and prevent duplicate activation;
- on failure, show a localized error and let the user choose the file again;
- on success, announce the new localized status and refresh completion data.

Never overwrite an earlier upload. Files selected together create one bundle version with one-based attachment positions. Replacing an item replaces the entire current bundle atomically and retains every attachment from earlier bundle versions. After success, show the new version number, filenames, uploaded time, and current state in user language. Earlier versions may be shown in a collapsed **ประวัติไฟล์** / **File history** list, clearly marked “previous,” and are never offered as the current file by mistake.

Do not rely on the browser `accept` attribute for security. Never preview executable or unvalidated content inline.

## Completeness and next action

The server determines completeness.

- If any required document is `MISSING`, show the missing count and a secondary text action that focuses the next missing document. Do not introduce another upload-styled primary button.
- If an actionable document is `REVISION_REQUIRED`, prioritize it when choosing the next-action target and state the count.
- When all required current versions are present for an initial draft, show **ตรวจสอบข้อมูลก่อนยื่นคำขอ** / **Review before submission**.
- Do not show an enabled submission action when the server says requirements are incomplete.
- A `REJECTED` application/document follows the backend-provided terminal or next-step guidance; the client must not invent a resubmission transition.

The review-before-submit screen (separate task) summarizes property information, classification, completeness, and responsible authority. Final submission is a backend action. After success, show the generated reference number and link to tracking; never construct the reference number in Vue.

## Loading, empty, and error states

- Loading: show heading/context plus text `กำลังโหลดรายการเอกสาร` and mark the list busy.
- Empty successful response: state that no configured requirements were found and prevent submission; this is a configuration issue, not proof that no documents are legally required.
- Stale classification: return to the result/re-evaluation path without discarding answers.
- Unauthorized: offer login and preserve public checklist context.
- Forbidden/not found: show a neutral message without confirming another applicant's record exists.
- API error: retain the last safe view, label it as potentially outdated, and provide retry.
- Concurrent update: refresh server state and explain that the checklist changed; never silently discard a newly selected file.

## Accessibility and mobile behavior

- Use a labelled navigation list for preparation steps, level-two headings for the active step and document-origin categories, and a semantic list for requirements.
- Each item action includes the document name in its accessible name.
- Completion is textual; a progress bar may supplement but not replace counts.
- File input label, help, selected-file details, and error are programmatically associated.
- Status updates use a polite live region; upload failure uses an alert when immediate attention is needed.
- At phone widths, cards stack in one column and metadata wraps without horizontal scrolling.
- Keep the single forward/review primary action at least 48 CSS px high; upload controls are visually distinct outlined controls.

## Acceptance criteria

1. Type 1 and Type 2 each expose 28 supplied checklist items; the non-hotel notification pathway exposes 17. All are fetched dynamically and grouped into database-provided steps plus document-origin categories.
2. Public users can read the checklist and external guidance before login.
3. Login returns the applicant to the preserved classification/checklist flow.
4. Every external document shows all available agency, authority, contact, supporting-item, and processing-time data.
5. The demo-data limitation is visible and no claim of legal completeness is made.
6. Status is always conveyed in localized text, not color alone or a raw code.
7. Only PDF/JPG/JPEG/PNG within configured limits can pass authoritative server validation.
8. Replacing a document or evidence bundle creates and displays a new version without overwriting history; multi-file photo items retain every attachment.
9. Missing required documents block the review/submission path with a clear explanation.
10. The page works by keyboard and at 320 CSS px, including compact step navigation, exact progress, immediate-on-selection upload, retry, revision reason, and version history.
