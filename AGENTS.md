# HoTLinE Doc Agent Guide

Operating rules for human and AI contributors. This two-day Hackathon MVP prioritizes a correct, secure, accessible end-to-end flow over polish or speculative flexibility.

## Source of Truth

`docs/` is authoritative. Read the relevant docs and implementation before editing.

| Change | Read first |
| --- | --- |
| Scope, flows, acceptance, business rules | `docs/requirements/` |
| Architecture or dependencies | `docs/architecture/` |
| Models, constraints, migrations | `docs/database/` |
| API contracts | `docs/api/api-contract.md` |
| UI, i18n, accessibility | `docs/ui/` |
| Authentication or permissions | `docs/security/auth-rbac.md` |
| Tests | `docs/testing/test-plan.md` |
| Infrastructure or process | `docs/infra/`, `docs/workflows/` |

If docs conflict or omit a required decision, stop and resolve the authoritative document first. Architecture, API, database, business-rule, or workflow changes update affected docs in the same commit.

## Engineering and Business Rules

- Priority order: correct user flow; working end to end; correct database/auth/API; simple UX; accessibility/i18n; visual polish.
- Choose the smallest reliable solution. Apply `docs/architecture/anti-overengineering.md` before adding a dependency, service, queue, cache, framework, or abstraction.
- Django owns business rules, authorization, validation, workflow, references, timestamps, audit/history, and file checks. Vue owns presentation and interaction, never authority.
- Keep APIs under `/api/v1/`, use the Django ORM, and keep storage behind Django's interface.
- Classification rules, property/document types, requirements, agencies, authorities, and fees are database-driven; never duplicate changeable master data in Vue.
- `8 rooms / 36 guests` is `REQUIRES_LICENSE_REVIEW`; never invent Type 1 or Type 2.
- Transitions atomically write immutable status history/audit. Replacement uploads create versions and retain history. Issued hotel licences retain their fee-schedule reference and snapshot.
- The supplied checklist is not officially validated Thai legal guidance. Seeded contacts and records are fictional; never imply certification or legal completeness.

## Authorization

- `APPLICANT`: own properties/applications only.
- `LOCAL_OFFICER`: applications assigned to their `LocalAuthority` only.
- `CENTRAL_OFFICER`: aggregate province data only; no individual decisions in the MVP.
- `SUPER_ADMIN`: master-data administration through Django Admin.

Enforce scope in backend querysets and mutations. Frontend guards are UX only. Add negative permission tests when protected access changes; avoid disclosing another user's records.

## Internationalization, Accessibility, and UX

- User-facing copy uses `vue-i18n`; support Thai and English without flags. Translated master data uses normalized locale records and documented fallbacks, not per-language columns.
- Use semantic HTML/native controls, visible focus, associated labels/help/errors, keyboard support, sufficient contrast, readable text, large touch targets, and textual status cues. Never rely on color or icons alone.
- Applicant UX follows **one screen = one main task** and clearly communicates location, next action, and consequence.
- Public classification remains available before login and preserves progress through authentication. Do not expose Super Admin on the public gateway.

## Privacy and Security

- Never use or commit real PII, identity documents, credentials, private keys, production secrets, or `.env`; commit only safe examples.
- Validate upload extension, MIME, size, path, and authorization on the backend; never execute uploaded content.
- Use Django password hashing and backend-generated ownership, roles, references, timestamps, status, and audit metadata. Never weaken permissions to make a demo pass.

## Testing and Scope Protection

- Update tests for changed rules, permissions, transitions, classification, document versions, fees, schema, API, or UI behavior. Cover success, failure, and negative authorization cases in `docs/testing/test-plan.md`.
- Run focused checks while iterating and the broader relevant suite before handoff. Report only commands actually run.
- Do not build deferred OCR, AI extraction, notifications, chat, marketplaces, advanced analytics, public QR verification, or full Myanmar/Chinese localization before the Must Have flow works.
- Preserve dirty-tree work. Never reset, clean, revert, reformat, or include changes you do not own; coordinate shared models, migrations, contracts, and locale files.

## Git Workflow

Before work, read relevant docs and inspect `git status`, branch, recent log, stash, and reflog without modifying them.

- One commit equals one reviewable subtask: feature, bug fix, migration, test, refactor, or docs.
- Commit a completed, verified subtask locally before starting the next one.
- Keep implementation, affected tests, and required architecture/API/database/business/workflow docs in the same commit. Contributor-guide-only work gets a separate docs commit.
- Stage only current-task files; never mix unrelated contributor changes.
- Never commit `.env`, credentials, keys, real PII, uploads, dumps, build/dependency output, or temporary files.
- Run appropriate checks before commit and report results in the handoff.
- Never rewrite history, amend, backdate timestamps, forge authorship, or create empty/fabricated commits.
- Never push, publish, change visibility/remotes, or force-push without explicit user approval.

Commit messages use `<type>(<scope>): <imperative summary>`. Scope is optional. Allowed types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`, `ci`, `perf`, `security`. Allowed scopes: `api`, `web`, `db`, `auth`, `wizard`, `workflow`, `documents`, `i18n`, `a11y`, `infra`, `docs`.

```text
feat(wizard): classify accommodation from room and guest limits
fix(auth): prevent officers from accessing other authorities applications
test(workflow): cover request-more-documents transition
docs(api): document application submission endpoint
chore: establish project baseline
```

Codex auto-commits locally only when a bounded feature/bug fix and its docs/tests are complete, the diff contains only current-task files, and no current-task check fails. Do not auto-commit mixed, incomplete, or unverified work. Pushing, publishing, and remote changes always require approval. If safe commit conditions are not met, report the blocker and leave unrelated work untouched.

## Change Loop and Definition of Done

1. Inspect docs, Git state, code, and migrations; define the smallest acceptance condition.
2. Implement the thinnest complete change; update tests and docs.
3. Run focused then broader checks; review unstaged/staged diffs for secrets, PII, generated files, unrelated churn, and undocumented decisions.
4. Commit the verified subtask; hand off outcome, checks, limitations, and next safe step.

A full feature is done only when backend behavior/permissions work, frontend success/error/empty states work, relevant tests pass, accessibility/i18n remain usable, and docs match implementation. For docs-only or single-layer work, apply and report that subset without claiming the full MVP is complete.
