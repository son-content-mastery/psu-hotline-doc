import io
import re
from datetime import date
from decimal import Decimal

import pytest
from PIL import Image
from django.core.exceptions import ValidationError
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.contrib import admin
from django.db import transaction
from django.db.models import Count
from django.test import Client, RequestFactory
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from django.urls import reverse
from pypdf import PdfWriter

from apps.core.exceptions import DomainError
from apps.core.models import (
    Application,
    ApplicationDocument,
    ApplicationStatusHistory,
    AuditLog,
    ClassificationRule,
    DocumentType,
    DocumentReview,
    EmailOutbox,
    FeeSchedule,
    License,
    LocalAuthority,
    Property,
    PropertyType,
    PropertyTypeDocumentRequirement,
    PropertyTypeTranslation,
    User,
)
from apps.core.services import (
    approve_application,
    capture_requirements,
    evaluate_classification,
    reject_application,
    request_application_revision,
    submit_application,
    validate_uploaded_file,
)
from apps.core.notifications import (
    deliver_email_outbox,
    make_activation_token,
    process_due_email_outbox,
    queue_activation_email,
)


def make_pdf(name="document.pdf", content_type="application/pdf", encrypted=False):
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("secret")
    writer.write(stream)
    return SimpleUploadedFile(name, stream.getvalue(), content_type=content_type)


def make_png(name="image.png", content_type="image/png"):
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(stream, "PNG")
    return SimpleUploadedFile(name, stream.getvalue(), content_type=content_type)


def create_application(owner, authority, *, status=Application.Status.DRAFT, type_code="TYPE_1", name="Test property"):
    property_type = PropertyType.objects.get(code=type_code)
    rule_code = "NOT_HOTEL" if type_code == "NON_HOTEL_NOTIFICATION" else type_code
    rule = ClassificationRule.objects.get(code=rule_code)
    is_non_hotel = type_code == "NON_HOTEL_NOTIFICATION"
    rooms = 6 if is_non_hotel else 20
    guests = 24 if is_non_hotel else 40
    property_record = Property.objects.create(
        owner=owner,
        local_authority=authority,
        property_type=property_type,
        name=name,
        address_line="1 Fictional Road",
        subdistrict="Patong",
        district="Kathu",
        province="Phuket",
        postal_code="83150",
        rooms=rooms,
        max_guests=guests,
        has_restaurant=type_code == "TYPE_2",
    )
    application = Application.objects.create(
        property=property_record,
        responsible_authority=authority,
        classification_rule=rule,
        confirmed_property_type=property_type,
        status=status,
        reference_number=None if status in {Application.Status.DRAFT, Application.Status.READY_TO_SUBMIT} else f"HTL-2026-{property_record.pk:05d}",
        rooms_snapshot=rooms,
        max_guests_snapshot=guests,
        restaurant_snapshot=type_code == "TYPE_2",
        classification_outcome_snapshot=rule.outcome_code,
    )
    capture_requirements(application)
    return application


def add_current_documents(application, *, document_status=ApplicationDocument.Status.UPLOADED):
    documents = []
    for requirement in application.requirements.filter(is_required=True):
        documents.append(
            ApplicationDocument.objects.create(
                application=application,
                document_type=requirement.document_type,
                version=1,
                original_filename=f"{requirement.document_type.code}.pdf",
                storage_key=f"test/{application.pk}/{requirement.document_type_id}.pdf",
                content_type="application/pdf",
                size_bytes=100,
                status=document_status,
                uploaded_by=application.property.owner,
                is_current=True,
            )
        )
    return documents


@pytest.mark.parametrize(
    ("rooms", "guests", "restaurant", "outcome", "requires_license"),
    [
        (6, 24, False, "NOT_HOTEL", False),
        (8, 36, False, "REQUIRES_LICENSE_REVIEW", True),
        (20, 40, False, "TYPE_1", True),
        (45, 80, True, "TYPE_2", True),
        (60, 80, False, "OUT_OF_SCOPE", True),
    ],
)
def test_public_classification_cases(seeded, api_client, rooms, guests, restaurant, outcome, requires_license):
    response = api_client.post(
        "/api/v1/classification/evaluate/",
        {"rooms": rooms, "guests": guests, "has_restaurant": restaurant},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["outcome"] == outcome
    assert response.data["requires_license"] is requires_license
    if outcome == "NOT_HOTEL":
        assert response.data["property_type"]["code"] == "NON_HOTEL_NOTIFICATION"
        assert response.data["property_type"]["issues_license"] is False
        assert response.data["fee"] is None
    if outcome == "REQUIRES_LICENSE_REVIEW":
        assert response.data["property_type"] is None
        assert response.data["fee"] is None
        assert response.data["needs_manual_classification_confirmation"] is True


def test_classification_and_fee_are_database_driven(seeded, api_client):
    fee = FeeSchedule.objects.get(property_type__code="TYPE_1", effective_from=date(2026, 1, 1))
    fee.amount = Decimal("12345.00")
    fee.save()
    response = api_client.post(
        "/api/v1/classification/evaluate/",
        {"rooms": 20, "guests": 40, "has_restaurant": False},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["fee"]["amount"] == "12345.00"


def test_overlapping_classification_configuration_fails_safely(seeded):
    ClassificationRule.objects.create(
        code="BAD_OVERLAP",
        priority=5,
        min_rooms=1,
        max_rooms=49,
        outcome_code=ClassificationRule.Outcome.NOT_HOTEL,
        is_active=True,
    )
    with pytest.raises(DomainError) as exc_info:
        evaluate_classification(rooms=20, max_guests=40, has_restaurant=False)
    assert exc_info.value.code == "NO_ACTIVE_CLASSIFICATION_RULE"


@pytest.mark.parametrize("value", ["true", "false", "yes", 1, 0])
def test_classification_requires_a_real_json_boolean(seeded, api_client, value):
    response = api_client.post(
        "/api/v1/classification/evaluate/",
        {"rooms": 20, "guests": 40, "has_restaurant": value},
        format="json",
    )
    assert response.status_code == 400
    assert "has_restaurant" in response.data["error"]["fields"]


def test_malformed_top_level_and_nested_payloads_return_validation_errors(seeded, api_client):
    response = api_client.post("/api/v1/classification/evaluate/", ["not", "an", "object"], format="json")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    api_client.force_authenticate(seeded["applicant"])
    response = api_client.post(
        "/api/v1/applications/",
        {
            "property": [],
            "classification_answers": {"rooms": 20, "guests": 40, "has_restaurant": False},
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


def test_translation_falls_back_to_thai_then_code(seeded, api_client):
    property_type = PropertyType.objects.get(code="TYPE_1")
    PropertyTypeTranslation.objects.filter(property_type=property_type, language_code="en").delete()
    response = api_client.get("/api/v1/property-types/", HTTP_ACCEPT_LANGUAGE="en")
    item = next(item for item in response.data["results"] if item["code"] == "TYPE_1")
    assert item["name"] == "ที่พักแรมประเภทที่ 1"
    assert item["translation_fallback"] is True
    PropertyTypeTranslation.objects.filter(property_type=property_type).delete()
    response = api_client.get("/api/v1/property-types/", HTTP_ACCEPT_LANGUAGE="en")
    item = next(item for item in response.data["results"] if item["code"] == "TYPE_1")
    assert item["name"] == "TYPE_1"


def test_application_create_re_evaluates_and_rejects_tampering(seeded, api_client):
    api_client.force_authenticate(seeded["applicant"])
    payload = {
        "property": {
            "name": "New fictional stay",
            "address_line": "22 Demo Road",
            "subdistrict": "Patong",
            "district": "Kathu",
            "province": "Phuket",
            "postal_code": "83150",
            "local_authority_id": seeded["patong"].id,
        },
        "classification_answers": {"rooms": 20, "guests": 40, "has_restaurant": False},
        "classification_outcome": "TYPE_2",
    }
    response = api_client.post("/api/v1/applications/", payload, format="json")
    assert response.status_code == 400
    assert "classification_outcome" in response.data["error"]["fields"]
    payload.pop("classification_outcome")
    response = api_client.post("/api/v1/applications/", payload, format="json")
    assert response.status_code == 201
    assert response.data["classification"]["outcome"] == "TYPE_1"
    application = Application.objects.get(pk=response.data["id"])
    assert application.property.owner == seeded["applicant"]
    assert application.requirements.count() > 0


def test_supplied_checklists_are_grouped_into_database_driven_steps(seeded, api_client):
    expected = {
        "TYPE_1": (28, {"APPLICANT", "PREMISES", "FACILITIES", "SAFETY", "MANAGER"}),
        "TYPE_2": (28, {"APPLICANT", "PREMISES", "FACILITIES", "SAFETY", "MANAGER"}),
        "NON_HOTEL_NOTIFICATION": (17, {"APPLICANT", "PREMISES", "FACILITIES", "SAFETY"}),
    }
    for code, (count, step_codes) in expected.items():
        property_type = PropertyType.objects.get(code=code)
        response = api_client.get(f"/api/v1/property-types/{property_type.id}/requirements/")
        assert response.status_code == 200
        assert sum(len(step["items"]) for step in response.data["steps"]) == count
        assert {step["code"] for step in response.data["steps"]} == step_codes
        assert sum(step["required"] for step in response.data["steps"]) == count


def test_missing_documents_block_submission_without_side_effects(seeded, api_client):
    application = create_application(seeded["applicant"], seeded["patong"], name="Incomplete")
    api_client.force_authenticate(seeded["applicant"])
    history_before = ApplicationStatusHistory.objects.filter(application=application).count()
    audit_before = AuditLog.objects.filter(object_id=str(application.id), object_type="core.Application").count()
    response = api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "MISSING_REQUIRED_DOCUMENTS"
    application.refresh_from_db()
    assert application.status == Application.Status.DRAFT
    assert application.reference_number is None
    assert ApplicationStatusHistory.objects.filter(application=application).count() == history_before
    assert AuditLog.objects.filter(object_id=str(application.id), object_type="core.Application").count() == audit_before


def test_complete_uploads_mark_ready_and_submit_once(seeded, api_client):
    application = create_application(seeded["applicant"], seeded["patong"], name="Complete")
    api_client.force_authenticate(seeded["applicant"])
    requirements = list(application.requirements.all())
    for requirement in requirements:
        response = api_client.post(
            f"/api/v1/applications/{application.id}/documents/",
            {"document_type_id": requirement.document_type_id, "file": make_pdf()},
            format="multipart",
        )
        assert response.status_code == 201
    application.refresh_from_db()
    assert application.status == Application.Status.READY_TO_SUBMIT
    history_before_submit = application.status_history.count()
    response = api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["reference_number"].startswith("HTL-")
    application.refresh_from_db()
    assert application.status == Application.Status.SUBMITTED
    assert application.status_history.count() == history_before_submit + 1
    reference = application.reference_number
    response = api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    )
    assert response.status_code == 409
    application.refresh_from_db()
    assert application.reference_number == reference
    assert application.status_history.count() == history_before_submit + 1


def test_first_submit_refreshes_changed_master_requirements(seeded, api_client):
    application = create_application(seeded["applicant"], seeded["patong"], name="Changing checklist")
    add_current_documents(application)
    application.status = Application.Status.READY_TO_SUBMIT
    application.save(update_fields=["status"])
    new_type = DocumentType.objects.get(code="NON_HOTEL_NOTIFICATION_FORM")
    assert not application.requirements.filter(document_type=new_type).exists()
    PropertyTypeDocumentRequirement.objects.update_or_create(
        property_type=application.confirmed_property_type,
        document_type=new_type,
        defaults={"is_required": True, "is_active": True, "display_order": 99},
    )
    api_client.force_authenticate(seeded["applicant"])
    response = api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "REQUIREMENTS_CHANGED"
    application.refresh_from_db()
    assert application.status == Application.Status.DRAFT
    assert application.reference_number is None
    assert application.requirements.filter(document_type=new_type, is_required=True).exists()


def test_applicant_ownership_and_protected_patch_are_enforced(seeded, api_client):
    other = User.objects.create_user(email="other@example.test", password="pass", display_name="Other")
    application = create_application(seeded["applicant"], seeded["patong"], name="Private")
    document = add_current_documents(application)[0]
    api_client.force_authenticate(other)
    urls = [
        f"/api/v1/applications/{application.id}/",
        f"/api/v1/applications/{application.id}/requirements/",
        f"/api/v1/applications/{application.id}/history/",
        f"/api/v1/applications/{application.id}/documents/",
        f"/api/v1/applications/{application.id}/documents/{document.id}/file/",
        f"/api/v1/applications/{application.id}/license/",
    ]
    for url in urls:
        assert api_client.get(url).status_code == 404
    assert api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    ).status_code == 404
    api_client.force_authenticate(seeded["applicant"])
    response = api_client.patch(
        f"/api/v1/applications/{application.id}/", {"status": "APPROVED"}, format="json"
    )
    assert response.status_code == 400
    application.refresh_from_db()
    assert application.status == Application.Status.DRAFT


def test_local_officer_scope_and_draft_privacy(seeded, api_client):
    other_authority = LocalAuthority.objects.exclude(pk=seeded["patong"].pk).first()
    other_officer = User.objects.create_user(
        email="other.officer@example.test",
        password="pass",
        display_name="Other officer",
        role=User.Role.LOCAL_OFFICER,
        local_authority=other_authority,
    )
    submitted = create_application(
        seeded["applicant"], other_authority, status=Application.Status.SUBMITTED, name="Other authority"
    )
    draft = create_application(seeded["applicant"], seeded["patong"], name="Unsubmitted private draft")
    draft_document = add_current_documents(draft)[0]
    api_client.force_authenticate(seeded["officer"])
    assert api_client.get(f"/api/v1/officer/applications/{submitted.id}/").status_code == 404
    assert api_client.post(
        f"/api/v1/officer/applications/{submitted.id}/reject/", {"reason": "No"}, format="json"
    ).status_code == 404
    assert api_client.get(f"/api/v1/officer/applications/{draft.id}/").status_code == 404
    assert api_client.get(f"/api/v1/officer/documents/{draft_document.id}/file/").status_code == 404
    api_client.force_authenticate(other_officer)
    assert api_client.get(f"/api/v1/officer/applications/{submitted.id}/").status_code == 200


def test_replacement_creates_immutable_document_version(seeded, api_client):
    application = create_application(seeded["applicant"], seeded["patong"], name="Versions")
    requirement = application.requirements.first()
    api_client.force_authenticate(seeded["applicant"])
    first = api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {"document_type_id": requirement.document_type_id, "file": make_pdf("first.pdf")},
        format="multipart",
    )
    second = api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {"document_type_id": requirement.document_type_id, "file": make_pdf("second.pdf")},
        format="multipart",
    )
    assert first.status_code == second.status_code == 201
    versions = list(
        ApplicationDocument.objects.filter(application=application, document_type=requirement.document_type).order_by("version")
    )
    assert [item.version for item in versions] == [1, 2]
    assert [item.is_current for item in versions] == [False, True]
    assert versions[0].storage_key != versions[1].storage_key


@pytest.mark.parametrize(
    "upload,expected",
    [
        (SimpleUploadedFile("bad.exe", b"MZ", content_type="application/octet-stream"), 415),
        (SimpleUploadedFile("fake.pdf", b"not a pdf", content_type="application/pdf"), 415),
        (make_png(content_type="application/pdf"), 415),
        (make_pdf(encrypted=True), 415),
        (SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf"), 400),
    ],
)
def test_upload_validation_rejects_unsafe_files(seeded, api_client, upload, expected):
    application = create_application(seeded["applicant"], seeded["patong"], name=f"Upload {upload.name}")
    requirement = application.requirements.first()
    api_client.force_authenticate(seeded["applicant"])
    response = api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {"document_type_id": requirement.document_type_id, "file": upload},
        format="multipart",
    )
    assert response.status_code == expected
    assert not ApplicationDocument.objects.filter(application=application).exists()


def test_upload_validation_rejects_oversize_and_path_names(seeded, settings):
    oversized = SimpleUploadedFile(
        "large.pdf", b"%PDF-" + b"x" * settings.MAX_UPLOAD_SIZE_BYTES, content_type="application/pdf"
    )
    with pytest.raises(DomainError) as exc_info:
        validate_uploaded_file(oversized)
    assert exc_info.value.code == "FILE_TOO_LARGE"

    class PathUpload:
        name = "../secret.pdf"
        size = 20
        content_type = "application/pdf"

    with pytest.raises(DomainError) as exc_info:
        validate_uploaded_file(PathUpload())
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_upload_validation_rejects_decompression_bomb(monkeypatch):
    upload = make_png("oversized-dimensions.png")

    def raise_bomb(*args, **kwargs):
        raise Image.DecompressionBombError("synthetic oversized image")

    monkeypatch.setattr("apps.core.services.Image.open", raise_bomb)
    with pytest.raises(DomainError) as exc_info:
        validate_uploaded_file(upload)
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


def test_upload_bundle_rejects_more_than_ten_files(seeded, api_client):
    application = create_application(seeded["applicant"], seeded["patong"], name="Oversized bundle")
    requirement = application.requirements.get(document_type__code="PARKING_PHOTOS")
    api_client.force_authenticate(seeded["applicant"])

    response = api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {
            "document_type_id": requirement.document_type_id,
            "files": [make_png(f"parking-{index}.png") for index in range(11)],
        },
        format="multipart",
    )

    assert response.status_code == 400
    assert not ApplicationDocument.objects.filter(application=application).exists()


def test_photo_requirement_accepts_a_versioned_multi_file_bundle(seeded, api_client):
    application = create_application(seeded["applicant"], seeded["patong"], name="Photo bundle")
    requirement = application.requirements.get(document_type__code="PARKING_PHOTOS")
    assert requirement.document_type.allows_multiple_files is True
    api_client.force_authenticate(seeded["applicant"])

    response = api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {
            "document_type_id": requirement.document_type_id,
            "files": [make_png("parking-1.png"), make_png("parking-2.png")],
        },
        format="multipart",
    )
    assert response.status_code == 201
    assert response.data["bundle_count"] == 2
    first_bundle = application.documents.filter(document_type=requirement.document_type, is_current=True)
    assert first_bundle.count() == 2
    assert set(first_bundle.values_list("attachment_index", flat=True)) == {1, 2}
    assert set(first_bundle.values_list("version", flat=True)) == {1}

    response = api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {"document_type_id": requirement.document_type_id, "file": make_png("parking-new.png")},
        format="multipart",
    )
    assert response.status_code == 201
    current = application.documents.get(document_type=requirement.document_type, is_current=True)
    assert current.version == 2
    assert current.attachment_index == 1
    assert application.documents.filter(document_type=requirement.document_type, is_current=False).count() == 2


def test_revision_resubmission_preserves_history_and_reference(seeded, api_client):
    application = create_application(
        seeded["applicant"], seeded["patong"], status=Application.Status.UNDER_REVIEW, name="Revision flow"
    )
    documents = add_current_documents(application)
    original_reference = application.reference_number
    api_client.force_authenticate(seeded["officer"])
    response = api_client.post(
        f"/api/v1/officer/documents/{documents[0].id}/review/",
        {"outcome": "REVISION_REQUIRED", "reason": "Image is unclear"},
        format="json",
    )
    assert response.status_code == 201
    response = api_client.post(
        f"/api/v1/officer/applications/{application.id}/request-revision/",
        {"reason": "Replace one unclear document"},
        format="json",
    )
    assert response.status_code == 200
    assert ApplicationStatusHistory.objects.filter(application=application, to_status="REVISION_REQUIRED").count() == 1
    assert AuditLog.objects.filter(object_id=str(application.id), action="APPLICATION_REVISION_REQUESTED").count() == 1
    api_client.force_authenticate(seeded["applicant"])
    history_response = api_client.get(f"/api/v1/applications/{application.id}/history/")
    revision_event = next(event for event in history_response.data["events"] if event["to_status"] == "REVISION_REQUIRED")
    assert revision_event["actor_category"] == User.Role.LOCAL_OFFICER
    assert revision_event["document_type"]["id"] == documents[0].document_type_id
    assert revision_event["affected_documents"] == [revision_event["document_type"]]
    requirement_id = documents[0].document_type_id
    response = api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {"document_type_id": requirement_id, "file": make_pdf("replacement.pdf")},
        format="multipart",
    )
    assert response.status_code == 201
    application.refresh_from_db()
    assert application.status == Application.Status.REVISION_REQUIRED
    response = api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    )
    assert response.status_code == 200
    application.refresh_from_db()
    assert application.status == Application.Status.RESUBMITTED
    assert application.reference_number == original_reference
    assert application.resubmitted_at is not None
    assert ApplicationDocument.objects.filter(application=application, document_type_id=requirement_id).count() == 2


def test_revision_and_rejection_reasons_are_required(seeded, api_client):
    application = create_application(
        seeded["applicant"], seeded["patong"], status=Application.Status.UNDER_REVIEW, name="Reasons"
    )
    document = add_current_documents(application)[0]
    api_client.force_authenticate(seeded["officer"])
    response = api_client.post(
        f"/api/v1/officer/documents/{document.id}/review/",
        {"outcome": "REVISION_REQUIRED", "reason": "   "},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "REASON_REQUIRED"
    assert not DocumentReview.objects.filter(application_document=document).exists()
    for action in ("request-revision", "reject"):
        response = api_client.post(
            f"/api/v1/officer/applications/{application.id}/{action}/", {"reason": ""}, format="json"
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "REASON_REQUIRED"


def test_mixed_rejected_and_revision_documents_cannot_deadlock_applicant(seeded, api_client):
    application = create_application(
        seeded["applicant"], seeded["patong"], status=Application.Status.UNDER_REVIEW, name="Mixed reviews"
    )
    documents = add_current_documents(application)
    documents[0].status = ApplicationDocument.Status.REVISION_REQUIRED
    documents[0].save(update_fields=["status"])
    documents[1].status = ApplicationDocument.Status.REJECTED
    documents[1].save(update_fields=["status"])
    api_client.force_authenticate(seeded["officer"])
    response = api_client.post(
        f"/api/v1/officer/applications/{application.id}/request-revision/",
        {"reason": "Mixed outcomes"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "DOCUMENTS_REJECTED"
    application.refresh_from_db()
    assert application.status == Application.Status.UNDER_REVIEW


def test_invalid_transition_has_no_partial_side_effects(seeded):
    application = create_application(seeded["applicant"], seeded["patong"], name="Invalid transition")
    before_history = application.status_history.count()
    before_audit = AuditLog.objects.count()
    with pytest.raises(DomainError) as exc_info:
        approve_application(application_id=application.id, actor=seeded["officer"])
    assert exc_info.value.code == "INVALID_STATUS_TRANSITION"
    application.refresh_from_db()
    assert application.status == Application.Status.DRAFT
    assert application.status_history.count() == before_history
    assert AuditLog.objects.count() == before_audit
    assert not License.objects.filter(application=application).exists()


def test_approval_creates_one_historical_fee_snapshot(seeded, api_client):
    application = create_application(
        seeded["applicant"], seeded["patong"], status=Application.Status.UNDER_REVIEW, name="Approval"
    )
    add_current_documents(application, document_status=ApplicationDocument.Status.APPROVED)
    fee = FeeSchedule.objects.get(property_type=application.confirmed_property_type, effective_from=date(2026, 1, 1))
    expected_fee = fee.amount
    api_client.force_authenticate(seeded["officer"])
    response = api_client.post(
        f"/api/v1/officer/applications/{application.id}/approve/", {"note": "Complete"}, format="json"
    )
    assert response.status_code == 200
    application.refresh_from_db()
    assert application.status == Application.Status.APPROVED
    license_record = License.objects.get(application=application)
    assert license_record.fee_schedule == fee
    assert license_record.fee_amount_snapshot == expected_fee
    fee.amount = Decimal("99999.00")
    fee.save()
    license_record.refresh_from_db()
    assert license_record.fee_amount_snapshot == expected_fee
    history_count = application.status_history.count()
    response = api_client.post(f"/api/v1/officer/applications/{application.id}/approve/", {}, format="json")
    assert response.status_code == 409
    assert License.objects.filter(application=application).count() == 1
    assert application.status_history.count() == history_count


def test_non_hotel_approval_creates_notification_acknowledgement_without_fee(seeded, api_client):
    application = create_application(
        seeded["applicant"],
        seeded["patong"],
        status=Application.Status.UNDER_REVIEW,
        type_code="NON_HOTEL_NOTIFICATION",
        name="Notification acknowledgement",
    )
    assert application.requirements.count() == 17
    add_current_documents(application, document_status=ApplicationDocument.Status.APPROVED)
    api_client.force_authenticate(seeded["officer"])
    response = api_client.post(
        f"/api/v1/officer/applications/{application.id}/approve/",
        {"note": "Notification complete"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["license"]["artifact_kind"] == License.ArtifactKind.NOTIFICATION_ACKNOWLEDGEMENT
    assert response.data["license"]["fee_amount_snapshot"] is None
    record = License.objects.get(application=application)
    assert record.license_number.startswith("ACK-")
    assert record.fee_schedule is None
    assert record.expires_at is None

    api_client.force_authenticate(seeded["applicant"])
    printable = api_client.get(f"/api/v1/applications/{application.id}/license/")
    assert printable.status_code == 200
    assert printable.data["artifact_kind"] == License.ArtifactKind.NOTIFICATION_ACKNOWLEDGEMENT
    assert printable.data["fee"] is None


def test_approval_prerequisites_fail_atomically(seeded, api_client):
    application = create_application(
        seeded["applicant"], seeded["patong"], status=Application.Status.UNDER_REVIEW, name="Pending docs"
    )
    add_current_documents(application, document_status=ApplicationDocument.Status.UPLOADED)
    api_client.force_authenticate(seeded["officer"])
    response = api_client.post(f"/api/v1/officer/applications/{application.id}/approve/", {}, format="json")
    assert response.status_code == 409
    assert response.data["error"]["code"] == "DOCUMENTS_NOT_APPROVED"
    application.refresh_from_db()
    assert application.status == Application.Status.UNDER_REVIEW
    assert not License.objects.filter(application=application).exists()


def test_approval_requires_an_unambiguous_effective_fee(seeded, api_client):
    application = create_application(
        seeded["applicant"],
        seeded["patong"],
        status=Application.Status.UNDER_REVIEW,
        type_code="TYPE_2",
        name="No fee",
    )
    add_current_documents(application, document_status=ApplicationDocument.Status.APPROVED)
    FeeSchedule.objects.filter(property_type=application.confirmed_property_type).delete()
    api_client.force_authenticate(seeded["officer"])
    response = api_client.post(f"/api/v1/officer/applications/{application.id}/approve/", {}, format="json")
    assert response.status_code == 409
    assert response.data["error"]["code"] == "FEE_SCHEDULE_NOT_FOUND"
    application.refresh_from_db()
    assert application.status == Application.Status.UNDER_REVIEW
    assert not License.objects.filter(application=application).exists()


def test_domain_services_recheck_scope_after_lock(seeded):
    other_applicant = User.objects.create_user(email="scope@example.test", password="pass", display_name="Scope")
    ready = create_application(seeded["applicant"], seeded["patong"], name="Scope submit")
    add_current_documents(ready)
    ready.status = Application.Status.READY_TO_SUBMIT
    ready.save(update_fields=["status"])
    with pytest.raises(DomainError) as exc_info:
        submit_application(application_id=ready.id, actor=other_applicant)
    assert exc_info.value.code == "NOT_FOUND"

    other_authority = LocalAuthority.objects.exclude(pk=seeded["patong"].pk).first()
    other_officer = User.objects.create_user(
        email="scope.officer@example.test",
        password="pass",
        display_name="Scope officer",
        role=User.Role.LOCAL_OFFICER,
        local_authority=other_authority,
    )
    reviewable = create_application(
        seeded["applicant"], seeded["patong"], status=Application.Status.UNDER_REVIEW, name="Scope approval"
    )
    add_current_documents(reviewable, document_status=ApplicationDocument.Status.APPROVED)
    with pytest.raises(DomainError) as exc_info:
        approve_application(application_id=reviewable.id, actor=other_officer)
    assert exc_info.value.code == "NOT_FOUND"


def test_central_summary_is_aggregate_only_and_role_separated(seeded, api_client):
    expected_total = Application.objects.count()
    expected_waiting = Application.objects.filter(
        status__in=[Application.Status.SUBMITTED, Application.Status.UNDER_REVIEW, Application.Status.RESUBMITTED]
    ).count()
    expected_revision = Application.objects.filter(status=Application.Status.REVISION_REQUIRED).count()
    expected_approved = Application.objects.filter(status=Application.Status.APPROVED).count()
    api_client.force_authenticate(seeded["central"])
    response = api_client.get("/api/v1/central/summary/")
    assert response.status_code == 200
    assert response.data["totals"] == {
        "applications": expected_total,
        "waiting_review": expected_waiting,
        "waiting_for_applicant_revision": expected_revision,
        "approved": expected_approved,
    }
    assert response.data["authority_zeroes_included"] is True
    assert len(response.data["by_local_authority"]) == LocalAuthority.objects.filter(is_active=True).count()
    assert all(item["count"] > 0 for item in response.data["by_local_authority"])
    for item in response.data["by_local_authority"]:
        assert item["totals"]["applications"] == item["count"]
        assert sum(entry["count"] for entry in item["by_property_type"]) == item["count"]
        assert sum(entry["count"] for entry in item["by_current_stage"]) == item["count"]
    assert "email" not in str(response.data).lower()
    sample = Application.objects.first()
    assert api_client.get(f"/api/v1/officer/applications/{sample.id}/").status_code == 403
    api_client.force_authenticate(seeded["officer"])
    assert api_client.get("/api/v1/central/summary/").status_code == 403


def test_database_driven_checklist_and_external_guidance(seeded, api_client):
    property_type = PropertyType.objects.get(code="TYPE_1")
    response = api_client.get(
        f"/api/v1/property-types/{property_type.id}/requirements/", HTTP_ACCEPT_LANGUAGE="en"
    )
    assert response.status_code == 200
    assert response.data["is_legally_validated_checklist"] is False
    categories = {group["category"]: group for group in response.data["groups"]}
    assert categories["OPERATOR_PREPARED"]["items"]
    external = categories["EXTERNAL_AGENCY"]["items"]
    assert external
    assert external[0]["document_type"]["description"]
    assert external[0]["document_type"]["instructions"]
    assert external[0]["description"]
    assert external[0]["instructions"]
    assert external[0]["guidance"]["issuing_agency"]["code"].startswith("DEMO_")
    assert all(item["guidance"]["required_supporting_items"] for item in external)
    assert all(item["guidance"]["approximate_processing_days"] > 0 for item in external)
    assert external[0]["guidance"]["instructions"]
    assert external[0]["guidance"]["source_url"].startswith("https://example.test/")


def test_officer_timing_actions_and_grouped_document_versions(seeded, api_client):
    application = create_application(
        seeded["applicant"], seeded["patong"], status=Application.Status.RESUBMITTED, name="Officer response"
    )
    application.submitted_at = timezone.now()
    application.resubmitted_at = timezone.now()
    application.save(update_fields=["submitted_at", "resubmitted_at"])
    documents = add_current_documents(application)
    first = documents[0]
    first.is_current = False
    first.status = ApplicationDocument.Status.REVISION_REQUIRED
    first.save(update_fields=["is_current", "status"])
    DocumentReview.objects.create(
        application_document=first,
        reviewer=seeded["officer"],
        outcome=DocumentReview.Outcome.REVISION_REQUIRED,
        reason="Prior copy unclear",
    )
    replacement = ApplicationDocument.objects.create(
        application=application,
        document_type=first.document_type,
        version=2,
        original_filename="replacement.pdf",
        storage_key=f"test/{application.pk}/{first.document_type_id}-v2.pdf",
        content_type="application/pdf",
        size_bytes=200,
        status=ApplicationDocument.Status.UPLOADED,
        uploaded_by=seeded["applicant"],
        is_current=True,
    )
    api_client.force_authenticate(seeded["officer"])
    queue = api_client.get("/api/v1/officer/applications/")
    queue_item = next(item for item in queue.data["results"] if item["id"] == application.id)
    assert queue_item["submitted_at"] is not None
    assert queue_item["resubmitted_at"] is not None
    assert queue_item["waiting_since"] is not None

    response = api_client.get(f"/api/v1/officer/applications/{application.id}/")
    assert response.status_code == 200
    assert response.data["submitted_at"] is not None
    assert response.data["resubmitted_at"] is not None
    assert response.data["waiting_since"] is not None
    assert response.data["allowed_actions"] == ["REVIEW_DOCUMENTS"]
    current = next(item for item in response.data["documents"] if item["id"] == replacement.id)
    assert current["is_current"] is True
    assert current["version_label"] == "CURRENT"
    assert current["category"] in {"OPERATOR_PREPARED", "EXTERNAL_AGENCY"}
    assert current["uploaded_by"]["role"] == User.Role.APPLICANT
    assert current["uploaded_at"] is not None
    assert len(current["versions"]) == 1
    assert current["versions"][0]["id"] == first.id
    assert current["versions"][0]["is_current"] is False
    assert current["versions"][0]["version_label"] == "PRIOR"

    application.status = Application.Status.UNDER_REVIEW
    application.save(update_fields=["status"])
    ApplicationDocument.objects.filter(application=application, is_current=True).update(
        status=ApplicationDocument.Status.APPROVED
    )
    response = api_client.get(f"/api/v1/officer/applications/{application.id}/")
    assert response.data["allowed_actions"] == ["APPROVE", "REJECT"]


def test_openapi_describes_enriched_officer_and_requirement_payloads(seeded):
    schema = SchemaGenerator().get_schema(request=None, public=True)
    schemas = schema["components"]["schemas"]
    officer_properties = schemas["OfficerApplicationDetailOutput"]["properties"]
    assert {"waiting_since", "submitted_at", "resubmitted_at", "documents", "allowed_actions"} <= set(
        officer_properties
    )
    document_properties = schemas["OfficerDocumentOutput"]["properties"]
    assert {"uploaded_at", "uploaded_by", "category", "version_label", "versions"} <= set(document_properties)
    requirement_properties = schemas["RequirementItemOutput"]["properties"]
    assert {"description", "instructions", "guidance"} <= set(requirement_properties)
    applicant_properties = schemas["ApplicantApplicationListItemOutput"]["properties"]
    assert {"property_type", "responsible_authority", "requirements"} <= set(applicant_properties)
    assert "new_password" not in schemas["PasswordResetCompleteOutput"]["properties"]


def test_complete_applicant_officer_license_and_central_flow(seeded, api_client):
    application = create_application(seeded["applicant"], seeded["patong"], name="End-to-end demo")
    api_client.force_authenticate(seeded["applicant"])
    for requirement in application.requirements.all():
        response = api_client.post(
            f"/api/v1/applications/{application.id}/documents/",
            {"document_type_id": requirement.document_type_id, "file": make_pdf(f"{requirement.document_type.code}.pdf")},
            format="multipart",
        )
        assert response.status_code == 201
    response = api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    )
    assert response.status_code == 200
    reference = response.data["reference_number"]

    api_client.force_authenticate(seeded["officer"])
    current_documents = list(application.documents.filter(is_current=True).order_by("id"))
    for index, document in enumerate(current_documents):
        outcome = "REVISION_REQUIRED" if index == 0 else "APPROVED"
        review_payload = {"outcome": outcome}
        if index == 0:
            review_payload["reason"] = "Please upload a clearer copy"
        assert api_client.post(
            f"/api/v1/officer/documents/{document.id}/review/", review_payload, format="json"
        ).status_code == 201
    assert api_client.post(
        f"/api/v1/officer/applications/{application.id}/request-revision/",
        {"reason": "One document needs a clearer copy"},
        format="json",
    ).status_code == 200

    api_client.force_authenticate(seeded["applicant"])
    revised_type_id = current_documents[0].document_type_id
    assert api_client.post(
        f"/api/v1/applications/{application.id}/documents/",
        {"document_type_id": revised_type_id, "file": make_pdf("clear-copy.pdf")},
        format="multipart",
    ).status_code == 201
    assert api_client.post(
        f"/api/v1/applications/{application.id}/submit/",
        {"confirm_information_is_correct": True},
        format="json",
    ).status_code == 200

    api_client.force_authenticate(seeded["officer"])
    replacement = application.documents.get(document_type_id=revised_type_id, is_current=True)
    assert api_client.post(
        f"/api/v1/officer/documents/{replacement.id}/review/", {"outcome": "APPROVED"}, format="json"
    ).status_code == 201
    assert api_client.post(
        f"/api/v1/officer/applications/{application.id}/approve/", {"note": "All complete"}, format="json"
    ).status_code == 200

    api_client.force_authenticate(seeded["applicant"])
    license_response = api_client.get(f"/api/v1/applications/{application.id}/license/")
    assert license_response.status_code == 200
    assert license_response.data["application_reference_number"] == reference
    assert license_response.data["fee"]["amount_snapshot"] == "10000.00"

    api_client.force_authenticate(seeded["central"])
    summary = api_client.get("/api/v1/central/summary/")
    assert summary.status_code == 200
    assert summary.data["totals"]["approved"] == Application.objects.filter(status="APPROVED").count()


def test_session_csrf_login_bootstrap_and_logout(seeded, settings):
    client = Client(enforce_csrf_checks=True)
    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.json() == {"authenticated": False, "user": None}
    csrf_token = client.cookies["csrftoken"].value
    missing_csrf = client.post(
        "/api/v1/auth/login/",
        {"email": "applicant@example.test", "password": "DemoPass123!"},
        content_type="application/json",
    )
    assert missing_csrf.status_code == 403
    response = client.post(
        "/api/v1/auth/login/",
        {"email": "applicant@example.test", "password": "DemoPass123!"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert response.status_code == 200
    assert client.cookies[settings.SESSION_COOKIE_NAME]["httponly"] is True
    me = client.get("/api/v1/auth/me/")
    assert me.json()["authenticated"] is True
    missing_unsafe_csrf = client.post("/api/v1/auth/logout/", {}, content_type="application/json")
    assert missing_unsafe_csrf.status_code == 403
    csrf_token = client.cookies["csrftoken"].value
    assert client.post(
        "/api/v1/auth/logout/", {}, content_type="application/json", HTTP_X_CSRFTOKEN=csrf_token
    ).status_code == 204
    assert client.get("/api/v1/auth/me/").json()["authenticated"] is False


def test_registration_activation_and_verified_login(db, settings):
    settings.FRONTEND_BASE_URL = "http://frontend.test"
    mail.outbox.clear()
    client = Client(enforce_csrf_checks=True)
    client.get("/api/v1/auth/me/")
    csrf_token = client.cookies["csrftoken"].value
    payload = {
        "display_name": "New Applicant",
        "email": "new.applicant@example.test",
        "password": "StrongRegistrationPass123!",
        "password_confirmation": "StrongRegistrationPass123!",
        "language": "en",
        "terms_accepted": True,
    }

    response = client.post(
        "/api/v1/auth/register/",
        payload,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    user = User.objects.get(email="new.applicant@example.test")
    assert user.role == User.Role.APPLICANT
    assert user.local_authority_id is None
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.preferred_language == User.Language.ENGLISH
    assert user.email_verified_at is None
    assert user.check_password(payload["password"])
    assert AuditLog.objects.filter(actor=user, action="USER_REGISTERED").exists()

    login_before_activation = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": payload["password"]},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert login_before_activation.status_code == 403
    assert login_before_activation.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    outbox = EmailOutbox.objects.get(recipient=user, template_code=EmailOutbox.Template.ACCOUNT_ACTIVATION)
    assert deliver_email_outbox(outbox.pk) is True
    outbox.refresh_from_db()
    assert outbox.status == EmailOutbox.Status.SENT
    assert len(mail.outbox) == 1
    assert "new.applicant@example.test" not in mail.outbox[0].body
    match = re.search(r"token=([^\s]+)", mail.outbox[0].body)
    assert match
    token = match.group(1)

    activated = client.post(
        "/api/v1/auth/activation/confirm/",
        {"token": token},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert activated.status_code == 200
    assert activated.json() == {"activated": True}
    user.refresh_from_db()
    assert user.email_verified_at is not None
    assert AuditLog.objects.filter(actor=user, action="USER_EMAIL_VERIFIED").exists()

    reused = client.post(
        "/api/v1/auth/activation/confirm/",
        {"token": token},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "ACTIVATION_INVALID"

    logged_in = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": payload["password"]},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert logged_in.status_code == 200


def test_registration_rejects_role_mass_assignment_and_weak_input(db):
    client = Client(enforce_csrf_checks=True)
    client.get("/api/v1/auth/me/")
    csrf_token = client.cookies["csrftoken"].value
    response = client.post(
        "/api/v1/auth/register/",
        {
            "display_name": "Attempted Admin",
            "email": "attempted.admin@example.test",
            "password": "StrongRegistrationPass123!",
            "password_confirmation": "StrongRegistrationPass123!",
            "language": "th",
            "terms_accepted": True,
            "role": "SUPER_ADMIN",
        },
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert response.status_code == 400
    assert "role" in response.json()["error"]["fields"]
    assert not User.objects.filter(email="attempted.admin@example.test").exists()


def test_registration_and_activation_resend_do_not_enumerate_accounts(db):
    user = User.objects.create_user(
        email="pending@example.test",
        password="StrongRegistrationPass123!",
        display_name="Pending Applicant",
    )
    client = Client(enforce_csrf_checks=True)
    client.get("/api/v1/auth/me/")
    csrf_token = client.cookies["csrftoken"].value

    unknown = client.post(
        "/api/v1/auth/activation/resend/",
        {"email": "unknown@example.test"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    existing = client.post(
        "/api/v1/auth/activation/resend/",
        {"email": user.email},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert unknown.status_code == existing.status_code == 202
    assert unknown.json() == existing.json() == {"accepted": True}
    assert EmailOutbox.objects.filter(recipient=user).count() == 1

    duplicate_payload = {
        "display_name": "Different Name",
        "email": user.email,
        "password": "AnotherStrongRegistrationPass123!",
        "password_confirmation": "AnotherStrongRegistrationPass123!",
        "language": "en",
        "terms_accepted": True,
    }
    duplicate = client.post(
        "/api/v1/auth/register/",
        duplicate_payload,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert duplicate.status_code == 202
    assert User.objects.filter(email=user.email).count() == 1
    user.refresh_from_db()
    assert user.display_name == "Pending Applicant"
    assert user.check_password("StrongRegistrationPass123!")


def test_activation_token_expires_and_email_change_invalidates_it(db, settings):
    user = User.objects.create_user(
        email="expiring@example.test",
        password="StrongRegistrationPass123!",
        display_name="Expiring Applicant",
    )
    token = make_activation_token(user)
    settings.ACCOUNT_ACTIVATION_TOKEN_MAX_AGE_SECONDS = -1
    client = Client(enforce_csrf_checks=True)
    client.get("/api/v1/auth/me/")
    csrf_token = client.cookies["csrftoken"].value
    expired = client.post(
        "/api/v1/auth/activation/confirm/",
        {"token": token},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "ACTIVATION_INVALID"

    settings.ACCOUNT_ACTIVATION_TOKEN_MAX_AGE_SECONDS = 86400
    token = make_activation_token(user)
    user.email = "changed@example.test"
    user.save(update_fields=["email"])
    changed = client.post(
        "/api/v1/auth/activation/confirm/",
        {"token": token},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert changed.status_code == 400
    assert changed.json()["error"]["code"] == "ACTIVATION_INVALID"

    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    user.email = "changed-again@example.test"
    user.save(update_fields=["email"])
    user.refresh_from_db()
    assert user.email_verified_at is None


def test_email_outbox_retries_with_redacted_error(db, settings, monkeypatch):
    settings.EMAIL_OUTBOX_MAX_ATTEMPTS = 2
    settings.EMAIL_OUTBOX_RETRY_BASE_SECONDS = 0
    user = User.objects.create_user(
        email="delivery@example.test",
        password="StrongRegistrationPass123!",
        display_name="Delivery Test",
    )
    entry = EmailOutbox.objects.create(
        event_key="activation:test-retry:recipient:1",
        recipient=user,
        template_code=EmailOutbox.Template.ACCOUNT_ACTIVATION,
        locale="en",
    )

    def fail_delivery(**kwargs):
        raise TimeoutError("sensitive provider detail")

    monkeypatch.setattr("apps.core.notifications.send_mail", fail_delivery)
    assert deliver_email_outbox(entry.pk) is False
    entry.refresh_from_db()
    assert entry.status == EmailOutbox.Status.PENDING
    assert entry.attempt_count == 1
    assert entry.last_error_code == "TimeoutError"
    assert process_due_email_outbox() == 0
    entry.refresh_from_db()
    assert entry.status == EmailOutbox.Status.FAILED
    assert entry.attempt_count == 2
    assert "sensitive" not in entry.last_error_code


def test_email_outbox_is_discarded_with_rolled_back_transaction(db):
    user = User.objects.create_user(
        email="rollback@example.test",
        password="StrongRegistrationPass123!",
        display_name="Rollback Test",
    )
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            queue_activation_email(user)
            raise RuntimeError("roll back the workflow")
    assert EmailOutbox.objects.filter(recipient=user).exists() is False


def test_workflow_actions_queue_scoped_notifications(seeded):
    mail.outbox.clear()
    submitted = create_application(seeded["applicant"], seeded["patong"], name="Notification submit")
    add_current_documents(submitted)
    submit_application(application_id=submitted.pk, actor=seeded["applicant"])
    submit_entries = EmailOutbox.objects.filter(application=submitted)
    assert set(submit_entries.values_list("template_code", flat=True)) == {
        EmailOutbox.Template.APPLICATION_SUBMITTED
    }
    assert set(submit_entries.values_list("recipient_id", flat=True)) == {
        seeded["applicant"].pk,
        seeded["officer"].pk,
    }

    revision = create_application(
        seeded["applicant"],
        seeded["patong"],
        status=Application.Status.UNDER_REVIEW,
        name="Notification revision",
    )
    add_current_documents(revision, document_status=ApplicationDocument.Status.REVISION_REQUIRED)
    request_application_revision(application_id=revision.pk, actor=seeded["officer"], reason="Needs action")
    revision_entries = EmailOutbox.objects.filter(application=revision)
    assert list(revision_entries.values_list("template_code", "recipient_id")) == [
        (EmailOutbox.Template.APPLICATION_REVISION_REQUESTED, seeded["applicant"].pk)
    ]
    ApplicationDocument.objects.filter(application=revision, is_current=True).update(
        status=ApplicationDocument.Status.UPLOADED
    )
    submit_application(application_id=revision.pk, actor=seeded["applicant"])
    resubmit_entries = EmailOutbox.objects.filter(
        application=revision,
        template_code=EmailOutbox.Template.APPLICATION_RESUBMITTED,
    )
    assert set(resubmit_entries.values_list("recipient_id", flat=True)) == {
        seeded["applicant"].pk,
        seeded["officer"].pk,
    }

    rejected = create_application(
        seeded["applicant"],
        seeded["patong"],
        status=Application.Status.UNDER_REVIEW,
        name="Notification rejected",
    )
    reject_application(application_id=rejected.pk, actor=seeded["officer"], reason="Not eligible")
    rejected_entry = EmailOutbox.objects.get(application=rejected)
    assert (rejected_entry.template_code, rejected_entry.recipient_id) == (
        EmailOutbox.Template.APPLICATION_REJECTED,
        seeded["applicant"].pk,
    )
    assert deliver_email_outbox(rejected_entry.pk) is True
    assert len(mail.outbox) == 1
    assert "Not eligible" not in mail.outbox[0].body
    assert rejected.property.address_line not in mail.outbox[0].body
    assert mail.outbox[0].attachments == []

    approved = create_application(
        seeded["applicant"],
        seeded["patong"],
        status=Application.Status.UNDER_REVIEW,
        name="Notification approved",
    )
    add_current_documents(approved, document_status=ApplicationDocument.Status.APPROVED)
    approve_application(application_id=approved.pk, actor=seeded["officer"])
    assert list(
        EmailOutbox.objects.filter(application=approved).values_list("template_code", "recipient_id")
    ) == [(EmailOutbox.Template.APPLICATION_APPROVED, seeded["applicant"].pk)]


def test_password_reset_is_generic_single_use_and_changes_password(seeded, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.FRONTEND_BASE_URL = "http://frontend.test"
    client = Client(enforce_csrf_checks=True)
    client.get("/api/v1/auth/me/")
    csrf_token = client.cookies["csrftoken"].value

    unknown = client.post(
        "/api/v1/auth/password-reset/",
        {"email": "unknown@example.test"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert unknown.status_code == 202
    assert unknown.json() == {"accepted": True}
    assert len(mail.outbox) == 0

    requested = client.post(
        "/api/v1/auth/password-reset/",
        {"email": seeded["applicant"].email},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert requested.status_code == 202
    assert requested.json() == unknown.json()
    reset_entry = EmailOutbox.objects.get(
        recipient=seeded["applicant"],
        template_code=EmailOutbox.Template.PASSWORD_RESET,
    )
    assert deliver_email_outbox(reset_entry.pk) is True
    assert len(mail.outbox) == 1
    match = re.search(r"uid=([^&\s]+)&token=([^\s]+)", mail.outbox[0].body)
    assert match
    uid, token = match.groups()

    confirmed = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "NewDemoPass456!"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert confirmed.status_code == 200
    seeded["applicant"].refresh_from_db()
    assert seeded["applicant"].check_password("NewDemoPass456!")

    reused = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "AnotherDemoPass789!"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "PASSWORD_RESET_INVALID"


def test_applicant_list_contains_dashboard_classification_and_progress(seeded, api_client):
    api_client.force_authenticate(seeded["applicant"])
    response = api_client.get("/api/v1/applications/", HTTP_ACCEPT_LANGUAGE="en")
    assert response.status_code == 200
    assert response.data["results"]
    item = response.data["results"][0]
    assert item["property_type"]["code"] in {"TYPE_1", "TYPE_2"}
    assert item["responsible_authority"]["id"] == seeded["patong"].id
    assert {"required", "approved", "current_uploads", "complete_for_submission"} <= set(item["requirements"])


def test_officer_queue_filters_by_database_property_type(seeded, api_client):
    create_application(
        seeded["applicant"],
        seeded["patong"],
        status=Application.Status.SUBMITTED,
        type_code="TYPE_2",
        name="Type 2 queue item",
    )
    api_client.force_authenticate(seeded["officer"])
    response = api_client.get("/api/v1/officer/applications/?property_type=TYPE_2&ordering=property_type")
    assert response.status_code == 200
    assert response.data["results"]
    assert {item["property_type"]["code"] for item in response.data["results"]} == {"TYPE_2"}
    invalid = api_client.get("/api/v1/officer/applications/?property_type=NOT_REAL")
    assert invalid.status_code == 400


def test_audit_events_are_immutable_and_server_owned(seeded):
    event = AuditLog.objects.create(
        actor=seeded["applicant"], action="TEST_EVENT", object_type="core.Application", object_id="123"
    )
    assert event.created_at is not None
    event.reason = "tampered"
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        event.delete()


def test_admin_boundary_requires_super_admin_role(seeded):
    request = RequestFactory().get("/admin/")
    central = seeded["central"]
    central.is_staff = True
    request.user = central
    assert admin.site.has_permission(request) is False
    request.user = seeded["admin"]
    assert admin.site.has_permission(request) is True


def test_seed_demo_is_idempotent(seeded, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "DemoPass123!")
    before = {
        "authorities": LocalAuthority.objects.count(),
        "users": User.objects.count(),
        "types": PropertyType.objects.count(),
        "rules": ClassificationRule.objects.count(),
        "fees": FeeSchedule.objects.count(),
        "applications": Application.objects.count(),
        "documents": ApplicationDocument.objects.count(),
        "reviews": DocumentReview.objects.count(),
        "history": ApplicationStatusHistory.objects.count(),
        "audit": AuditLog.objects.count(),
        "licenses": License.objects.count(),
    }
    call_command("seed_demo", verbosity=0)
    after = {
        "authorities": LocalAuthority.objects.count(),
        "users": User.objects.count(),
        "types": PropertyType.objects.count(),
        "rules": ClassificationRule.objects.count(),
        "fees": FeeSchedule.objects.count(),
        "applications": Application.objects.count(),
        "documents": ApplicationDocument.objects.count(),
        "reviews": DocumentReview.objects.count(),
        "history": ApplicationStatusHistory.objects.count(),
        "audit": AuditLog.objects.count(),
        "licenses": License.objects.count(),
    }
    assert before == after
    assert after["authorities"] == 19


def test_seed_demo_reconciles_a_replaced_demo_document(seeded, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "DemoPass123!")
    application = Application.objects.get(property__name="ที่พักตัวอย่างรอตรวจ")
    baseline = application.documents.filter(is_current=True).first()
    assert baseline is not None
    baseline.is_current = False
    baseline.save(update_fields=["is_current"])
    replacement = ApplicationDocument.objects.create(
        application=application,
        document_type=baseline.document_type,
        version=2,
        attachment_index=1,
        original_filename="replacement.pdf",
        storage_key=f"test-replacements/{application.id}/{baseline.document_type_id}.pdf",
        content_type="application/pdf",
        size_bytes=128,
        status=ApplicationDocument.Status.UPLOADED,
        uploaded_by=seeded["applicant"],
        is_current=True,
    )

    call_command("seed_demo", verbosity=0)

    baseline.refresh_from_db()
    replacement.refresh_from_db()
    assert baseline.is_current is True
    assert replacement.is_current is False
    assert application.documents.filter(document_type=baseline.document_type, is_current=True).count() == 1


def test_seeded_central_analytics_cover_all_authorities(seeded):
    fixture_owner = User.objects.get(email="central.analytics.fixtures@example.test")
    fixtures = Application.objects.filter(property__owner=fixture_owner)
    active_authority_ids = set(LocalAuthority.objects.filter(is_active=True).values_list("id", flat=True))
    covered_authority_ids = set(Application.objects.values_list("responsible_authority_id", flat=True))

    assert fixture_owner.is_active is False
    assert fixtures.count() == 36
    assert fixtures.exclude(status=Application.Status.DRAFT).exists() is False
    assert covered_authority_ids == active_authority_ids
    assert Application.objects.count() == 40


def test_seeded_workflow_fixtures_are_internally_coherent(seeded):
    submitted = Application.objects.get(property__name="ที่พักตัวอย่างรอตรวจ")
    assert submitted.documents.filter(is_current=True, status="UPLOADED").count() == submitted.requirements.count()
    assert submitted.status_history.filter(to_status="SUBMITTED").exists()

    revision = Application.objects.get(property__name="ที่พักตัวอย่างรอแก้ไข")
    assert revision.documents.filter(is_current=True, status="REVISION_REQUIRED").count() == 1
    assert revision.documents.filter(is_current=True, status="REJECTED").count() == 0
    assert revision.status_history.filter(to_status="REVISION_REQUIRED").exists()

    approved = Application.objects.get(property__name="ที่พักตัวอย่างอนุมัติ")
    assert approved.documents.filter(is_current=True, status="APPROVED").count() == approved.requirements.count()
    assert approved.status_history.filter(to_status="APPROVED").exists()
    assert License.objects.filter(application=approved).count() == 1
