# Internationalization and accessibility

## Scope

The MVP supports Thai (`th`) and English (`en`) through `vue-i18n`. Thai is the fallback/default locale for the hackathon service. A user's explicit language selection is retained for later visits. The implementation must allow additional locale files such as Myanmar (`my`) and Chinese (`zh`) without changing component logic or database columns.

Core navigation, form labels, validation, status text, and the complete demo flow require both Thai and English UI strings. The MVP does not claim that every piece of legal or master-data content has an authoritative English translation; when a backend translation is unavailable, use the documented fallback and do not invent legal wording.

## Language behavior

- Display the selector as text: `ไทย` and `English`.
- Never use national flags as language selectors.
- The selector is available on public and authenticated screens in a consistent header position.
- Mark the active language in text and programmatically, for example with `aria-pressed` or the current option in a labelled native select.
- Changing language updates the current page in place. It must not reset a wizard, clear form input, discard uploads, change filters, or navigate to the homepage.
- Update the document `lang` attribute (`th` or `en`) immediately.
- Page titles, headings, validation messages, API error presentation, dates, amounts, status labels, accessible names, and live announcements all change with the locale.
- Store only the locale preference, never sensitive form data, in long-lived browser storage.

## UI string architecture

Reusable frontend logic must never contain user-facing Thai or English prose. Components call translation keys; locale JSON owns UI copy.

Use stable, domain-oriented keys grouped by feature, for example:

```text
common.actions.next
common.actions.back
home.roles.applicant.title
classification.steps.rooms.question
classification.results.type1.title
documents.status.revisionRequired
applications.status.underReview
tracking.action.noneRequired
validation.required
```

Do not use an English sentence as a key. Do not concatenate translated fragments to build a sentence because Thai and English word order differs. Use interpolation and pluralization instead:

```text
tracking.waitingDays(count)
documents.revisionCount(count)
```

All enum/code-to-label mappings live in translation files or localized backend data. The UI must have a safe localized fallback such as “ไม่สามารถแสดงสถานะได้” / “Status unavailable” and must never expose the raw code.

Development and test builds should report missing keys. Production must fall back to Thai for a missing UI key and log the missing-key defect without showing the key to the user.

## Database-driven translated content

Changeable master data does not belong in `th.json` or `en.json`. Property types, document types, issuing agencies, and similar entities use normalized translation records keyed by language code.

The API should return:

- a stable machine code/id for behavior;
- a localized display value for the requested locale;
- the effective language when fallback occurred, if the API contract supports it.

Fallback order for master data is:

1. requested locale;
2. Thai (`th`);
3. a localized generic unavailable label.

Do not fall back to an internal code as visible copy. Never add a new `name_xx` column for each language.

## Locale-aware formatting

Use `Intl`/`vue-i18n` formatters rather than manual string assembly.

- Format money with the API-provided amount and currency; do not assume every fee is THB even though seeded fees are.
- Show dates in a familiar localized form while retaining an unambiguous machine timestamp from the API.
- Use the same calendar convention consistently within a locale. If Buddhist Era display is introduced, name and test that decision explicitly; do not shift years ad hoc.
- Translate relative waiting text with plural rules. Include an absolute date nearby or in accessible text where it helps avoid ambiguity.
- Do not translate reference numbers, licence numbers, email addresses, or user-entered property names.
- Inputs submit locale-independent values (for example integers and ISO dates) to the API.

## Semantic page structure

Every page uses:

- one `<header>` for the service header;
- a skip link to the main content;
- one `<main>` landmark;
- one descriptive level-one heading;
- headings in logical order without skipping levels for visual size;
- `<nav>` only for genuine groups of navigation links;
- `<footer>` only when footer content exists.

On client-side route change, update the document title and move focus to the new page's level-one heading or main container. Do not unexpectedly move focus while the user is typing.

## Keyboard and focus

All functionality must work with keyboard alone:

- logical DOM/tab order matching the visual order;
- visible focus indicator with at least 3:1 contrast against adjacent colors;
- no positive `tabindex` and no keyboard traps;
- `Enter` activates the focused primary button; `Space` operates native buttons and radio/checkbox controls;
- dialogs, if unavoidable, receive focus, contain focus while open, close with `Escape` when safe, and return focus to the trigger;
- validation sends focus to a linked error summary or the first invalid field;
- after an upload or review action, focus moves to the resulting status message or stays at the control with a live announcement.

Cards must not rely on a click handler attached to a generic `<div>`. Put a real link or button inside.

## Forms and errors

- Associate every label and error with its control using native label relationships and `aria-describedby` where needed.
- Group related options in `<fieldset>` with `<legend>`; this is required for the restaurant yes/no question and similar choices.
- Use `inputmode="numeric"` to help phone users, but validate the actual value rather than relying on the keyboard layout.
- Communicate required status in visible text and programmatically.
- Do not remove entered values after an error.
- Error messages identify the field and the remedy.
- A multi-error summary contains links to the invalid controls.
- Do not announce validation on every keystroke. Validate on blur or attempted continuation unless immediate feedback is clearly helpful.
- Server and network failures use `role="alert"` or an assertive live region only when immediate interruption is justified.

## Wizard and progress

The classification wizard shows visible localized text such as `ขั้นตอน 1 จาก 3` / `Step 1 of 3` plus a large progress indicator. Expose progress programmatically using a labelled `<progress>` element or equivalent `role="progressbar"` values.

The progress indicator supplements the text and never becomes the only indication of location. Completed steps are not exposed as clickable navigation in the MVP; the explicit Back action preserves a simple, predictable sequence.

## Statuses, timelines, and charts

- Pair color with text and, when helpful, a symbol whose accessible meaning is not dependent on its shape alone.
- Mark the current timeline item with visible “current” wording and `aria-current="step"` or equivalent.
- Render history as an ordered list with a readable timestamp and explanation, not as decorative connected dots only.
- Decorative timeline lines and icons are hidden from assistive technology.
- Central overview bars always include the category and numeric value in text. The tables remain the authoritative readable representation.
- Never announce decorative checkmarks twice; use either meaningful icon alternative text or adjacent status text, not both.

## Contrast, zoom, motion, and touch

- Normal text contrast is at least 4.5:1; large text and meaningful graphical objects are at least 3:1.
- Information and controls remain usable at 200% browser zoom.
- Content reflows at 320 CSS px without two-dimensional page scrolling; a genuinely tabular staff table may scroll within a labelled region if a card alternative would lose relationships.
- Applicant touch targets are at least 48 × 48 CSS px with separation from adjacent targets.
- Do not encode meaning only with position, shape, or color.
- Respect `prefers-reduced-motion`. The MVP does not need nonessential animation.
- Do not use flashing content or time-limited interactions.

## Files and uploaded-document access

- The upload control has a visible label and clear accepted formats: PDF, JPG/JPEG, PNG, plus the configured maximum size.
- Selecting a file does not upload without a clearly described action unless auto-upload behavior is explicitly announced.
- Report upload progress in text and announce success/failure.
- Provide the filename, version, upload time, and localized review status as text.
- A document preview or download link identifies the document and whether it opens a new window.
- Do not require drag-and-drop; a native file picker is always available.

## Language and accessibility test matrix

Before a core page is complete, verify:

1. Thai and English at 320 px, a common phone width, and desktop width.
2. Keyboard-only navigation from the browser address bar through the primary task.
3. Visible focus for every interactive control.
4. Browser zoom at 200% without lost content or actions.
5. Screen-reader names for controls, progress, statuses, and timeline current state.
6. Missing translation fallback without exposing a key or raw enum.
7. Long English labels and Thai line wrapping without clipping.
8. Errors announced once, linked to the correct field, with entered values retained.
9. Status meaning understandable in monochrome.
10. Language switching in the middle of classification and document work without state loss.

Target WCAG 2.2 AA for applicant-facing interfaces. Any known exception must be recorded as a defect, not silently accepted.
