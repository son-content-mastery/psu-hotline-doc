# Normalization Decisions

## Goal

The MVP schema is designed to at least Third Normal Form (3NF) for operational data while retaining a few named historical snapshots. The purpose is practical: update changing government/master data in one place, prevent contradictory records, preserve past decisions, and keep API authorization/query paths understandable.

## What 3NF Means Here

For each normal operational table:

1. one row represents one thing or relationship;
2. fields contain atomic values appropriate to querying and constraints;
3. non-key fields depend on that row's key; and
4. facts about another entity live with that entity rather than being copied across rows.

The design does not split values merely for academic purity. Addresses and localized instruction text remain text fields because the MVP does not need to query their internal parts.

## System-specific Decisions

### LocalAuthority is separate from User

An officer stores `local_authority_id`, not copied authority name, address, and contact fields. Many officers can belong to one authority, and a contact update changes one master row. Properties and applications also reference the authority by key, enabling reliable server-side scope filters.

The application deliberately retains its responsible-authority FK even though the property also has one. This is a documented routing snapshot: changing the current property authority must not silently move an already submitted case.

### PropertyType is separate from Property and Application

Stable type identity and translated display content belong to `PropertyType` and `PropertyTypeTranslation`. Property/application rows reference the type rather than repeating names, fees, or document lists. Outcomes such as `NOT_HOTEL`, `OUT_OF_SCOPE`, and `REQUIRES_LICENSE_REVIEW` may have no property-type FK because inventing a type would be false data.

### ClassificationRule is separate from application inputs

A rule is editable master data; an application's answer/result is an event in time. The application references the rule and preserves its evaluated input/outcome snapshot. Storing all rules directly on every application would duplicate policy and make administration inconsistent; storing only a live rule FK would make old decisions change meaning after an edit.

### DocumentType is separate from ApplicationDocument

`DocumentType` says what a document is. `ApplicationDocument` says which version was uploaded for one application, by whom, when, and with what review state. Names, categories, issuing agencies, and guidance are not repeated on each upload. This allows one document definition to be required by many property types and used by many applications.

### Many-to-many requirements use relationship tables

Property types require many document types, and a document type may be required by many property types. `PropertyTypeDocumentRequirement` represents that many-to-many relationship and stores facts about the relationship, such as required/active state and display order. A comma-separated document list on `PropertyType` or an array in Vue would violate normalization and make constraints/administration difficult.

`ApplicationRequirement` captures which document types applied to one application. It remains a relationship table: it references the application and document type rather than copying names, agency contacts, or translation content. It intentionally snapshots `step_code`, required state, and display order because those are facts about how that checklist applied at the submission boundary. This freeze prevents future master-data edits from silently changing or regrouping an in-flight checklist.

### Translations are separated from master entities

`PropertyTypeTranslation`, `DocumentTypeTranslation`, and `IssuingAgencyTranslation` each contain one locale's text for one parent. The unique `(parent_id, language_code)` constraint prevents duplicate translations.

This avoids repeating structural data once per language and avoids schema changes such as adding `name_my` or `name_zh`. Adding a language inserts rows. Non-translatable stable codes and operational relationships stay in the parent.

For the MVP, `LocalAuthority.official_name` is the statutory source name rather than a set of translated marketing labels. If approved translations are needed later, they must use a child translation table with the same pattern.

### IssuingAgency is separate from DocumentType

Agency name and contact information are facts about an agency, not each document type. Multiple externally issued documents can point to one `IssuingAgency`; changing a phone number updates one place. Document-specific instructions and supporting items remain on `DocumentTypeTranslation` because they describe how to obtain that particular document in a locale.

### FeeSchedule is versioned instead of overwritten

Amount, currency, validity, and effective dates form one fee schedule row for one property type and period. A new fee creates a new row; it does not overwrite the old amount. Date-range validation prevents two ambiguous schedules for the same type/currency and date.

`License.fee_schedule_id` supplies provenance. The amount, currency, and validity snapshots intentionally repeat the selected schedule values so an issued artifact remains reproducible even if master data is corrected or archived.

### ApplicationDocument is versioned rather than overwritten

Every attachment is identified by `(application_id, document_type_id, version, attachment_index)`. Files selected together share the bundle version. A conditional uniqueness constraint permits only one current attachment for each application/document type/attachment position. A review references the exact attachment/version it evaluated. Replacing a bundle marks the previous attachments non-current rather than overwriting file paths or review evidence.

### Reviews, status history, and audit are events

`DocumentReview`, `ApplicationStatusHistory`, and `AuditLog` use one row per event. They are not mutable “last action” columns packed into Application. The application keeps its current status for efficient filtering, while history preserves how it got there. The transition transaction updates both consistently.

`AuditLog` uses a controlled generic `object_type/object_id` pair because it observes multiple models. This is the only purposeful generic relation; core domain behavior never depends on it, so referential business logic remains strongly related through foreign keys.

## Functional Dependency Examples

| Table | Key | Non-key facts depend on |
| --- | --- | --- |
| `LocalAuthority` | `id` | that authority (`code`, official name, contacts) |
| `DocumentTypeTranslation` | `(document_type_id, language_code)` | that document in that language (name, instructions) |
| `PropertyTypeDocumentRequirement` | `(property_type_id, document_type_id)` | that exact requirement relationship (required flag/order) |
| `ApplicationDocument` | `(application_id, document_type_id, version, attachment_index)` | that exact attachment in an evidence-bundle version (storage key, uploader, time, current/status) |
| `FeeSchedule` | `id` | one type/period fee decision (amount, currency, validity, effective dates) |
| `License` | `application_id` | the one issued result for that application |

No translation name determines a master entity, no authority name determines an officer, and no current status determines an application's history.

## Intentional Historical Snapshots

Snapshots are denormalization only when they copy data for a defined historical boundary. The MVP uses these intentionally:

- application rooms, maximum guests, restaurant answer, and outcome at classification;
- application's responsible authority after routing;
- the set of application document requirements;
- license fee amount, currency, and validity; and
- current application status alongside append-only history.

Each has one authoritative creation/update rule and a reason:

| Snapshot | Set when | Why |
| --- | --- | --- |
| Classification inputs/outcome | Server evaluates application classification | Later property/rule edits must not rewrite the decision |
| Responsible authority | Application is routed; fixed by submission | Later property edits must not bypass officer scope |
| Application requirements | Confirmed type checklist is captured; fixed by submission | Later master edits must not change an in-flight case |
| License fee fields | Approval selects effective fee | Issued financial context must remain reproducible |
| `Application.status` | Domain transition | Queues need fast current-state queries; history remains the event record |

Snapshots must not be accepted blindly from the client. They are produced by backend domain logic in the same transaction as their source decision.

## Values Not Stored Redundantly

Unless profiling or an explicit requirement changes the decision, do not persist:

- translated labels on every application/document;
- applicant email/name on Application when ownership is reachable through Property;
- officer authority names on reviews;
- checklist completion percentages;
- “days waiting” values;
- central summary totals; or
- Type 1/Type 2 fees on PropertyType.

Checklist completion, waiting duration, and central totals are derived from current relational data. User-facing labels are resolved through translations.

## Constraints Reinforcing the Model

Normalization is effective only with integrity rules:

- unique stable codes for authorities, types, document types, agencies, and rules;
- unique parent/language translation pairs;
- unique type/document and application/document requirement pairs;
- unique application/document/version plus one conditional current version;
- one decision artifact per application and unique public reference/artifact numbers;
- checked positive counts, versions, file sizes, amounts, and validity periods;
- valid effective date ordering and no overlapping fee periods; and
- protected/inactivated referenced master data rather than destructive deletion.

Cross-row business invariants—classification overlap, status transitions, same-authority review, requirement completeness—remain in named backend domain logic with transactional tests.

## Why This Is Enough for the MVP

The model avoids language-column growth, repeated contact/type data, overwritten fees/files, and serialized relationship lists. It still uses ordinary Django foreign keys and modest relationship tables. It does not introduce event sourcing, a rules DSL, a data warehouse, or generic entity/value storage. That balance supports the demo and leaves understandable upgrade paths without speculative infrastructure.
