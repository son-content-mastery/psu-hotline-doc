# AI-assisted Development Workflow

## Purpose

This workflow lets human and AI contributors move quickly without losing domain, security, or documentation consistency. It applies to every implementation task in the Hackathon. `AGENTS.md` is the top-level operating agreement; this document describes the repeatable execution loop.

## Non-negotiable Gate

Do not begin feature implementation until the documentation foundation for that area exists. Before changing a domain, read its source-of-truth files:

| Change | Required reading |
| --- | --- |
| Scope or behavior | `docs/requirements/mvp-scope.md`, `user-stories.md`, `business-rules.md` |
| Component boundary/dependency | `docs/architecture/` |
| Model/migration | `docs/database/` |
| Endpoint | `docs/api/api-contract.md` |
| Page/component | Relevant `docs/ui/` page spec plus accessibility/i18n docs |
| Auth/permission | `docs/security/auth-rbac.md` and business-role rules |
| Deployment | `docs/infra/deployment.md` |
| Tests | `docs/testing/test-plan.md` |

If docs conflict or omit a decision needed for safe implementation, pause the implementation, propose the smallest resolution, and update the authoritative document first. Do not fill ambiguity silently in code. The canonical example is `8 rooms / 36 guests`: use `REQUIRES_LICENSE_REVIEW`, never an invented Type 1/Type 2 category.

## Delivery Phases

Work in this order, keeping each completed phase runnable:

1. **Inspect** — repository, existing code/config, status, and constraints; preserve unrelated work.
2. **Foundation** — `AGENTS.md`, README, and `/docs` source of truth.
3. **Backend foundation** — Django/DRF/PostgreSQL, users/roles, master data, classification, applications, documents, audit, fees, licenses, migrations, Admin.
4. **Backend API** — documented endpoints, authorization, validation, tests.
5. **Frontend foundation** — Vue/TypeScript/router/Pinia/i18n/Tailwind and simple route/layout shell.
6. **Applicant flow** — homepage through tracking/revision, working end to end before broadening UI.
7. **Officer flow** — authority-scoped queue, review, revision, approval.
8. **Central overview** — minimal aggregate-only view.
9. **License** — print-friendly approved reference.
10. **Demo and QA** — clean seed, full happy path, permission checks, builds, documentation reconciliation.

Do not parallelize later-phase features if the shared contract/model they require is still undecided.

## The Task Loop

### 1. Frame one vertical outcome

Write a one-sentence result and concrete acceptance checks. Prefer a small end-to-end slice such as “backend evaluates all five classification outcomes and the wizard renders translated results” over “build classification system.”

Identify:

- affected user story and Must Have item;
- relevant API/model/page docs;
- permission boundary;
- error/empty/loading states;
- test cases; and
- files likely to be shared with other work.

### 2. Inspect before editing

- Read the full relevant files, not isolated snippets.
- Check working-tree state and recent migrations.
- Search for existing terms, models, endpoints, translations, and tests before creating duplicates.
- Treat uncommitted changes as another contributor's work unless clearly yours.
- Never overwrite or revert unrelated changes to make a task easier.

### 3. State the smallest design

Choose the simplest solution compatible with the docs. Record a new architectural/domain decision in docs before code. Apply `anti-overengineering.md` before adding dependencies, layers, queues, caches, generic engines, or component libraries.

For business mutations, identify the transaction boundary and which history/audit rows it must create. For protected resources, identify both queryset scoping and object-level enforcement.

### 4. Implement backend authority first

For cross-stack features, establish backend behavior before trusting frontend behavior:

- database constraints and migration;
- domain validation/transition;
- permission and object scoping;
- serializer/API representation;
- success and failure tests; then
- presentation and client interaction.

Frontend validation and route guards mirror server behavior for usability; they never replace it.

### 5. Test narrow, then broad

Run the fastest relevant checks while iterating. Before handoff, run the broader checks proportional to risk.

Typical sequence once the project commands exist:

```text
backend unit test for changed domain
backend permission/API tests for changed resource
Django system checks and migration consistency
frontend focused Vitest tests when useful
frontend typecheck and production build
full backend suite before demo/release
```

Test negative paths explicitly:

- another applicant's object;
- another authority's application;
- wrong role;
- invalid transition;
- missing/rejected documents;
- invalid file type/size;
- duplicate/retried action; and
- absent requested translation.

Do not say “passes” for a check that was not run. Report the exact command and result, or label it unverified with the reason.

### 6. Reconcile documentation

Before considering the change complete:

- update API examples/status/errors if behavior changed;
- update ERD/normalization if models or constraints changed;
- update business rules when a domain decision changed;
- update page specs and translations when the user flow changed;
- update test plan and setup commands; and
- search for stale names/codes across docs and code.

Documentation updates belong in the same change as implementation.

### 7. Handoff clearly

Use this compact handoff structure:

1. outcome delivered;
2. important domain/architecture choices;
3. files/contracts changed;
4. commands actually run and their results;
5. known limitations or unverified items; and
6. next safe slice.

Avoid dumping a list of every file when a domain summary is clearer. Never claim the full MVP works because an isolated unit test passes.

## Multi-agent Coordination

Parallel work is useful only with non-overlapping ownership and stable contracts.

Before delegating:

- define one concrete deliverable and acceptance criteria;
- assign explicit files or domain boundaries;
- identify files that must have a single owner (models, migrations, API contract, shared locales, central settings); and
- share decisions, not just task names.

While work is parallel:

- do not have multiple agents edit the same migration/model/contract without coordination;
- communicate new status codes, field names, endpoint shapes, and translation keys immediately;
- integrate small completed slices early; and
- review delegated output against source docs rather than assuming correctness.

The coordinating contributor owns final integration, test execution, and doc/code reconciliation. Delegation does not transfer accountability.

## Domain-specific Checklists

### Classification

- Rules are active, ordered database records.
- All five outcomes and invalid input are tested.
- Anonymous answers are re-evaluated after login.
- `REQUIRES_LICENSE_REVIEW` has no inferred property type/fee.

### Application workflow

- Named action, not arbitrary status patch.
- Actor may perform the source→target transition.
- Transaction writes status, status history, and audit together.
- Retry/concurrency cannot duplicate reference/license/history.
- Applicant-facing label is translated.

### Documents

- Owner/authority permission is enforced before file access.
- Extension, MIME, and size are checked on the server.
- New upload creates a version; old bytes/review remain.
- Exactly one current version is enforced.

### Master data and translations

- Data is not duplicated in Vue.
- Stable code is separate from display text.
- Parent/locale uniqueness is enforced.
- Requested locale → Thai → stable-code fallback is tested.
- Demo checklist content is not described as legally authoritative.

### UI

- One screen has one main task and one obvious primary action.
- Current location, next action, and consequence are clear.
- Keyboard/focus/labels/errors/status semantics work.
- Mobile layout and large touch/text targets are usable.
- Raw backend codes do not leak as sole labels.

## Stop Conditions

Stop and escalate rather than guess when:

- an authoritative legal/business classification is missing;
- a change would expose cross-owner or cross-authority data;
- a destructive migration could lose user/history/file data;
- required secrets or external credentials are unavailable;
- two active edits conflict in a shared contract/migration; or
- the requested work materially expands beyond the accepted MVP.

A blocked optional integration must not prevent progress on an in-scope local/demo alternative. For example, missing ThaiID access means use documented demo authentication, not abandon the MVP.

## Final MVP Verification

Before presenting the completed MVP:

1. create a clean database and run migrations;
2. run `seed_demo` and verify an idempotent second run;
3. run the full backend tests and Django checks;
4. run frontend tests if present, typecheck, and production build;
5. execute the complete 20-room/40-guest/no-restaurant demo story;
6. execute the 8-room/36-guest ambiguity case;
7. manually verify applicant ownership and cross-authority denial;
8. verify replacement upload history and immutable audit/history;
9. verify Thai/English switching and fallback plus mobile/keyboard basics;
10. reconcile README, docs, OpenAPI, migrations, and actual behavior.

The final report must list known limitations and deliberately deferred stretch work.
