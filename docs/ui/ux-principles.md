# UI and UX principles

## Purpose

HoTLinE Doc is a guided public service, not a generic dashboard or an online form dump. The interface must help accommodation operators understand whether a licence is required, what category may apply, what evidence is needed, and what happens next. Correct flow and plain language take priority over visual polish.

This document is the UI source of truth. Page-specific behavior is defined in [`page-specs/`](page-specs/), and language and accessibility requirements are defined in [`i18n-accessibility.md`](i18n-accessibility.md).

## Core rule: one screen, one main task

Every screen must make these three answers obvious without relying on prior knowledge:

1. Where am I?
2. What should I do next?
3. What happens after I do it?

Each screen has one visually dominant action. Secondary actions such as **Back**, **Save and continue later**, or **Sign out** remain available but must not compete with the primary action. A list screen may contain repeated row actions, but it still has only one page-level purpose.

Examples:

- A classification step asks one question only.
- A document page helps the applicant prepare or upload documents; it does not also ask unrelated property questions.
- A tracking page explains the current state and presents an action only when the applicant must act.
- An officer review view focuses on one application and one review decision at a time.

## Audience and design priorities

Applicant-facing screens are designed first for:

- elderly users;
- people with limited digital literacy;
- a mobile phone held in one hand;
- users unfamiliar with licensing terminology;
- intermittent mistakes, backtracking, and interrupted sessions.

Use plain, respectful sentences and familiar terms. Explain necessary official terminology at first use. Do not make the user interpret internal workflow codes, database terminology, icons, or color.

Officer and central screens may be denser than applicant screens, but must still use semantic HTML, clear focus states, readable text, and human-readable statuses.

## Information architecture

### Public and applicant flow

The primary flow is linear:

`Homepage → Classification questions → Classification result → Document requirements → Sign in or create account → Verify email when newly registered → Upload documents → Review before submission → Submission success → Tracking`

Classification and the initial document requirements are available before authentication. Authentication must preserve the completed classification result and return the user to the same flow. Do not require an applicant account merely to learn whether a licence may be needed.

Registration is applicant-only and asks only for email, password, password confirmation, and explicit consent. Notification language follows the current supported interface language, while the server assigns a neutral localized display name; legal or operator identity is collected later only where the application requires it. The success state directs the applicant to email without revealing whether an address already existed. Activation opens on a dedicated page with clear loading, success, invalid/expired, and resend states. Officer and central accounts are never self-registered.

Applicant pages use a single-column layout, no sidebar, and no complex dashboard. After authentication, an applicant may access their own applications, but navigation must stay small and task-oriented.

### Staff flow

- Local officer: `Login → Work queue → Application review → Decision`
- Central officer: `Login → Province overview`
- Super admin: Django Admin only; never show a Super Admin option on the public homepage.

The backend is authoritative for ownership, role, and LocalAuthority access. Hiding a control in Vue is not authorization.

## Page shell

Use a restrained, consistent shell:

- header with the `HoTLinE Doc` wordmark/name;
- text language selector labelled `ไทย` and `English` (never flags);
- page title describing the current task;
- optional step or location cue below the title;
- main content;
- one prominent primary action near the end of the content;
- a small service/help footer only if useful contact information is available.

Authenticated screens may add the signed-in role/name and a clear sign-out action. Do not turn the applicant shell into a sidebar dashboard.

The language selector changes language in place and must not discard entered values, uploads, wizard progress, filters, or the current route.

## Visual hierarchy and sizing

Applicant screens should approximately use:

| Element | Target size |
| --- | --- |
| Page title | 28–36 px |
| Important question/result | 26–32 px |
| Body and form text | 18–20 px |
| Helper text | At least 16 px where practical |
| Touch target | At least 48 × 48 CSS px |

Use generous line height and spacing. Keep readable content to roughly 40–45rem on wide screens; extra viewport width should become whitespace rather than stretched text. Never reduce essential copy below 16 px to make it fit.

Font, spacing, border, and status colors may later be refined using design references, but changes must preserve the hierarchy and accessibility rules here.

## Controls and interaction

- Prefer native links, buttons, inputs, radio buttons, checkboxes, headings, lists, and tables.
- Use a link for navigation and a button for an action.
- Every form control has a visible label; placeholder text is never the only label.
- Put units and examples next to the field without embedding them as ambiguous placeholder-only text.
- Numeric questions use a numeric-friendly input while still accepting keyboard entry and paste.
- Yes/no questions use an explicit labelled choice; do not make users infer an icon or swipe gesture.
- Preserve valid answers when the user moves back in a wizard.
- Disable a primary action only when its unavailable state is also explained in text. Otherwise, allow activation and show a clear validation message.
- Prevent accidental double submission while a request is in progress, and announce completion or failure.
- Never add auto-advancing questions, carousels, gesture-only controls, or important information that appears only on hover.

Primary action labels describe the result, for example **ถัดไป**, **ดูรายการเอกสาร**, **ยื่นคำขอ**, or **แก้ไขเอกสาร**. Avoid vague labels such as “OK” and “Submit” when a more specific translation is possible.

## Forms, validation, and recovery

Validate close to the relevant control, then repeat a concise error summary at the top after an unsuccessful submit when more than one error exists. Each message must say what happened and how to fix it.

Requirements:

- retain all valid values after an error;
- move focus to the error summary or first invalid field after submit;
- mark required fields in text, not only with an asterisk;
- show accepted file types and maximum size before upload;
- distinguish a client-side format check from the authoritative server result;
- provide a retry action for network failures without duplicating a completed request;
- warn before leaving only when unsaved work would actually be lost.

For Phuket property addresses, keep the street/building line as free text, fix the province to Phuket, offer cascading district and subdistrict selects from the backend catalog, and display the derived postal code read-only. Keep the responsible local-authority selector separate and explain that it controls routing.

Do not blame the user. Prefer “กรอกจำนวนห้องเป็นตัวเลขจำนวนเต็ม” over “Invalid input.”

## Status communication

No meaning may be communicated by color alone. Every status has:

1. a localized text label;
2. an optional icon or shape with redundant meaning;
3. a short explanation or next action when needed.

Examples include `✓ อัปโหลดแล้ว`, `! ต้องแก้ไขเอกสาร`, and `○ ยังไม่ได้อัปโหลด`. Icons are decorative when adjacent text already carries the meaning. Raw values such as `UNDER_REVIEW` and `REVISION_REQUIRED` must never appear in user-facing output.

Waiting, loading, empty, success, and error states need descriptive text. Skeletons or spinners may supplement that text but cannot replace it.

## Responsive behavior

Design mobile-first from 320 CSS px without horizontal page scrolling. On small screens:

- stack fields, cards, buttons, and summary blocks vertically;
- allow the primary button to span the content width;
- keep actions near the item they affect;
- turn staff tables into labelled cards if a table cannot reflow without losing meaning;
- do not hide required content behind hover, truncated text, or an unlabeled icon.

At larger widths, the applicant content remains a centered single column. Staff queues and aggregate tables may use available width while retaining readable line lengths.

## Data and business-rule boundaries

Vue renders and collects information; it does not decide licensing outcomes, permissions, required documents, fees, or workflow transitions.

The API/database is the source of truth for:

- classification questions, rules, and outcomes;
- property types and translated labels;
- document types and requirements;
- issuing agencies and LocalAuthorities;
- document review and application status;
- fees and validity;
- reference/licence data.

The client may perform immediate format validation for usability but must display server validation results. Do not hardcode master-data arrays or mutable government/business rules in components or locale files.

## Privacy and safety

- Use mock identities, addresses, phone numbers, and files in the demo.
- Do not expose another applicant's application or another LocalAuthority's work, even momentarily.
- Avoid personal details in URLs, page titles, analytics labels, logs, and generic error messages.
- On a forbidden or missing record, show a neutral localized message without confirming that a protected application exists.
- Do not display uploaded documents in public pages or third-party embeds.

## Deliberate MVP constraints

The MVP does not add marketing sections, animation-heavy transitions, a design-system package, a complex applicant dashboard, chat, OCR, advanced analytics, or public licence verification. Visual refinement must not delay the complete demo path or change the documented interaction model.

## UX definition of done

A UI flow is complete only when:

- its happy path works with the API;
- loading, empty, validation, permission, and server-error states are present;
- keyboard-only operation is possible;
- mobile layout works at 320 CSS px and common phone widths;
- Thai and English UI keys exist for core MVP screens;
- no raw status or untranslated technical key is visible;
- focus is placed sensibly after navigation and errors;
- authorization is enforced by the backend;
- the page spec and implementation still agree.
