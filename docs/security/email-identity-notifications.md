# Email Identity and Notifications

## Status and interpretation

This document defines the implemented account-activation and transactional-email feature. The Django model/API, signed activation token, templates, PostgreSQL outbox, polling retry worker, Vue registration/activation views, localized error and resend states, and automated backend/frontend tests are present. A Gmail SMTP smoke test was completed on 2026-09-19 without recording credentials in Git or test output.

“Authenticate through Gmail” means that HoTLinE Doc keeps its own Django account and sends a single-use email-verification link through Gmail SMTP. Gmail is the delivery provider, not the identity provider. Google OAuth / “Sign in with Google” is a separate future decision and is not implied by this requirement.

The existing password-reset flow remains in scope and uses the same delivery configuration.

## Account lifecycle and user management

### Applicant registration

1. Public registration accepts display name, normalized email, password, password confirmation, language preference, and required privacy/terms consent only.
2. The server always assigns `APPLICANT`. A public request can never set role, staff status, superuser status, or `LocalAuthority`.
3. A new account records a separate email-verification state such as nullable `email_verified_at`. Account disablement (`is_active`) must remain distinct from email verification so administrators can revoke access without corrupting verification history.
4. Registration returns a generic accepted response. Duplicate-email and unknown-email resend requests must not reveal whether an account exists.
5. Until verification succeeds, the account cannot create an authenticated session or access protected application data. The UI explains how to resend the email without exposing account existence through the API response.
6. The activation link is built from configured `FRONTEND_BASE_URL`, not from a request header. It contains a purpose-specific, random/signed, single-use token with a configured expiry.
7. Successful activation records the server time, invalidates the token, and permits normal login. Reuse, expiry, malformed tokens, or a changed email fail safely without disclosing account details.
8. The browser may retain only a validated same-origin relative continuation path while the user opens the activation email. It never stores the activation token, password, session identifier, or trusted authorization state; another browser/device falls back to the applicant dashboard.

### Managed roles

- `LOCAL_OFFICER`, `CENTRAL_OFFICER`, and `SUPER_ADMIN` are created or invited only by an authorized administrator. Self-registration never grants these roles.
- A local officer still requires exactly one active `LocalAuthority`; email verification does not widen object access.
- Changing an email address requires password or administrator re-authentication, clears the verification state, sends a new activation link, and invalidates existing sessions as appropriate.
- Disabling an account blocks login immediately. Role, authority, activation, disablement, and email changes create immutable audit entries without storing token values or email bodies.
- Production administration uses individual accounts. Shared Gmail, officer, or admin credentials are forbidden.

## Activation endpoints

| Endpoint | Purpose | Required behavior |
| --- | --- | --- |
| `POST /api/v1/auth/register/` | Create an applicant account | CSRF-protected, throttled, generic `202`, server-owned `APPLICANT` role |
| `POST /api/v1/auth/activation/resend/` | Request another link | Generic `202` for every email; per-email and source throttles |
| `POST /api/v1/auth/activation/confirm/` | Consume an activation token | Single-use and time-limited; generic invalid/expired error |

Registration and resend must not return a token, user-existence flag, role, or delivery-provider error. Delivery failure is observable to operators through redacted logs/metrics, not to anonymous callers.

## Transactional notification scope

Emails are transactional prompts, not the source of workflow truth. The in-app status, history, and authorized API remain authoritative.

| Event | Recipient | Email intent |
| --- | --- | --- |
| Account registration accepted | Applicant email | Verify email and activate the account |
| Password reset requested | Active, verified account | Set a new password with the existing single-use flow; deliver through the retrying outbox and create the token only when sending |
| Application submitted | Applicant; active officers in the responsible authority | Confirm reference/status; alert the correct review queue |
| Application revision requested | Applicant | State that action is required and link to the application |
| Application resubmitted | Applicant; active officers in the responsible authority | Confirm receipt; alert the review queue |
| Application approved | Applicant | Confirm approval and link to the protected printable artifact |
| Application rejected | Applicant | Confirm the decision and link to the protected history/details |

Do not send an email for every upload or every individual document review. Bundle those changes into the application-level revision or resubmission event to avoid noise and conflicting instructions.

Security and account-recovery mail cannot be disabled by a user. A later preference may opt out of non-security workflow mail, but it must not suppress an action-required notice until the product provides an equivalent, reviewed policy.

## Message and privacy rules

- Provide Thai and English text or choose the user's stored language with a safe Thai fallback. Templates must include meaningful plain-text content; HTML is optional.
- Use a recognizable subject, event summary, application reference when relevant, support contact, expiry when relevant, and one trusted HTTPS link.
- Never attach submitted documents or include identity numbers, exact addresses, document contents, rejection/revision free text, passwords, tokens, session data, or other sensitive details in the email.
- Links lead to the normal authenticated application. Possession of an application link never grants access. Activation and password-reset links are the only anonymous token links.
- Do not log credentials, full tokens, full activation/reset URLs, or message bodies. Delivery logs may contain an event code, internal recipient/user identifier, provider response category, attempt number, and timestamp.
- Use a project-controlled Gmail/Google Workspace sender, not a personal mailbox. `DEFAULT_FROM_EMAIL` must align with the authenticated sender or an approved Workspace alias.

## Delivery and consistency

The email service must be called only after the related database transaction commits. A workflow action must not roll back because Gmail is temporarily unavailable.

The implementation uses a small database-backed outbox processed first by an `on_commit` delivery attempt and then by a polling management-command worker for due retries. Each record has a stable event key, recipient user, template code, locale, attempt count, next-attempt time, sent time, and redacted last error class. The event key prevents duplicate mail when an API request is retried. Retry uses bounded exponential backoff and ends in an operator-visible failed state; no infinite retry loop is allowed.

Direct synchronous SMTP from a request is acceptable only for local demonstration. It is not sufficient for production workflow notification because a process failure after commit can lose the message.

Gmail SMTP is suitable for the Hackathon and low-volume testing. Before production, confirm Google Workspace policy, sender-domain authentication, quotas, bounce handling, retention, and whether an approved transactional provider is required.

## Configuration boundary

SMTP configuration is documented in `docs/infra/deployment.md`. Real values live only in the ignored `.env` or the deployment secret store. The committed `.env.example` contains safe placeholders.

For Gmail SMTP submission the expected transport is:

- host `smtp.gmail.com`;
- port `587` with STARTTLS;
- the full Gmail/Workspace address as the username; and
- a Google App Password as the password, never the normal account password.

Google requires 2-Step Verification before an App Password can be created, and some managed or Advanced Protection accounts do not expose App Passwords. Workspace deployments should prefer the administrator-approved SMTP relay or provider policy when applicable. See Google's official [App Password guidance](https://support.google.com/mail/answer/185833) and [SMTP client settings](https://support.google.com/mail/answer/7104828).

## Acceptance checks

The implementation is accepted when automated tests and a real-provider smoke test show that:

1. public registration can create only an `APPLICANT` and cannot mass-assign role/authority/staff fields;
2. login is denied before verification and allowed after a valid activation exactly once;
3. registration and resend responses are indistinguishable for existing and unknown emails and are throttled;
4. expired, malformed, reused, or email-invalidated activation links fail safely;
5. email change, disablement, role change, and authority change preserve authorization rules and create audit entries;
6. each workflow event queues the correct template for only the applicant and/or responsible-authority recipients;
7. transaction rollback queues no email, request retries do not create duplicates, and temporary SMTP failure is retried without rolling back the workflow action;
8. templates contain no attachments or prohibited sensitive data and links use the trusted frontend base;
9. Thai/English fallback, keyboard-accessible activation/resend UI, and clear expiry/error states pass UI checks; and
10. Gmail delivery is smoke-tested with a non-production account without exposing the App Password in Git, logs, screenshots, or handoff notes.
