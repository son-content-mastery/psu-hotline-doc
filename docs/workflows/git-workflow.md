# Git Workflow

## Goal

Use a lightweight workflow that keeps the Hackathon main branch runnable and makes changes easy to review or recover. Documentation, migrations, tests, and implementation for one decision travel together.

## Protect Existing Work

Before editing:

```bash
git status --short
git branch --show-current
git diff --stat
```

- Treat existing uncommitted files as user/team work.
- Do not reset, clean, discard, or rewrite changes you did not create.
- Do not reformat unrelated files.
- If another contributor owns a shared file, coordinate before editing it.
- Never commit secrets, real PII, uploaded identity documents, local media, database dumps, virtual environments, or generated dependency/build folders.

## Branches

For work that uses branches, branch from the team's current integration branch with one purpose:

```text
codex/<short-purpose>
```

Examples:

```text
codex/classification-rules
codex/document-versioning
codex/officer-review
```

Short-lived branches are preferred. Do not create nested release/develop structures for a two-day project. If the team works directly on one shared Hackathon branch, preserve the same small-commit and review discipline and coordinate file ownership explicitly.

Do not force-push a shared branch. Rebase only your private unpublished branch and only when it will not discard work.

## Work-unit Size

Each change should produce one reviewable outcome, ideally a vertical slice. Good boundaries include:

- classification model/evaluator/API/tests/docs;
- versioned upload validation/API/tests/docs; or
- one officer revision transition through UI/API/audit/tests.

Avoid mixing broad refactors, dependency upgrades, UI restyling, and a domain feature. Smaller changes reduce live-demo risk and merge conflicts.

## Documentation-first Sequence

For any architectural or domain change:

1. update/confirm the relevant source-of-truth document;
2. implement migration/model and backend behavior;
3. update API and frontend;
4. update tests and examples;
5. reconcile docs with actual behavior; and
6. commit them as one coherent change or an explicitly ordered, build-safe series.

Do not merge implementation that knowingly contradicts `/docs`.

## Shared-file Coordination

These files/directories need a clear single owner at any one time:

- Django settings and root URLs;
- user/application/document models;
- migration numbering and migration files;
- `docs/api/api-contract.md`;
- generated OpenAPI schema;
- package/requirements lock files;
- shared Pinia/router configuration; and
- locale JSON files.

Before parallel work, assign ownership and communicate proposed model fields, status codes, endpoint paths, and translation-key namespaces. Prefer one migration author per Django app until changes are integrated.

## Migrations

- Never edit an already shared/applied migration to hide a later schema change; add a new migration.
- Inspect generated migrations before committing.
- Give data migrations deterministic forward behavior and a safe reverse operation when practical.
- Do not place real/demo secrets or environment-specific paths in migrations.
- Run migration checks and, before final demo, migrate a clean database.
- If two branches generate conflicting migration leaves, coordinate and create an explicit merge migration after both model decisions are accepted; do not randomly renumber files.

Model, migration, ERD, normalization notes, seed data, and affected tests should agree in the same integrated change.

## Staging and Reviewing

Review before staging:

```bash
git diff --check
git diff
git status --short
```

Stage only intended files. Review the staged patch as the actual change to be recorded:

```bash
git diff --cached --check
git diff --cached
```

Look specifically for:

- secrets or personal data;
- accidental generated/media files;
- debug output or bypassed permissions;
- undocumented contract/schema changes;
- raw Thai strings in reusable frontend logic;
- hardcoded master-data arrays;
- destructive migration operations; and
- unrelated formatting churn.

## Commit Messages

Use concise imperative messages in this required format:

```text
<type>(<scope>): <imperative summary>
```

The scope may be omitted when none applies. Allowed types are `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`, `ci`, `perf`, and `security`. Allowed scopes are `api`, `web`, `db`, `auth`, `wizard`, `workflow`, `documents`, `i18n`, `a11y`, `infra`, and `docs`.

```text
docs: define classification ambiguity rule
feat(wizard): add database-driven classification evaluation
fix(auth): enforce local authority scope on officer detail
test(documents): cover document replacement versioning
chore(infra): add local Docker development services
```

A commit should leave the repository in a coherent state. If a large slice needs multiple commits, order them so intermediate commits are understandable and do not deliberately break the build.

Do not add AI-generated attribution, fabricated co-authors, or tool transcripts to commit messages.

## Local Commit Timing

- One local commit represents one verified, reviewable subtask.
- Commit a completed subtask immediately before starting the next one.
- Architecture, API, database, business-rule, or workflow documentation changed by implementation belongs in the same commit.
- Codex commits a bounded feature or bug fix automatically only when implementation, docs, and tests are complete; the diff contains only current-task files; and no current-task check fails.
- Do not auto-commit mixed contributor changes, incomplete/unverified work, or any action that also requires pushing, publishing, or changing remote settings.
- Pushing, changing repository visibility/remotes, or force-pushing always requires explicit user approval.

## Pre-integration Checks

Run checks proportional to the change and report only those actually executed:

- backend focused and full relevant pytest suites;
- applicant/authority negative permission tests;
- Django `check` and migration consistency;
- seed command against a clean database when seed/model data changes;
- frontend focused tests, typecheck, and production build;
- `git diff --check`; and
- docs/contract search for stale names or codes.

Before the final demo integration, run the full verification list in `ai-development-workflow.md`.

## Pull Request or Review Note

Keep review notes short and evidence-based:

1. outcome and linked user story/Must Have item;
2. domain/schema/API decisions;
3. security and accessibility impact;
4. tests and commands actually run;
5. screenshots only when they clarify UI behavior; and
6. known limitations/follow-ups.

Call out migrations, new environment variables, seed changes, and breaking API changes prominently.

## Integrating Changes

- Update from the integration branch before final merge and resolve conflicts by understanding both decisions.
- Never choose “ours” or “theirs” wholesale for models, contracts, migrations, or locale files without reconciling content.
- Re-run affected checks after conflict resolution.
- Prefer a normal merge or team-selected squash policy; consistency matters more than elaborate history.
- Delete short-lived branches after safe integration.

## Emergency Demo Fixes

For a demo-blocking bug:

1. reproduce and write the smallest regression test where feasible;
2. change only the blocking behavior;
3. run focused permission/domain checks plus the affected happy-path segment;
4. update docs if behavior changed; and
5. record the limitation if a safe full fix cannot fit the remaining time.

Do not bypass backend permissions, file validation, audit/history, or database integrity to make the demo appear successful.

## Prohibited Git Actions

- No destructive reset/clean/checkout of uncommitted team work.
- No history rewriting, amending existing commits, timestamp backdating, fabricated authorship, or empty/fabricated commits.
- No force push to a shared branch.
- No committing `.env`, real credentials, PII, local uploads, or database volumes.
- No silent rewriting/deletion of shared migrations.
- No merge that knowingly leaves docs and implementation inconsistent.
- No claim that checks passed without their actual execution.
