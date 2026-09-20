import pytest
from django.utils import timezone

from apps.core.exceptions import DomainError
from apps.core.models import (
    Application,
    ApplicationDocument,
    ApplicationStatusHistory,
    AuditLog,
    CentralAssistanceRequest,
    ClassificationRule,
    DiscussionMessage,
    DocumentReview,
    EmailOutbox,
    License,
    LocalAuthority,
    Property,
    PropertyType,
    User,
)
from apps.core.services import approve_application, capture_requirements, review_document


def create_reviewable_application(owner, authority):
    property_type = PropertyType.objects.get(code="TYPE_1")
    rule = ClassificationRule.objects.get(code="TYPE_1")
    property_record = Property.objects.create(
        owner=owner,
        local_authority=authority,
        property_type=property_type,
        name="Cross-authority authorization test",
        address_line="1 Fictional Road",
        subdistrict="Patong",
        district="Kathu",
        province="Phuket",
        postal_code="83150",
        rooms=20,
        max_guests=40,
        has_restaurant=False,
    )
    application = Application.objects.create(
        property=property_record,
        responsible_authority=authority,
        classification_rule=rule,
        confirmed_property_type=property_type,
        status=Application.Status.UNDER_REVIEW,
        reference_number=f"HTL-2026-{property_record.pk:05d}",
        rooms_snapshot=20,
        max_guests_snapshot=40,
        restaurant_snapshot=False,
        classification_outcome_snapshot=rule.outcome_code,
    )
    capture_requirements(application)
    documents = [
        ApplicationDocument.objects.create(
            application=application,
            document_type=requirement.document_type,
            version=1,
            attachment_index=1,
            original_filename=f"{requirement.document_type.code}.pdf",
            storage_key=f"tests/officer-scope/{application.pk}/{requirement.document_type_id}.pdf",
            content_type="application/pdf",
            size_bytes=100,
            status=ApplicationDocument.Status.APPROVED,
            uploaded_by=owner,
            is_current=True,
        )
        for requirement in application.requirements.filter(is_required=True)
    ]
    return application, documents


@pytest.mark.django_db
def test_cross_authority_officer_endpoints_return_404_without_side_effects(seeded, api_client):
    other_authority = (
        LocalAuthority.objects.exclude(pk=seeded["patong"].pk).filter(is_active=True).first()
    )
    other_officer = User.objects.create_user(
        email="authorized.other-area.officer@example.test",
        password="StrongPassword123!",
        display_name="Authorized other-area officer",
        role=User.Role.LOCAL_OFFICER,
        local_authority=other_authority,
        email_verified_at=timezone.now(),
    )
    application, documents = create_reviewable_application(seeded["applicant"], other_authority)
    document = documents[0]

    tracked_models = (
        ApplicationStatusHistory,
        AuditLog,
        DocumentReview,
        License,
        CentralAssistanceRequest,
        DiscussionMessage,
        EmailOutbox,
    )
    counts_before = {model: model.objects.count() for model in tracked_models}

    api_client.force_authenticate(seeded["officer"])
    queue_response = api_client.get("/api/v1/officer/applications/")
    assert queue_response.status_code == 200
    assert application.pk not in {item["id"] for item in queue_response.data["results"]}

    requests = (
        ("get", f"/api/v1/officer/applications/{application.pk}/", None),
        ("get", f"/api/v1/officer/documents/{document.pk}/file/", None),
        (
            "post",
            f"/api/v1/officer/documents/{document.pk}/review/",
            {"outcome": DocumentReview.Outcome.APPROVED, "reason": ""},
        ),
        ("post", f"/api/v1/officer/applications/{application.pk}/approve/", {"note": "Complete"}),
        (
            "post",
            f"/api/v1/officer/applications/{application.pk}/request-revision/",
            {"reason": "Replace a document"},
        ),
        (
            "post",
            f"/api/v1/officer/applications/{application.pk}/reject/",
            {"reason": "Not eligible"},
        ),
        (
            "post",
            f"/api/v1/officer/applications/{application.pk}/central-assistance/",
            {"question_code": "WORKFLOW_EXCEPTION"},
        ),
        ("get", f"/api/v1/officer/applications/{application.pk}/discussion/", None),
        (
            "post",
            f"/api/v1/officer/applications/{application.pk}/discussion/",
            {"body": "This message must not be created."},
        ),
    )
    for method, url, payload in requests:
        if payload is None:
            response = getattr(api_client, method)(url)
        else:
            response = getattr(api_client, method)(url, payload, format="json")
        assert response.status_code == 404, (method, url, response.data)
        assert response.data["error"]["code"] == "NOT_FOUND"

    application.refresh_from_db()
    document.refresh_from_db()
    assert application.status == Application.Status.UNDER_REVIEW
    assert document.status == ApplicationDocument.Status.APPROVED
    assert {model: model.objects.count() for model in tracked_models} == counts_before

    api_client.force_authenticate(other_officer)
    assert api_client.get(f"/api/v1/officer/applications/{application.pk}/").status_code == 200
    approval = api_client.post(
        f"/api/v1/officer/applications/{application.pk}/approve/",
        {"note": "Same-authority approval"},
        format="json",
    )
    assert approval.status_code == 200
    assert approval.data["status"] == Application.Status.APPROVED

    api_client.force_authenticate(seeded["officer"])
    license_response = api_client.get(f"/api/v1/applications/{application.pk}/license/")
    assert license_response.status_code == 404
    assert license_response.data["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_officer_services_scope_database_lookups_to_assigned_authority(seeded):
    other_authority = (
        LocalAuthority.objects.exclude(pk=seeded["patong"].pk).filter(is_active=True).first()
    )
    application, documents = create_reviewable_application(seeded["applicant"], other_authority)

    with pytest.raises(DomainError) as review_error:
        review_document(
            document_id=documents[0].pk,
            actor=seeded["officer"],
            outcome=DocumentReview.Outcome.APPROVED,
        )
    assert review_error.value.code == "NOT_FOUND"
    assert review_error.value.http_status == 404

    with pytest.raises(DomainError) as approval_error:
        approve_application(application_id=application.pk, actor=seeded["officer"])
    assert approval_error.value.code == "NOT_FOUND"
    assert approval_error.value.http_status == 404

    assert not DocumentReview.objects.filter(application_document__application=application).exists()
    assert not License.objects.filter(application=application).exists()
