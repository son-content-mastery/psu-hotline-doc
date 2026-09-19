# Classification wizard and result

## Purpose and routes

- Suggested question route: `/classification/:step`
- Suggested result route: `/classification/result`
- Authentication: public
- Main task per question screen: answer one classification question.
- Main task on result screen: understand the outcome and the next appropriate step.

Applicants receive useful classification and document information before login. The classification decision comes from the backend's database-driven rules; Vue must not reproduce the rule tree.

## Entry and transient state

Starting from the applicant homepage CTA creates or resets an anonymous classification session only after warning if doing so would discard an existing unfinished classification. Store the three answers and the latest evaluation response in short-lived client state suitable for surviving navigation to authentication (for example Pinia plus session-scoped persistence). Do not store personal data in this anonymous state.

After authentication, send or attach the preserved evaluation to the applicant's draft application using the API. The backend reevaluates/validates the answers; the client must not treat a previously rendered outcome as authoritative forever. Clear the anonymous copy after it is safely attached.

Back navigation preserves valid earlier answers. Refreshing or returning from authentication restores the current step/result when transient state is still available. A missing or invalid transient state returns to step 1 with a localized explanation.

## Shared question-screen anatomy

Each question is a separate screen and includes, in this order:

1. service header and language selector;
2. visible step text: `ขั้นตอน N จาก 3` / `Step N of 3`;
3. a large progress indicator with programmatic current/max values;
4. one level-one question;
5. one answer control and concise helper text;
6. an inline validation region;
7. primary **ถัดไป** / **Next** action;
8. **ย้อนกลับ** / **Back** from steps 2 and 3.

Do not display a summary of all three questions as editable fields on one screen. The explicit Back action is the only step navigation in the MVP; the progress indicator is not clickable.

## Step 1: number of rooms

Step label:

> ขั้นตอน 1 จาก 3

Question:

> ที่พักของคุณมีห้องพักทั้งหมดกี่ห้อง?

Example field presentation:

> 20

Helper:

> นับเฉพาะห้องที่เปิดให้ผู้เข้าพัก

Behavior:

- Use one visibly labelled numeric text/number control with a numeric mobile input mode.
- Accept a positive whole number. Trim surrounding whitespace; do not accept decimals, negative values, scientific notation, or units typed into the value.
- Do not impose an arbitrary UI maximum; more than 49 is a valid answer that leads to an out-of-scope outcome.
- Continue to step 2 only after local format validation.

## Step 2: maximum guests

Step label:

> ขั้นตอน 2 จาก 3

Question:

> ที่พักของคุณรองรับผู้เข้าพักได้สูงสุดกี่คน?

Helper copy explains that this means the maximum total guest capacity, not the number currently staying.

Behavior:

- Use one visibly labelled numeric control.
- Accept a positive whole number with the same input rules as rooms.
- Continue to step 3 after local format validation.
- Back returns to step 1 with both focus placement and the prior room value preserved.

## Step 3: restaurant

Step label:

> ขั้นตอน 3 จาก 3

Question:

> ที่พักของคุณมีห้องอาหารหรือไม่?

Behavior:

- Use a `<fieldset>` and `<legend>` with two explicit radio choices: **มี** / **Yes** and **ไม่มี** / **No**.
- Do not preselect an answer.
- The primary action is **ดูผลการตรวจสอบ** / **See result**.
- Back returns to step 2 and preserves all prior answers.
- Submitting sends all three values to the classification evaluation API once. Prevent duplicate requests while loading.

## Evaluation loading and errors

During evaluation, retain the answers, show localized progress text such as “กำลังตรวจสอบข้อมูล”, and mark the result region busy. Do not replace the page with an indefinite spinner.

For a validation error, keep the user on the relevant question and focus its message. For a network/server error, retain all answers and provide **ลองอีกครั้ง** / **Try again**. If rules cannot produce a safe outcome, show a neutral “cannot determine” state and direct the user to authoritative contact guidance; never guess a property type in Vue.

## Result-screen anatomy

The result screen includes:

1. heading `ผลการตรวจสอบเบื้องต้น` / `Preliminary check result`;
2. an explicit outcome title and explanation;
3. an answer summary (rooms, guests, restaurant) with **แก้ไขคำตอบ** / **Edit answers**;
4. fee and validity only when supplied for an applicable category;
5. a statement that the result is based on current system rules and is not itself a licence;
6. exactly one primary next action appropriate to the outcome.

The displayed category, fee, validity, explanation, and recommended next step come from the evaluation response and localized master data. Never derive them from room count in the component.

## Required outcomes

### `NOT_HOTEL`

Seed rule: rooms `<= 8` **and** guests `<= 30`.

Thai outcome:

> แจ้งสถานที่พักที่ไม่เป็นโรงแรม

Explain in plain language that the current rule does not require a hotel licence and that the user may continue to the supplied non-hotel accommodation notification checklist. Do not show a fee or fabricate a hotel licence. The response assigns the non-licensing processing type `NON_HOTEL_NOTIFICATION`, and the primary action opens its 17-item public checklist before login.

### `TYPE_1`

Seed rule: rooms `> 8` and `<= 49`, restaurant is false.

Thai outcome:

> ที่พักแรมประเภทที่ 1

Show returned fee `10,000 THB` and validity `5 years`, formatted for the locale. Primary action:

> ดูรายการเอกสาร

This opens the dynamic document checklist without requiring login.

### `TYPE_2`

Seed rule: rooms `> 8` and `<= 49`, restaurant is true.

Thai outcome:

> ที่พักแรมประเภทที่ 2

Show returned fee `20,000 THB` and validity `5 years`, formatted for the locale. Primary action opens the dynamic document checklist without requiring login.

### `REQUIRES_LICENSE_REVIEW`

Required safe edge case: `8 rooms / 36 guests` requires a hotel licence because guest capacity exceeds the exemption, but the source requirements do not establish Type 1 versus Type 2 for this shape.

The result must state clearly:

> ที่พักนี้ต้องขอใบอนุญาตโรงแรม แต่ต้องยืนยันประเภทเพิ่มเติม

Explain that the system will not guess a category. Show database-driven contact/next-step guidance when available. Do not show Type 1/Type 2 fees as though confirmed and do not generate a category-specific checklist or application until an authoritative category is available. The primary action is to view contact guidance or return/edit answers, not to bypass confirmation.

### `OUT_OF_SCOPE`

Seed rule: rooms `> 49`.

Thai outcome:

> อยู่นอกขอบเขตแพลตฟอร์มระยะนี้

Guidance:

> แนะนำให้ติดต่อนายทะเบียนโดยตรง

Display database-driven authority/contact information if available. Do not offer the MVP submission flow or pretend to classify the property.

For `REQUIRES_LICENSE_REVIEW` and `OUT_OF_SCOPE`, the primary result action opens contact guidance rather than returning the visitor to the wizard. Because the three classification questions do not establish an address, the visitor explicitly selects the responsible LocalAuthority from backend master data. The resulting card shows only database-provided phone/email details and clearly labels fictional demo contact data. Editing answers remains a secondary action.

## Authentication handoff

For Type 1 or Type 2, the next sequence is:

`Result → Document checklist (public) → Authentication → Same checklist/application upload state`

Authentication must preserve answers, outcome identifier/rule version if returned, and checklist context. The backend revalidates the classification when the application draft is created. If rules changed during the handoff, show the new result and explain that requirements were refreshed before continuing.

## Accessibility

- The question is the page's level-one heading, not placeholder text.
- Progress has visible text and an accessible name/value.
- Numeric input errors are associated with their controls.
- Restaurant choices are native radio buttons in a labelled group.
- On next/back navigation, focus the new question heading; when returning, do not erase the answer.
- Results are announced by focusing the result heading, not by an unlabelled color change.
- Outcome styling always includes text; icons and color are supplemental.

## Acceptance criteria

1. Only one question is displayed on each of three steps.
2. Step text and a large accessible progress indicator show `N of 3`.
3. `6 rooms / 24 guests` evaluates to `NOT_HOTEL`.
4. `8 rooms / 36 guests` evaluates to `REQUIRES_LICENSE_REVIEW`, never silently to Type 1 or Type 2.
5. `20 rooms / 40 guests / no restaurant` evaluates to Type 1 and offers the checklist.
6. `45 rooms / restaurant` evaluates to Type 2.
7. `60 rooms` evaluates to `OUT_OF_SCOPE`.
8. Rules, labels, fees, and validity are rendered from API data rather than duplicated in Vue logic.
9. Classification and initial requirements remain available before login, and progress survives the authentication handoff.
10. Back, refresh recovery, validation, retry, Thai/English switching, mobile layout, and keyboard operation do not lose valid answers.
