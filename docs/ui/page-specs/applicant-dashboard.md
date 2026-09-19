# Applicant dashboard and application list

## Purpose and route

- Route: `/applications`
- Authentication: `APPLICANT`
- Main task: understand which owned application needs attention and continue the correct next step.

This remains a compact application overview, not a complex analytics dashboard. The backend returns only applications owned by the authenticated applicant.

## Required layout

1. A compact identity band with display name, applicant role context, email, and the action to check a new accommodation.
2. Four text-labelled counts: needs applicant action, in progress, approved, and total.
3. One filter for needs action, in progress, completed, or all.
4. Application cards ordered with actionable work first and recent updates next.

Each card shows reference state, accommodation name, localized status, database-provided property type, responsible LocalAuthority, last update, and one next-step primary action. Draft/ready/revision cards also show current document progress, a plain-language next step, and a secondary action to edit accommodation details. Draft/ready editing may update the responsible authority and classification answers; revision editing keeps those two workflow-routing inputs locked. The server re-evaluates classification and the checklist after eligible answer changes. Color and icons supplement but never replace status text.

## API data

`GET /api/v1/applications/` supplies the type, responsible authority, current stage, applicant-action flag, requirement counts, and timestamps. Vue may group and filter the already owner-scoped page but does not infer workflow permission or retrieve applications individually to construct the list.

## Accessibility and responsiveness

- The page has one level-one heading inside the identity band and a following level-two application-list heading.
- Summary counts have a group label and visible text.
- The filter is a native labelled select.
- Cards retain a logical heading and action order at 200% zoom and stack at phone widths.
- Every card has one descriptive primary action; status never relies on color alone.
