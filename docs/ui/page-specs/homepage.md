# Homepage / role gateway

## Purpose and route

- Route: `/`
- Authentication: public
- Main task: choose how to enter HoTLinE Doc.

This is a role gateway, not a marketing homepage. It contains exactly three role options and no statistics, carousel, feature marketing, testimonials, news, or complex footer.

## Required content

Header:

> HoTLinE Doc

Language selector:

> ไทย  
> English

Main heading:

> ยินดีต้อนรับสู่ HoTLinE Doc

Introductory text:

> ระบบช่วยตรวจสอบ เตรียมเอกสาร  
> และติดตามการขอใบอนุญาตโรงแรม

Instruction:

> กรุณาเลือกว่าคุณเข้ามาใช้งานในฐานะใด

All copy uses `vue-i18n`; the Thai above is the required Thai presentation, not text to hardcode in the component.

## Role options

Display these three large options in this order. The applicant option is visually primary and appears first.

### 1. Applicant

Title:

> ผู้ประกอบการ / เจ้าของที่พัก

Description:

> ตรวจสอบประเภทที่พัก  
> เตรียมเอกสาร และติดตามคำขอ

CTA:

> เริ่มตรวจสอบที่พัก

Behavior: navigate directly to classification step 1. Do not require authentication. If an authenticated applicant explicitly returns here with an in-progress application, the CTA may resume that applicant flow only when the destination is clearly stated; it must never route an officer into applicant data.

### 2. Local officer

Title:

> เจ้าหน้าที่ท้องถิ่น

Description:

> ตรวจสอบคำขอในพื้นที่รับผิดชอบ

CTA:

> เข้าสู่ระบบเจ้าหน้าที่

Behavior: navigate to staff login with the intended local-officer destination. After successful authentication, continue to the LocalAuthority-scoped work queue. Authentication/authorization determines the actual role; a URL hint cannot grant access.

### 3. Central officer

Title:

> เจ้าหน้าที่ส่วนกลาง

Description:

> ดูภาพรวมคำขอทั้งจังหวัด

CTA:

> เข้าสู่ระบบส่วนกลาง

Behavior: navigate to staff login with the intended central destination. After successful authentication, continue to the province overview. Authentication/authorization determines the actual role.

Do not add a Super Admin card. Super Admin uses Django Admin through a separately documented URL.

## Layout and interaction

- Use a centered, single-column introduction followed by three large role regions.
- On phone widths, stack all role options vertically and make their CTAs full-width.
- On wider screens, the options may remain stacked or use a simple grid, but applicant stays first in reading and tab order and remains visually primary.
- Each option uses a heading, description, and real link/button. Do not make an unlabeled generic card the only click target.
- Role titles and CTAs must not be truncated.
- Language switching happens in place and retains focus context where practical.
- On initial load, keyboard focus remains at the normal document start; provide a skip link rather than automatically focusing a role.

## States

The page requires no API data for its core content.

- If locale preference cannot be loaded, render Thai and keep all role links functional.
- If JavaScript startup is delayed, show a stable shell rather than a blank page.
- If a stale authenticated session is discovered after choosing a staff role, the login/session flow decides the permitted destination and shows a neutral role mismatch message if needed.

## Accessibility

- Use one level-one heading for the welcome text.
- Put the three options in a labelled list or three sibling sections with level-two headings.
- The language control has an accessible label such as “ภาษา / Language” and programmatically exposes the selected locale.
- Every CTA's accessible name includes its visible label; do not rely on surrounding card text to disambiguate it.
- Controls meet the 48 × 48 CSS px applicant touch-target goal.

## Acceptance criteria

1. An unauthenticated applicant reaches classification step 1 with one activation.
2. Local and central selections lead to authentication before protected content.
3. Only the three specified roles are displayed, in the specified order.
4. Applicant is the primary option; Super Admin is absent.
5. Thai and English selectors use text, not flags, and switching locale does not navigate away.
6. The page has no marketing sections, carousel, statistics, dense navigation, or complex footer.
7. The complete page is usable at 320 CSS px and by keyboard.
