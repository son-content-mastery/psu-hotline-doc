# Officer Case Library

## Route and permission

- Route: `/officer/cases`
- Permission: verified `LOCAL_OFFICER` only.
- API: `GET /api/v1/officer/case-library/?q=&decision=&property_type=`.

## Interaction

The officer reaches the library from the work queue. A compact form combines one keyword field with decision and accommodation-type filters; search happens on explicit submit and reset restores the full result. Results are cards because each case has a small structured comparison set rather than row-level actions.

Each card shows only the pseudonymous case reference, decision, accommodation type, room/guest/restaurant facts, revision rounds, elapsed processing days, reviewed-version count, and decision date. No link opens the source application. A visible advisory states that similarity never replaces current-case review.

FAQs follow the results as native keyboard-operable `details/summary` disclosures. Empty, loading, failure, and paginated states have text announcements and do not depend on colour.
