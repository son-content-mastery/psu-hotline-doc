# Entity-relationship Model

## Scope

This is the target logical schema for the HoTLinE Doc MVP. It keeps changing master data normalized, preserves document/status history, and stores only the snapshots needed to reproduce submitted and approved decisions. Django migration/model names may use conventional casing, but domain names, relationships, and constraints must remain aligned with this document.

## Mermaid ER Diagram

```mermaid
erDiagram
    LOCAL_AUTHORITY ||--o{ USER_ACCOUNT : assigns_officers
    USER_ACCOUNT ||--o{ PROPERTY : owns
    LOCAL_AUTHORITY ||--o{ PROPERTY : governs
    PROPERTY_TYPE o|--o{ PROPERTY : currently_classified_as
    PROPERTY_TYPE ||--o{ PROPERTY_TYPE_TRANSLATION : has
    PROPERTY ||--o{ APPLICATION : has
    LOCAL_AUTHORITY ||--o{ APPLICATION : is_responsible_for
    CLASSIFICATION_RULE ||--o{ APPLICATION : explains_result
    PROPERTY_TYPE o|--o{ APPLICATION : confirms_type
    USER_ACCOUNT o|--o{ APPLICATION_STATUS_HISTORY : acts_in
    APPLICATION ||--o{ APPLICATION_STATUS_HISTORY : records

    ISSUING_AGENCY o|--o{ DOCUMENT_TYPE : issues
    ISSUING_AGENCY ||--o{ ISSUING_AGENCY_TRANSLATION : has
    DOCUMENT_TYPE ||--o{ DOCUMENT_TYPE_TRANSLATION : has
    PROPERTY_TYPE ||--o{ PROPERTY_TYPE_DOCUMENT_REQUIREMENT : requires
    DOCUMENT_TYPE ||--o{ PROPERTY_TYPE_DOCUMENT_REQUIREMENT : is_required_by
    APPLICATION ||--o{ APPLICATION_REQUIREMENT : freezes
    DOCUMENT_TYPE ||--o{ APPLICATION_REQUIREMENT : identifies

    APPLICATION ||--o{ APPLICATION_DOCUMENT : receives
    DOCUMENT_TYPE ||--o{ APPLICATION_DOCUMENT : classifies
    USER_ACCOUNT ||--o{ APPLICATION_DOCUMENT : uploads
    APPLICATION_DOCUMENT ||--o{ DOCUMENT_REVIEW : receives
    USER_ACCOUNT ||--o{ DOCUMENT_REVIEW : performs

    PROPERTY_TYPE ||--o{ FEE_SCHEDULE : prices
    APPLICATION ||--o| LICENSE : produces
    PROPERTY_TYPE ||--o{ LICENSE : confirms
    FEE_SCHEDULE ||--o{ LICENSE : sourced_fee_from
    USER_ACCOUNT o|--o{ AUDIT_LOG : acts_in

    LOCAL_AUTHORITY {
        bigint id PK
        string code UK
        string official_name
        string contact_phone
        string contact_email
        text address
        boolean is_active
    }

    USER_ACCOUNT {
        bigint id PK
        string email UK
        string password_hash
        string role
        bigint local_authority_id FK
        boolean is_active
        datetime created_at
    }

    PROPERTY {
        bigint id PK
        bigint owner_id FK
        bigint local_authority_id FK
        bigint property_type_id FK
        string name
        text address
        integer rooms
        integer max_guests
        boolean has_restaurant
        datetime created_at
        datetime updated_at
    }

    PROPERTY_TYPE {
        bigint id PK
        string code UK
        boolean issues_license
        boolean is_active
    }

    PROPERTY_TYPE_TRANSLATION {
        bigint id PK
        bigint property_type_id FK
        string language_code
        string name
        text description
    }

    CLASSIFICATION_RULE {
        bigint id PK
        string code UK
        integer priority
        boolean is_active
        integer min_rooms
        integer max_rooms
        integer min_guests
        integer max_guests
        boolean restaurant_value
        string outcome_code
        bigint result_property_type_id FK
        text guidance_key
    }

    APPLICATION {
        bigint id PK
        bigint property_id FK
        bigint responsible_authority_id FK
        bigint classification_rule_id FK
        bigint confirmed_property_type_id FK
        string status
        string reference_number UK
        integer rooms_snapshot
        integer max_guests_snapshot
        boolean restaurant_snapshot
        string classification_outcome_snapshot
        datetime submitted_at
        datetime created_at
        datetime updated_at
    }

    APPLICATION_STATUS_HISTORY {
        bigint id PK
        bigint application_id FK
        bigint actor_id FK
        string from_status
        string to_status
        text reason
        datetime created_at
    }

    DOCUMENT_TYPE {
        bigint id PK
        string code UK
        string category
        bigint issuing_agency_id FK
        integer approximate_processing_days
        boolean allows_multiple_files
        boolean is_active
    }

    DOCUMENT_TYPE_TRANSLATION {
        bigint id PK
        bigint document_type_id FK
        string language_code
        string name
        text description
        text instructions
        text supporting_items
    }

    PROPERTY_TYPE_DOCUMENT_REQUIREMENT {
        bigint id PK
        bigint property_type_id FK
        bigint document_type_id FK
        boolean is_required
        string step_code
        integer display_order
        boolean is_active
    }

    APPLICATION_REQUIREMENT {
        bigint id PK
        bigint application_id FK
        bigint document_type_id FK
        boolean is_required
        string step_code
        integer display_order
        datetime captured_at
    }

    APPLICATION_DOCUMENT {
        bigint id PK
        bigint application_id FK
        bigint document_type_id FK
        integer version
        integer attachment_index
        string file_name
        string storage_key
        string mime_type
        bigint file_size
        string status
        bigint uploaded_by_id FK
        datetime uploaded_at
        boolean is_current
    }

    DOCUMENT_REVIEW {
        bigint id PK
        bigint application_document_id FK
        bigint reviewer_id FK
        string outcome
        text reason
        datetime reviewed_at
    }

    ISSUING_AGENCY {
        bigint id PK
        string code UK
        string contact_phone
        string contact_email
        string website_url
        boolean is_active
    }

    ISSUING_AGENCY_TRANSLATION {
        bigint id PK
        bigint issuing_agency_id FK
        string language_code
        string name
        text address
        text contact_notes
    }

    FEE_SCHEDULE {
        bigint id PK
        bigint property_type_id FK
        decimal amount
        string currency
        integer validity_years
        date effective_from
        date effective_to
    }

    LICENSE {
        bigint id PK
        bigint application_id FK
        string artifact_kind
        string license_number UK
        bigint property_type_id FK
        bigint fee_schedule_id FK
        decimal fee_amount_snapshot
        string fee_currency_snapshot
        integer validity_years_snapshot
        datetime issued_at
        date expires_at
    }

    AUDIT_LOG {
        bigint id PK
        bigint actor_id FK
        string action
        string object_type
        string object_id
        string from_status
        string to_status
        text reason
        datetime created_at
    }
```

Nullable FKs are marked by their relationships even though Mermaid's attribute list does not express nullability. In particular, `USER_ACCOUNT.local_authority_id` is required only for local officers; classification/property-type FKs are nullable for exemption, out-of-scope, and unresolved results; and an audit actor may be null only for a clearly identified system action.

## Core Design Decisions

### User roles without a role table

The MVP has four stable role codes: `APPLICANT`, `LOCAL_OFFICER`, `CENTRAL_OFFICER`, and `SUPER_ADMIN`. A constrained role field on a custom Django user is simpler than a role/permission graph. Django permissions still protect Admin operations. `local_authority_id` is required for an active local officer and must be null for roles that are not authority-scoped.

### Authority is retained on the application

`Property.local_authority_id` is the current property relationship. `Application.responsible_authority_id` is the routing snapshot used for authorization after submission. This intentional duplication prevents a later property edit from silently moving an in-flight application. Any administrative correction is audited.

### Classification is data-driven and explainable

`ClassificationRule` holds simple bounded conditions, priority, outcome, and an optional resulting property type. `REQUIRES_LICENSE_REVIEW` has no `result_property_type_id`. The application stores the selected rule plus the three input values and outcome snapshot so a later rule edit does not rewrite history.

This is not a generic expression language. The small evaluator understands the documented room/guest/restaurant columns and rejects ambiguous active configuration.

### Requirements use two relationship tables

`PropertyTypeDocumentRequirement` is editable master data. `ApplicationRequirement` is the application's captured checklist. It is created from active type requirements when an authenticated application with a confirmed type is established (and may be refreshed while still an untouched draft under one documented rule). It snapshots the preparation `step_code` together with required/order fields. Once submitted, it is fixed. This prevents a later Admin edit from adding, removing, or regrouping documents on an in-flight application without an audit trail.

`APPLICATION_REQUIREMENT` is the one entity beyond the brief's suggested list that directly protects historical correctness. It stores relationships and ordering, not copied document names or instructions.

### Document bytes and metadata are separate

File bytes live in configured Django storage. `ApplicationDocument` stores the opaque storage key plus validation/display metadata. Files selected together share a monotonically increasing bundle version and use `attachment_index` for their position in that bundle. Reviews target one exact attachment/version; replacement retains all prior bundle attachments.

### Translations are rows, not language columns

Property types, document types, and issuing agencies use child translation tables. Each table has a unique parent/language pair. Local authorities retain their statutory `official_name` for the MVP; if user-authored localized names become authoritative later, add a `LocalAuthorityTranslation` table using the same pattern rather than `name_en`, `name_my`, and similar columns.

### Fees are effective-dated and licenses snapshot them

Schedules are append-only/effective-dated master data. `License.artifact_kind` distinguishes a fee-bearing hotel licence from a non-hotel notification acknowledgement. A hotel licence keeps the schedule FK for provenance and amount/currency/validity snapshots for historical reproduction. Those fields and expiry are null for an acknowledgement. The property type FK records the confirmed processing type at issuance. The application-to-artifact relationship is zero-or-one.

### Audit is generic but deliberately small

`AuditLog.object_type` and `object_id` can refer to several workflow objects without creating one nullable FK per model. This controlled generic reference is appropriate for an append-only cross-cutting log. Domain tables retain their own strongly typed relationships for all functional behavior; no workflow query depends on the generic audit reference.

## Required Constraints and Indexes

Implement these database protections where supported, with matching application validation:

| Table | Constraint/index |
| --- | --- |
| `UserAccount` | unique normalized email; index `(role, local_authority_id)` |
| `PropertyTypeTranslation` | unique `(property_type_id, language_code)` |
| `DocumentTypeTranslation` | unique `(document_type_id, language_code)` |
| `IssuingAgencyTranslation` | unique `(issuing_agency_id, language_code)` |
| `ClassificationRule` | unique code; unique or validated active priority; nonnegative bounds and minimum ≤ maximum |
| `PropertyTypeDocumentRequirement` | unique `(property_type_id, document_type_id)` |
| `ApplicationRequirement` | unique `(application_id, document_type_id)` |
| `Application` | unique nullable reference number; indexes `(property_id, status)` and `(responsible_authority_id, status)` |
| `ApplicationDocument` | unique `(application_id, document_type_id, version, attachment_index)`; conditional unique current row per `(application_id, document_type_id, attachment_index)`; positive version/attachment index/file size |
| `FeeSchedule` | amount ≥ 0, validity years > 0, end ≥ start; prevent overlapping active periods for a property type/currency in validation/constraint |
| `License` | unique application; unique artifact number; hotel licence requires fee/validity/expiry while notification acknowledgement requires those fields to be null |
| Histories/audit | indexes by parent/object and descending `created_at`; no product update/delete endpoint |

Add indexes in response to actual list/filter paths, not speculatively. The authority/status and application/document paths above are known MVP queries.

## Deletion Policy

- Use `PROTECT` for master rows referenced by submitted applications, documents, fee schedules, or licenses.
- Prefer `is_active = false` over deletion for rules, types, agencies, authorities, and requirements.
- Never cascade-delete audit, status history, reviewed document versions, or an issued license through ordinary product behavior.
- Draft-only records may be deleted only if the product explicitly adds that flow; it is not required for the MVP.
- File cleanup must never remove historical document bytes still referenced by a version row.

## Transaction Boundaries

The following operations must be atomic:

- capture an application's requirements;
- allocate a document version and switch the current marker;
- submit and allocate a reference plus status history/audit;
- request revision or resubmit plus history/audit; and
- approve plus status/history/audit/license creation and fee snapshot.

Uniqueness constraints make retries/concurrency safe; domain functions turn resulting conflicts into clear API errors or idempotent responses.
