# Applicant application tracking

## Purpose and route

- Suggested route: `/applications/:id/tracking`
- Authentication: applicant owner only
- Main task: understand the application's current state and whether the applicant must do anything now.

The page also shows the immutable applicant/local-officer conversation for this application. Messages use role labels and server timestamps, remain readable after completion, and can be posted only while the submitted application is active. Explain that messages are evidence and cannot be edited or deleted.

The backend enforces object ownership. A frontend route guard improves navigation but is never the permission boundary.

## Required information hierarchy

Render these regions in order:

1. page heading `ติดตามคำขอ` / `Track application`;
2. application reference number, for example `HTL-2026-00001`;
3. property name/short identifier;
4. highly prominent current-status panel;
5. current responsible stage and waiting duration;
6. `ตอนนี้คุณต้องทำอะไร?` / `What do you need to do now?` action panel;
7. simple vertical timeline;
8. detailed status history;
9. printable hotel licence or non-hotel notification acknowledgement action when approved.

Do not bury the current status below history or render this as a dense applicant dashboard.

## Current-status panel

Required Thai presentation pattern:

> สถานะตอนนี้
>
> เจ้าหน้าที่กำลังตรวจสอบเอกสาร
>
> รอมาแล้ว 2 วัน

The API supplies the current code, transition timestamp, and responsible stage. Vue maps codes to localized UI text and formats duration; it does not infer a different workflow state. If the duration cannot be computed safely, show the absolute status date rather than a misleading number.

Also display one human-readable responsible-stage label, such as:

- `อยู่ที่ผู้ยื่นคำขอ` / `With applicant`
- `อยู่ระหว่างการตรวจของเจ้าหน้าที่ท้องถิ่น` / `With local officer`
- `ดำเนินการเสร็จแล้ว` / `Completed`

Do not expose internal team ids or raw role/status codes.

## Applicant-facing status mapping

Exact wording lives in locale files and may be refined for clarity, but it must preserve these meanings:

| API code | Thai label intent | Responsible stage / applicant implication |
| --- | --- | --- |
| `DRAFT` | กำลังเตรียมคำขอ | Applicant must finish information/documents |
| `READY_TO_SUBMIT` | เอกสารพร้อมยื่นคำขอ | Applicant can review and submit |
| `SUBMITTED` | ยื่นคำขอแล้ว | Local authority receives the application; no immediate action |
| `UNDER_REVIEW` | เจ้าหน้าที่กำลังตรวจสอบเอกสาร | Local officer; no action unless contacted through a new status |
| `REVISION_REQUIRED` | ต้องแก้ไขเอกสาร | Applicant action required, with count and reason |
| `RESUBMITTED` | ส่งเอกสารแก้ไขแล้ว | Local officer; wait for another review |
| `APPROVED` | คำขอได้รับอนุมัติ/รับแจ้งแล้ว | Complete; the printable artifact appropriate to the processing type is available when generated |
| `REJECTED` | คำขอไม่ได้รับอนุมัติ | Complete/terminal for MVP; display reason and official next-step guidance |

If an unknown code is received, show a localized “status unavailable” message, preserve the reference number, and offer refresh/contact guidance. Never display the code.

## Action panel

Place this immediately after current status.

When no applicant action is needed:

> ตอนนี้คุณต้องทำอะไร?
>
> ✓ ยังไม่ต้องดำเนินการ

Include a short explanation that the page can be revisited for updates. Do not add a disabled button simply to fill space.

When revision is required:

> ตอนนี้คุณต้องทำอะไร?
>
> มีเอกสารที่ต้องแก้ไข 1 รายการ

Primary CTA:

> แก้ไขเอกสาร

Show each affected document and the officer's human-readable reason. The CTA opens the checklist focused on the first actionable item. After a replacement is uploaded, the backend controls whether/when the application becomes `RESUBMITTED`; Vue must not arbitrarily mutate status.

Other status actions:

- `DRAFT`: **เตรียมเอกสารต่อ** / **Continue preparing**.
- `READY_TO_SUBMIT`: **ตรวจสอบและยื่นคำขอ** / **Review and submit**.
- `APPROVED` hotel type: **เปิดใบอนุญาต/เลขอ้างอิงสำหรับพิมพ์** / **Open printable licence/reference**.
- `APPROVED` non-hotel notification: **เปิดหนังสือรับแจ้งสำหรับพิมพ์** / **Open printable notification acknowledgement**.
- `REJECTED`: show the required reason and backend-provided guidance; no unsupported resubmit action.

## Vertical timeline

Use a simple ordered list. The primary three-stage presentation is:

> ✓ ยื่นคำขอแล้ว  
> │  
> ● เจ้าหน้าที่กำลังตรวจสอบ  
> │  
> ○ ผลการพิจารณา

Text and state are authoritative; lines, dots, checkmarks, and color are supplemental. Mark the current item visibly and programmatically. Completed items include dates. Future items say they have not started rather than presenting fake dates.

`REVISION_REQUIRED` and `RESUBMITTED` appear as nested or additional chronological events between review and outcome. They never erase the original submission/review history. `REJECTED` and `APPROVED` replace the generic outcome label with the actual result.

## Detailed history

Below the summary timeline, show an ordered history with:

- localized event label;
- event date/time;
- actor category in safe human terms (for example “เจ้าหน้าที่ท้องถิ่น”), when appropriate;
- human-readable reason for revision/rejection;
- affected document name when applicable.

History comes from immutable status/audit data. Never accept or display a client-created timestamp as authoritative. Escape user/officer-provided reasons as text. Do not expose officer email, internal database ids, audit internals, or unrelated applicant details.

## Waiting duration

“Waiting” starts at the backend-provided time the application entered its current actionable stage, not at initial draft creation. Update the visible relative value when the page loads and as the local day boundary changes; the backend timestamp remains authoritative.

- Under one full day may be shown as “less than 1 day” rather than `0 days` if locale copy supports it.
- Show absolute date/time in history and optionally next to the relative duration.
- For terminal statuses, replace active waiting language with the completed/decision date.
- Never show service-level promises or predicted completion dates unless the backend supplies an approved policy.

## Decision-artifact state

For `APPROVED`, request the decision-artifact resource. While it is being generated or temporarily unavailable, keep the approved status visible and state that the printable record is not ready yet; do not downgrade the application or fabricate a number.

For hotel types, the printable view uses the backend-issued licence number, issue/expiry dates, property type, and fee snapshot. For `NON_HOTEL_NOTIFICATION`, it instead identifies itself as a notification acknowledgement, uses the `ACK-` number, and omits fee and expiry. Both open as print-friendly HTML. Label new-window behavior if used.

## Loading, empty, and error states

- Loading retains the page heading and states that the latest status is being loaded.
- Refresh failure keeps the last successfully loaded status visibly marked with its retrieval time and provides retry; never present stale data as current without warning.
- No application/forbidden returns the same neutral localized page so the UI does not reveal another person's record.
- No history is treated as an integrity/configuration issue and offers contact/retry; do not invent timeline events.
- If a just-submitted application has no reference yet, show the confirmed submission response state and retry retrieval; never generate a client reference.

## Accessibility and mobile behavior

- Current status is a heading/text block announced after a successful refresh.
- Timeline is an ordered list; current step uses `aria-current="step"` or equivalent.
- Decorative connectors/icons are hidden from assistive technology.
- Revision count and required action are written in text and pluralized by locale.
- At 320 CSS px, every region stacks in one column and reasons wrap without clipping.
- Reference numbers are selectable text, not images; a copy action must have an accessible name and success announcement.

## Acceptance criteria

1. Owner sees reference number, obvious current status, responsible stage, waiting duration, timeline, history, and required action.
2. `UNDER_REVIEW` produces the exact intent “เจ้าหน้าที่กำลังตรวจสอบเอกสาร” and “ยังไม่ต้องดำเนินการ.”
3. `REVISION_REQUIRED` shows the number of documents, each reason, and a working **แก้ไขเอกสาร** action.
4. Timeline is vertical, textual, chronological, and preserves revision/resubmission history.
5. No raw workflow code appears in Thai, English, unknown-status, or error states.
6. Waiting duration is based on authoritative current-stage time and terminal states show decision/completion time instead.
7. Approved applications provide the correct backend-generated printable artifact—hotel licence or notification acknowledgement—when available.
8. Another applicant's application cannot be read, and the UI does not confirm its existence.
9. Color is never the sole status signal; keyboard, screen reader, zoom, and phone layouts remain usable.
