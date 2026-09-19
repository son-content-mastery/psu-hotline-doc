import io
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path, PurePath

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rest_framework import status as http_status

from .exceptions import DomainError
from .notifications import queue_application_event
from .models import (
    Application,
    ApplicationDocument,
    ApplicationRequirement,
    ApplicationStatusHistory,
    AuditLog,
    ClassificationRule,
    DocumentReview,
    DocumentPreflight,
    FeeSchedule,
    EmailOutbox,
    License,
    PropertyTypeDocumentRequirement,
    User,
)


ALLOWED_UPLOADS = {
    ".pdf": ("application/pdf", "pdf"),
    ".jpg": ("image/jpeg", "jpeg"),
    ".jpeg": ("image/jpeg", "jpeg"),
    ".png": ("image/png", "png"),
}
MAX_IMAGE_PIXELS = 40_000_000
QUALITY_ANALYZER_VERSION = "quality-v1"
QUALITY_MIN_SHORT_EDGE_PX = 800
QUALITY_MIN_CONTRAST_STDDEV = 12
QUALITY_DARK_MEAN = 40
QUALITY_BRIGHT_MEAN = 245
QUALITY_MIN_EDGE_VARIANCE = 60


@dataclass(frozen=True)
class ClassificationResult:
    rule: ClassificationRule

    @property
    def outcome(self):
        return self.rule.outcome_code

    @property
    def property_type(self):
        return self.rule.result_property_type

    @property
    def requires_license(self):
        return self.outcome != ClassificationRule.Outcome.NOT_HOTEL


def requested_locale(request) -> str:
    raw = request.headers.get("Accept-Language", "th").split(",", 1)[0].strip().lower()
    return raw.split("-", 1)[0] or "th"


def translated_value(instance, locale, *, fields=("name",)):
    translations = list(instance.translations.all())
    requested = next((item for item in translations if item.language_code.lower() == locale), None)
    thai = next((item for item in translations if item.language_code.lower() == "th"), None)
    selected = requested or thai
    result = {}
    for field in fields:
        value = getattr(selected, field, "") if selected else ""
        result[field] = value or (instance.code if field == "name" else "")
    result["translation_fallback"] = requested is None
    return result


def effective_fee(property_type, on_date=None):
    on_date = on_date or timezone.localdate()
    matches = list(
        FeeSchedule.objects.filter(property_type=property_type, effective_from__lte=on_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .order_by("-effective_from", "id")
    )
    if len(matches) > 1:
        raise DomainError(
            "FEE_SCHEDULE_AMBIGUOUS",
            "More than one fee schedule is effective for this property type.",
        )
    return matches[0] if matches else None


def _rule_matches(rule, rooms, max_guests, has_restaurant):
    checks = (
        rule.min_rooms is None or rooms >= rule.min_rooms,
        rule.max_rooms is None or rooms <= rule.max_rooms,
        rule.min_guests is None or max_guests >= rule.min_guests,
        rule.max_guests is None or max_guests <= rule.max_guests,
        rule.restaurant_value is None or has_restaurant == rule.restaurant_value,
    )
    return all(checks)


def evaluate_classification(*, rooms, max_guests, has_restaurant):
    rules = list(
        ClassificationRule.objects.filter(is_active=True)
        .select_related("result_property_type")
        .order_by("priority", "id")
    )
    matches = [rule for rule in rules if _rule_matches(rule, rooms, max_guests, has_restaurant)]
    if not matches:
        raise DomainError(
            "NO_ACTIVE_CLASSIFICATION_RULE",
            "No active classification rule matches these answers.",
        )
    if len(matches) > 1:
        raise DomainError(
            "NO_ACTIVE_CLASSIFICATION_RULE",
            "Classification rules overlap; an administrator must correct the configuration.",
        )
    return ClassificationResult(matches[0])


def capture_requirements(application):
    if not application.confirmed_property_type_id:
        return []
    source = PropertyTypeDocumentRequirement.objects.filter(
        property_type=application.confirmed_property_type,
        is_active=True,
        document_type__is_active=True,
    ).order_by("display_order", "id")
    captured = [
        ApplicationRequirement(
            application=application,
            document_type=item.document_type,
            is_required=item.is_required,
            step_code=item.step_code,
            display_order=item.display_order,
        )
        for item in source
    ]
    ApplicationRequirement.objects.bulk_create(captured)
    return captured


def active_requirement_signature(application):
    if not application.confirmed_property_type_id:
        return []
    return list(
        PropertyTypeDocumentRequirement.objects.filter(
            property_type=application.confirmed_property_type,
            is_active=True,
            document_type__is_active=True,
        )
        .order_by("document_type_id")
        .values_list("document_type_id", "is_required", "step_code", "display_order")
    )


def captured_requirement_signature(application):
    return list(
        application.requirements.order_by("document_type_id").values_list(
            "document_type_id", "is_required", "step_code", "display_order"
        )
    )


def requirements_have_changed(application):
    return active_requirement_signature(application) != captured_requirement_signature(application)


def replace_captured_requirements(application):
    ApplicationRequirement.objects.filter(application=application).delete()
    return capture_requirements(application)


def requirement_state(application):
    requirements = list(application.requirements.filter(is_required=True).select_related("document_type"))
    current_documents = {}
    for item in application.documents.filter(is_current=True).select_related("document_type").order_by(
        "document_type_id", "attachment_index"
    ):
        current_documents.setdefault(item.document_type_id, []).append(item)
    acceptable = {ApplicationDocument.Status.UPLOADED, ApplicationDocument.Status.APPROVED}

    def documents_are_acceptable(document_type_id):
        documents = current_documents.get(document_type_id, [])
        return bool(documents) and all(document.status in acceptable for document in documents)

    def documents_are_approved(document_type_id):
        documents = current_documents.get(document_type_id, [])
        return bool(documents) and all(
            document.status == ApplicationDocument.Status.APPROVED for document in documents
        )

    missing = [
        requirement.document_type_id
        for requirement in requirements
        if not documents_are_acceptable(requirement.document_type_id)
    ]
    approved = sum(
        1
        for requirement in requirements
        if documents_are_approved(requirement.document_type_id)
    )
    return {
        "required": len(requirements),
        "approved": approved,
        "current_uploads": sum(
            1 for requirement in requirements if current_documents.get(requirement.document_type_id)
        ),
        "complete_for_submission": bool(requirements) and not missing,
        "missing_document_type_ids": missing,
        "requirements": requirements,
        "current": {
            document_type_id: documents[0]
            for document_type_id, documents in current_documents.items()
            if documents
        },
        "current_documents": current_documents,
    }


ALLOWED_TRANSITIONS = {
    Application.Status.DRAFT: {Application.Status.READY_TO_SUBMIT},
    Application.Status.READY_TO_SUBMIT: {Application.Status.DRAFT, Application.Status.SUBMITTED},
    Application.Status.SUBMITTED: {Application.Status.UNDER_REVIEW},
    Application.Status.UNDER_REVIEW: {
        Application.Status.REVISION_REQUIRED,
        Application.Status.APPROVED,
        Application.Status.REJECTED,
    },
    Application.Status.REVISION_REQUIRED: {Application.Status.RESUBMITTED},
    Application.Status.RESUBMITTED: {Application.Status.UNDER_REVIEW},
}


def audit_event(*, actor, action, obj, from_status="", to_status="", reason=""):
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        object_type=obj._meta.label,
        object_id=str(obj.pk),
        from_status=from_status or "",
        to_status=to_status or "",
        reason=(reason or "").strip(),
    )


def transition_application(application, to_status, *, actor, action, reason=""):
    from_status = application.status
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise DomainError(
            "INVALID_STATUS_TRANSITION",
            f"Cannot transition an application from {from_status} to {to_status}.",
        )
    reason = (reason or "").strip()
    application.status = to_status
    application.save()
    ApplicationStatusHistory.objects.create(
        application=application,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
    )
    audit_event(
        actor=actor,
        action=action,
        obj=application,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
    )
    return application


def refresh_submission_readiness(application, *, actor):
    """Keep the pre-submission status synchronized with server-computed completeness."""
    if application.status not in {Application.Status.DRAFT, Application.Status.READY_TO_SUBMIT}:
        return application
    state = requirement_state(application)
    ready = bool(application.confirmed_property_type_id and state["complete_for_submission"])
    if ready and application.status == Application.Status.DRAFT:
        return transition_application(
            application,
            Application.Status.READY_TO_SUBMIT,
            actor=actor,
            action="APPLICATION_READY_TO_SUBMIT",
        )
    if not ready and application.status == Application.Status.READY_TO_SUBMIT:
        return transition_application(
            application,
            Application.Status.DRAFT,
            actor=actor,
            action="APPLICATION_NO_LONGER_READY",
        )
    return application


def _require_applicant_scope(application, actor):
    if actor.role != User.Role.APPLICANT:
        raise DomainError(
            "PERMISSION_DENIED",
            "Applicant access is required.",
            http_status=http_status.HTTP_403_FORBIDDEN,
        )
    if application.property.owner_id != actor.id:
        raise DomainError("NOT_FOUND", "The application was not found.", http_status=http_status.HTTP_404_NOT_FOUND)


def _require_officer_scope(application, actor):
    if actor.role != User.Role.LOCAL_OFFICER or not actor.local_authority_id:
        raise DomainError(
            "PERMISSION_DENIED",
            "Local officer access is required.",
            http_status=http_status.HTTP_403_FORBIDDEN,
        )
    if application.responsible_authority_id != actor.local_authority_id:
        raise DomainError("NOT_FOUND", "The application was not found.", http_status=http_status.HTTP_404_NOT_FOUND)


def _safe_filename(name):
    if not name or name in {".", ".."} or "\x00" in name or "/" in name or "\\" in name:
        raise DomainError(
            "VALIDATION_ERROR",
            "The uploaded filename is invalid.",
            http_status=http_status.HTTP_400_BAD_REQUEST,
            fields={"file": ["Use a plain filename without path components."]},
        )
    if PurePath(name).name != name or len(name) > 255:
        raise DomainError(
            "VALIDATION_ERROR",
            "The uploaded filename is invalid.",
            http_status=http_status.HTTP_400_BAD_REQUEST,
            fields={"file": ["Use a plain filename no longer than 255 characters."]},
        )
    return name


def validate_uploaded_file(upload):
    name = _safe_filename(upload.name)
    if not upload.size:
        raise DomainError(
            "VALIDATION_ERROR",
            "The uploaded file is empty.",
            http_status=http_status.HTTP_400_BAD_REQUEST,
            fields={"file": ["The file must not be empty."]},
        )
    if upload.size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise DomainError(
            "FILE_TOO_LARGE",
            f"Files must not exceed {settings.MAX_UPLOAD_SIZE_MB} MiB.",
            http_status=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_UPLOADS:
        raise DomainError(
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, JPG/JPEG, and PNG files are supported.",
            http_status=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )
    expected_mime, family = ALLOWED_UPLOADS[extension]
    if (getattr(upload, "content_type", "") or "").lower() != expected_mime:
        raise DomainError(
            "UNSUPPORTED_FILE_TYPE",
            "The file extension and declared content type do not match.",
            http_status=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )
    data = upload.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    upload.seek(0)
    if len(data) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise DomainError(
            "FILE_TOO_LARGE",
            f"Files must not exceed {settings.MAX_UPLOAD_SIZE_MB} MiB.",
            http_status=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    try:
        if family == "pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("missing PDF signature")
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError("encrypted PDF")
            len(reader.pages)
        else:
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("image dimensions are too large")
                image.verify()
                if image.format.lower() != family:
                    raise ValueError("image signature does not match")
    except (PdfReadError, UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, EOFError):
        raise DomainError(
            "UNSUPPORTED_FILE_TYPE",
            "The file is malformed, protected, or does not match its declared type.",
            http_status=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )
    return name, extension, expected_mime, data


def analyze_document_quality(data, content_type):
    """Return advisory, non-blocking quality signals without retaining document content."""
    if not settings.DOCUMENT_QUALITY_PREFLIGHT_ENABLED:
        return None
    if content_type == "application/pdf":
        return {
            "status": DocumentPreflight.Status.LIMITED,
            "issue_codes": ["PDF_VISUAL_CHECK_UNAVAILABLE"],
            "analyzer_version": QUALITY_ANALYZER_VERSION,
        }
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            width, height = source.size
            grayscale = source.convert("L")
            grayscale.thumbnail((1600, 1600))
            statistics = ImageStat.Stat(grayscale)
            brightness = statistics.mean[0]
            contrast = statistics.stddev[0]
            edges = grayscale.filter(ImageFilter.FIND_EDGES)
            if edges.width > 4 and edges.height > 4:
                edges = edges.crop((2, 2, edges.width - 2, edges.height - 2))
            edge_variance = ImageStat.Stat(edges).var[0]
        issue_codes = []
        if min(width, height) < QUALITY_MIN_SHORT_EDGE_PX:
            issue_codes.append("LOW_RESOLUTION")
        if brightness < QUALITY_DARK_MEAN:
            issue_codes.append("TOO_DARK")
        elif brightness > QUALITY_BRIGHT_MEAN:
            issue_codes.append("TOO_BRIGHT")
        if contrast < QUALITY_MIN_CONTRAST_STDDEV:
            issue_codes.append("LOW_CONTRAST")
        if edge_variance < QUALITY_MIN_EDGE_VARIANCE:
            issue_codes.append("POSSIBLY_BLURRY")
        return {
            "status": DocumentPreflight.Status.WARNING if issue_codes else DocumentPreflight.Status.PASS,
            "issue_codes": issue_codes,
            "analyzer_version": QUALITY_ANALYZER_VERSION,
        }
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, EOFError):
        return {
            "status": DocumentPreflight.Status.LIMITED,
            "issue_codes": ["QUALITY_CHECK_UNAVAILABLE"],
            "analyzer_version": QUALITY_ANALYZER_VERSION,
        }


@transaction.atomic
def upload_document(*, application_id, document_type_id, actor, upload=None, uploads=None):
    application = (
        Application.objects.select_for_update(of=("self",))
        .select_related("property")
        .get(pk=application_id)
    )
    _require_applicant_scope(application, actor)
    if application.status not in {
        Application.Status.DRAFT,
        Application.Status.READY_TO_SUBMIT,
        Application.Status.REVISION_REQUIRED,
    }:
        raise DomainError("APPLICATION_NOT_EDITABLE", "This application does not accept uploads.")
    requirement = application.requirements.filter(document_type_id=document_type_id).select_related("document_type").first()
    if not requirement:
        raise DomainError(
            "NOT_FOUND", "The document type was not found in this checklist.", http_status=http_status.HTTP_404_NOT_FOUND
        )
    upload_list = list(uploads or ([] if upload is None else [upload]))
    if not upload_list:
        raise DomainError(
            "VALIDATION_ERROR",
            "At least one file is required.",
            http_status=http_status.HTTP_400_BAD_REQUEST,
            fields={"files": ["Select at least one file."]},
        )
    if len(upload_list) > 10:
        raise DomainError(
            "VALIDATION_ERROR",
            "A document bundle may contain at most 10 files.",
            http_status=http_status.HTTP_400_BAD_REQUEST,
            fields={"files": ["Select no more than 10 files."]},
        )
    if len(upload_list) > 1 and not requirement.document_type.allows_multiple_files:
        raise DomainError(
            "MULTIPLE_FILES_NOT_ALLOWED",
            "This checklist item accepts one file.",
            http_status=http_status.HTTP_400_BAD_REQUEST,
            fields={"files": ["Upload one file for this checklist item."]},
        )
    current = list(
        ApplicationDocument.objects.select_for_update()
        .filter(application=application, document_type_id=document_type_id, is_current=True)
        .order_by("attachment_index")
    )
    if application.status == Application.Status.REVISION_REQUIRED and (
        not current
        or not any(document.status == ApplicationDocument.Status.REVISION_REQUIRED for document in current)
    ):
        raise DomainError(
            "DOCUMENT_NOT_OPEN_FOR_REVISION", "This document was not requested for replacement."
        )
    validated_uploads = [validate_uploaded_file(item) for item in upload_list]
    preflight_results = [analyze_document_quality(data, mime) for _, _, mime, data in validated_uploads]
    max_version = (
        ApplicationDocument.objects.filter(application=application, document_type_id=document_type_id)
        .aggregate(value=Max("version"))["value"]
        or 0
    )
    saved_keys = []
    try:
        for _, extension, _, data in validated_uploads:
            storage_key = f"application_documents/{application.pk}/{uuid.uuid4().hex}{extension}"
            saved_keys.append(default_storage.save(storage_key, ContentFile(data)))
        if current:
            ApplicationDocument.objects.filter(pk__in=[document.pk for document in current]).update(is_current=False)
        documents = []
        for attachment_index, ((name, _, mime, data), saved_key, preflight_result) in enumerate(
            zip(validated_uploads, saved_keys, preflight_results), start=1
        ):
            document = ApplicationDocument.objects.create(
                application=application,
                document_type_id=document_type_id,
                version=max_version + 1,
                attachment_index=attachment_index,
                original_filename=name,
                storage_key=saved_key,
                content_type=mime,
                size_bytes=len(data),
                status=ApplicationDocument.Status.UPLOADED,
                uploaded_by=actor,
                is_current=True,
            )
            if preflight_result is not None:
                DocumentPreflight.objects.create(
                    application_document=document,
                    **preflight_result,
                )
            audit_event(actor=actor, action="DOCUMENT_UPLOADED", obj=document)
            documents.append(document)
        refresh_submission_readiness(application, actor=actor)
        return documents
    except Exception:
        for saved_key in saved_keys:
            default_storage.delete(saved_key)
        raise


def submit_application(*, application_id, actor):
    requirements_changed = False
    result = None
    with transaction.atomic():
        application = (
            Application.objects.select_for_update(of=("self",))
            .select_related("confirmed_property_type", "property")
            .get(pk=application_id)
        )
        _require_applicant_scope(application, actor)
        if application.status not in {
            Application.Status.DRAFT,
            Application.Status.READY_TO_SUBMIT,
            Application.Status.REVISION_REQUIRED,
        }:
            raise DomainError("INVALID_STATUS_TRANSITION", "This application cannot be submitted in its current state.")
        if not application.confirmed_property_type_id:
            raise DomainError("CLASSIFICATION_UNRESOLVED", "A confirmed property type is required before submission.")
        if application.status in {Application.Status.DRAFT, Application.Status.READY_TO_SUBMIT} and requirements_have_changed(application):
            replace_captured_requirements(application)
            refresh_submission_readiness(application, actor=actor)
            requirements_changed = True
        else:
            state = requirement_state(application)
            if not state["requirements"]:
                raise DomainError("REQUIREMENTS_NOT_CONFIGURED", "No document checklist is configured for this type.")
            if state["missing_document_type_ids"]:
                code = "REVISION_ITEMS_INCOMPLETE" if application.status == Application.Status.REVISION_REQUIRED else "MISSING_REQUIRED_DOCUMENTS"
                raise DomainError(
                    code,
                    "Required documents are missing or not ready.",
                    fields={"missing_document_type_ids": state["missing_document_type_ids"]},
                )
            if application.status == Application.Status.DRAFT:
                refresh_submission_readiness(application, actor=actor)
                if application.status != Application.Status.READY_TO_SUBMIT:
                    raise DomainError("INVALID_STATUS_TRANSITION", "This application is not ready to submit.")
            now = timezone.now()
            if application.status == Application.Status.REVISION_REQUIRED:
                application.resubmitted_at = now
                result = transition_application(
                    application,
                    Application.Status.RESUBMITTED,
                    actor=actor,
                    action="APPLICATION_RESUBMITTED",
                )
                history_id = result.status_history.order_by("-id").values_list("id", flat=True).first()
                queue_application_event(result, EmailOutbox.Template.APPLICATION_RESUBMITTED, history_id)
            else:
                if not application.reference_number:
                    application.reference_number = f"HTL-{now.year}-{application.pk:05d}"
                application.submitted_at = application.submitted_at or now
                result = transition_application(
                    application,
                    Application.Status.SUBMITTED,
                    actor=actor,
                    action="APPLICATION_SUBMITTED",
                )
                history_id = result.status_history.order_by("-id").values_list("id", flat=True).first()
                queue_application_event(result, EmailOutbox.Template.APPLICATION_SUBMITTED, history_id)
    if requirements_changed:
        raise DomainError(
            "REQUIREMENTS_CHANGED",
            "The active checklist changed. Review the refreshed requirements before submitting.",
        )
    return result


@transaction.atomic
def review_document(*, document_id, actor, outcome, reason=""):
    document = (
        ApplicationDocument.objects.select_for_update()
        .select_related("application")
        .get(pk=document_id)
    )
    application = Application.objects.select_for_update().get(pk=document.application_id)
    _require_officer_scope(application, actor)
    if not document.is_current:
        raise DomainError("DOCUMENT_VERSION_NOT_CURRENT", "Only the current document version can be reviewed.")
    if application.status not in {
        Application.Status.SUBMITTED,
        Application.Status.RESUBMITTED,
        Application.Status.UNDER_REVIEW,
    }:
        raise DomainError("APPLICATION_NOT_REVIEWABLE", "This application is not reviewable.")
    if not application.requirements.filter(document_type_id=document.document_type_id, is_required=True).exists():
        raise DomainError(
            "NOT_FOUND",
            "The document is not part of the submitted checklist.",
            http_status=http_status.HTTP_404_NOT_FOUND,
        )
    if document.reviews.exists():
        raise DomainError("DOCUMENT_ALREADY_REVIEWED", "This document version already has a review.")
    reason = (reason or "").strip()
    if outcome in {DocumentReview.Outcome.REVISION_REQUIRED, DocumentReview.Outcome.REJECTED} and not reason:
        raise DomainError(
            "REASON_REQUIRED", "A reason is required for this outcome.", http_status=http_status.HTTP_400_BAD_REQUEST
        )
    if application.status in {Application.Status.SUBMITTED, Application.Status.RESUBMITTED}:
        transition_application(
            application,
            Application.Status.UNDER_REVIEW,
            actor=actor,
            action="APPLICATION_REVIEW_STARTED",
        )
    review = DocumentReview.objects.create(
        application_document=document,
        reviewer=actor,
        outcome=outcome,
        reason=reason,
    )
    document.status = outcome
    document.save(update_fields=["status"])
    audit_event(actor=actor, action="DOCUMENT_REVIEWED", obj=document, to_status=outcome, reason=reason)
    return review


@transaction.atomic
def request_application_revision(*, application_id, actor, reason):
    application = Application.objects.select_for_update().get(pk=application_id)
    _require_officer_scope(application, actor)
    reason = (reason or "").strip()
    if not reason:
        raise DomainError(
            "REASON_REQUIRED", "A reason is required.", http_status=http_status.HTTP_400_BAD_REQUEST
        )
    if application.status != Application.Status.UNDER_REVIEW:
        raise DomainError("INVALID_STATUS_TRANSITION", "Only an application under review can be returned.")
    if not application.documents.filter(
        is_current=True, status=ApplicationDocument.Status.REVISION_REQUIRED
    ).exists():
        raise DomainError("NO_DOCUMENT_REVISIONS_REQUESTED", "Mark at least one current document for revision first.")
    required_type_ids = application.requirements.filter(is_required=True).values_list("document_type_id", flat=True)
    if application.documents.filter(
        is_current=True,
        document_type_id__in=required_type_ids,
        status=ApplicationDocument.Status.REJECTED,
    ).exists():
        raise DomainError(
            "DOCUMENTS_REJECTED",
            "Rejected required documents prevent a revision cycle; reject the application or record a supported review outcome.",
        )
    result = transition_application(
        application,
        Application.Status.REVISION_REQUIRED,
        actor=actor,
        action="APPLICATION_REVISION_REQUESTED",
        reason=reason,
    )
    history_id = result.status_history.order_by("-id").values_list("id", flat=True).first()
    queue_application_event(result, EmailOutbox.Template.APPLICATION_REVISION_REQUESTED, history_id)
    return result


def _expiry_date(issue_date, years):
    try:
        anniversary = issue_date.replace(year=issue_date.year + years)
    except ValueError:
        anniversary = issue_date.replace(year=issue_date.year + years, day=28)
    return anniversary - timedelta(days=1)


@transaction.atomic
def approve_application(*, application_id, actor, note=""):
    application = (
        Application.objects.select_for_update(of=("self",))
        .select_related("confirmed_property_type")
        .get(pk=application_id)
    )
    _require_officer_scope(application, actor)
    if application.status != Application.Status.UNDER_REVIEW:
        if License.objects.filter(application=application).exists():
            raise DomainError("LICENSE_ALREADY_EXISTS", "A license has already been issued.")
        raise DomainError("INVALID_STATUS_TRANSITION", "Only an application under review can be approved.")
    state = requirement_state(application)
    pending = [
        requirement.document_type_id
        for requirement in state["requirements"]
        if not state["current_documents"].get(requirement.document_type_id)
        or any(
            document.status != ApplicationDocument.Status.APPROVED
            for document in state["current_documents"][requirement.document_type_id]
        )
    ]
    if pending:
        raise DomainError(
            "DOCUMENTS_NOT_APPROVED",
            "Every required current document must be approved.",
            fields={"pending_document_type_ids": pending},
        )
    issue_time = timezone.now()
    if License.objects.filter(application=application).exists():
        raise DomainError("LICENSE_ALREADY_EXISTS", "A license has already been issued.")
    if application.confirmed_property_type.issues_license:
        fee = effective_fee(application.confirmed_property_type, timezone.localdate(issue_time))
        if not fee:
            raise DomainError("FEE_SCHEDULE_NOT_FOUND", "No effective fee schedule is configured.")
        license_record = License.objects.create(
            application=application,
            artifact_kind=License.ArtifactKind.HOTEL_LICENSE,
            license_number=f"LIC-{issue_time.year}-{application.pk:05d}",
            property_type=application.confirmed_property_type,
            fee_schedule=fee,
            fee_amount_snapshot=fee.amount,
            fee_currency_snapshot=fee.currency,
            validity_years_snapshot=fee.validity_years,
            issued_at=issue_time,
            expires_at=_expiry_date(timezone.localdate(issue_time), fee.validity_years),
        )
        issued_action = "LICENSE_ISSUED"
    else:
        license_record = License.objects.create(
            application=application,
            artifact_kind=License.ArtifactKind.NOTIFICATION_ACKNOWLEDGEMENT,
            license_number=f"ACK-{issue_time.year}-{application.pk:05d}",
            property_type=application.confirmed_property_type,
            issued_at=issue_time,
        )
        issued_action = "NOTIFICATION_ACKNOWLEDGEMENT_ISSUED"
    application.approved_at = issue_time
    transition_application(
        application,
        Application.Status.APPROVED,
        actor=actor,
        action="APPLICATION_APPROVED",
        reason=(note or "").strip(),
    )
    audit_event(actor=actor, action=issued_action, obj=license_record)
    history_id = application.status_history.order_by("-id").values_list("id", flat=True).first()
    queue_application_event(application, EmailOutbox.Template.APPLICATION_APPROVED, history_id)
    return application, license_record


@transaction.atomic
def reject_application(*, application_id, actor, reason):
    application = Application.objects.select_for_update().get(pk=application_id)
    _require_officer_scope(application, actor)
    reason = (reason or "").strip()
    if not reason:
        raise DomainError(
            "REASON_REQUIRED", "A reason is required.", http_status=http_status.HTTP_400_BAD_REQUEST
        )
    if hasattr(application, "license"):
        raise DomainError("LICENSE_ALREADY_ISSUED", "An issued application cannot be rejected.")
    if application.status != Application.Status.UNDER_REVIEW:
        raise DomainError("INVALID_STATUS_TRANSITION", "Only an application under review can be rejected.")
    application.rejected_at = timezone.now()
    result = transition_application(
        application,
        Application.Status.REJECTED,
        actor=actor,
        action="APPLICATION_REJECTED",
        reason=reason,
    )
    history_id = result.status_history.order_by("-id").values_list("id", flat=True).first()
    queue_application_event(result, EmailOutbox.Template.APPLICATION_REJECTED, history_id)
    return result


def current_stage(status):
    if status == Application.Status.REVISION_REQUIRED:
        return "APPLICANT_ACTION"
    if status in {Application.Status.SUBMITTED, Application.Status.UNDER_REVIEW, Application.Status.RESUBMITTED}:
        return "LOCAL_OFFICER_REVIEW"
    if status in {Application.Status.APPROVED, Application.Status.REJECTED}:
        return "COMPLETED"
    return "APPLICANT_PREPARATION"


def waiting_since(application):
    event = application.status_history.order_by("-created_at", "-id").first()
    return event.created_at if event else application.updated_at


def officer_allowed_actions(application):
    """Advisory UI actions derived from the same server-owned workflow prerequisites."""
    actions = []
    if application.status not in {
        Application.Status.SUBMITTED,
        Application.Status.RESUBMITTED,
        Application.Status.UNDER_REVIEW,
    }:
        return actions
    state = requirement_state(application)
    required_current = [
        document
        for requirement in state["requirements"]
        for document in state["current_documents"].get(requirement.document_type_id, [])
    ]
    if any(document and document.status == ApplicationDocument.Status.UPLOADED for document in required_current):
        actions.append("REVIEW_DOCUMENTS")
    if application.status == Application.Status.UNDER_REVIEW:
        has_revision = any(
            document and document.status == ApplicationDocument.Status.REVISION_REQUIRED
            for document in required_current
        )
        has_rejected = any(
            document and document.status == ApplicationDocument.Status.REJECTED
            for document in required_current
        )
        if has_revision and not has_rejected:
            actions.append("REQUEST_REVISION")
        all_approved = bool(required_current) and all(
            document and document.status == ApplicationDocument.Status.APPROVED
            for document in required_current
        )
        if all_approved and application.confirmed_property_type_id:
            if not application.confirmed_property_type.issues_license:
                actions.append("APPROVE")
            else:
                try:
                    if effective_fee(application.confirmed_property_type):
                        actions.append("APPROVE")
                except DomainError:
                    pass
        actions.append("REJECT")
    return actions
