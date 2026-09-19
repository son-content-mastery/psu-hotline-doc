import io
from collections import Counter, defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.crypto import salted_hmac
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
import qrcode
from qrcode.image.svg import SvgPathImage

from .exceptions import DomainError
from .models import (
    Application,
    ApplicationDocument,
    ApplicationRequirement,
    ApplicationStatusHistory,
    CaseLibraryArticle,
    CentralAssistanceRequest,
    ClassificationRule,
    DocumentReview,
    DocumentPreflight,
    DiscussionMessage,
    DocumentType,
    FeeSchedule,
    IssuingAgency,
    License,
    LocalAuthority,
    MaintenanceNotice,
    Property,
    PropertyType,
    PropertyTypeDocumentRequirement,
    ProviderDirectoryEntry,
    ThaiProvince,
    User,
)
from .permissions import IsApplicant, IsCentralOfficer, IsLocalOfficer, IsVerifiedUser
from .notifications import activate_user_from_token, queue_activation_email, queue_password_reset_email
from .serializers import (
    ActivationCompleteOutputSerializer,
    ActivationConfirmSerializer,
    ActivationResendSerializer,
    ApplicationCreateSerializer,
    ApplicationPatchSerializer,
    ApprovalSerializer,
    CentralAssistanceRequestSerializer,
    CentralAssistanceResolutionSerializer,
    ClassificationInputSerializer,
    DocumentReviewSerializer,
    DiscussionMessageSerializer,
    EmptySerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetCompleteOutputSerializer,
    PasswordResetAcceptedOutputSerializer,
    PasswordResetRequestSerializer,
    PublicLicenseVerificationOutputSerializer,
    PaginatedApplicantApplicationOutputSerializer,
    PaginatedCaseLibraryOutputSerializer,
    HistoryOutputSerializer,
    OfficerApplicationDetailOutputSerializer,
    PaginatedOfficerQueueOutputSerializer,
    ReasonSerializer,
    RegistrationAcceptedOutputSerializer,
    RegistrationSerializer,
    RequirementsOutputSerializer,
    SubmitSerializer,
    ThaiLocationCatalogOutputSerializer,
    UploadSerializer,
)
from .throttles import AccountEmailRateThrottle
from .services import (
    approve_application,
    audit_event,
    capture_requirements,
    current_stage,
    effective_fee,
    evaluate_classification,
    officer_allowed_actions,
    reject_application,
    request_application_revision,
    requested_locale,
    requirement_state,
    review_document,
    submit_application,
    translated_value,
    upload_document,
    waiting_since,
    refresh_submission_readiness,
)


DISCLAIMER_TH = "รายการนี้จัดทำจากบัญชีเอกสารที่ได้รับสำหรับโครงการ และยังต้องยืนยันกับหน่วยงานที่รับผิดชอบก่อนใช้งานจริง"
DISCLAIMER_EN = "This checklist is based on the document supplied for the project and must still be confirmed with the responsible authority before real use."


class ContractAPIView(GenericAPIView):
    """Schema-friendly base for the small, explicitly implemented API views."""

    serializer_class = EmptySerializer


class SystemStatusView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        now = timezone.now()
        notice = (
            MaintenanceNotice.objects.filter(is_active=True, starts_at__lte=now, ends_at__gt=now)
            .order_by("-starts_at")
            .first()
        )
        if notice is None:
            return Response({"maintenance": None, "checked_at": now})
        locale = requested_locale(request)
        return Response(
            {
                "maintenance": {
                    "title": notice.title_en if locale == "en" else notice.title_th,
                    "message": notice.message_en if locale == "en" else notice.message_th,
                    "starts_at": notice.starts_at,
                    "ends_at": notice.ends_at,
                },
                "checked_at": now,
            }
        )


class ProviderDirectoryView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        queryset = ProviderDirectoryEntry.objects.filter(is_active=True)
        service = request.query_params.get("service", "").strip().upper()
        if service:
            if service not in ProviderDirectoryEntry.ServiceCode.values:
                raise DomainError("INVALID_PROVIDER_SERVICE", "Unknown provider service code.")
            queryset = queryset.filter(services__contains=[service])
        locale = requested_locale(request)
        return Response(
            {
                "disclaimer": (
                    "Listings are informational only and are not endorsed, licensed, or guaranteed by HoTLinE Doc. Verify qualifications, scope, and price directly before hiring."
                    if locale == "en"
                    else "รายชื่อนี้เป็นข้อมูลประกอบเท่านั้น HoTLinE Doc ไม่ได้รับรอง ใบอนุญาต คุณภาพ หรือราคา กรุณาตรวจสอบคุณสมบัติ ขอบเขตงาน และราคากับผู้ให้บริการก่อนว่าจ้าง"
                ),
                "results": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "services": item.services,
                        "price": {
                            "min": str(item.price_min) if item.price_min is not None else None,
                            "max": str(item.price_max) if item.price_max is not None else None,
                            "currency": item.currency,
                            "note": item.price_note_en if locale == "en" else item.price_note_th,
                        },
                        "contact_url": item.contact_url or None,
                        "source_url": item.source_url or None,
                        "source_status": item.source_status,
                        "source_checked_at": item.source_checked_at,
                    }
                    for item in queryset
                ],
            }
        )


def authority_data(authority):
    if authority is None:
        return None
    return {"id": authority.id, "code": authority.code, "name": authority.official_name}


def user_data(user):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "local_authority": authority_data(user.local_authority),
    }


def property_type_data(property_type, locale):
    if property_type is None:
        return None
    translation = translated_value(property_type, locale, fields=("name", "description"))
    return {
        "id": property_type.id,
        "code": property_type.code,
        "name": translation["name"],
        "description": translation["description"],
        "issues_license": property_type.issues_license,
        "translation_fallback": translation["translation_fallback"],
    }


def public_verification_links(license_record):
    token = str(license_record.verification_token)
    return {
        "verification_url": f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify/{token}",
        "qr_code_url": f"/api/v1/public/licenses/{token}/qr/",
    }


def public_license_data(license_record, locale):
    expires_at = license_record.expires_at
    if license_record.artifact_kind == License.ArtifactKind.NOTIFICATION_ACKNOWLEDGEMENT:
        public_status = "RECORDED"
    elif expires_at and expires_at < timezone.localdate():
        public_status = "EXPIRED"
    else:
        public_status = "VALID"
    application = license_record.application
    return {
        "status": public_status,
        "artifact_kind": license_record.artifact_kind,
        "license_number": license_record.license_number,
        "property": {"name": application.property.name},
        "property_type": property_type_data(license_record.property_type, locale),
        "issuing_authority": authority_data(application.responsible_authority),
        "issued_at": license_record.issued_at,
        "expires_at": expires_at,
        "checked_at": timezone.now(),
    }


def document_type_data(document_type, locale):
    translation = translated_value(document_type, locale, fields=("name", "description", "instructions", "supporting_items"))
    return {
        "id": document_type.id,
        "code": document_type.code,
        "name": translation["name"],
        "description": translation["description"] or None,
        "instructions": translation["instructions"] or None,
        "category": document_type.category,
        "allows_multiple_files": document_type.allows_multiple_files,
        "translation_fallback": translation["translation_fallback"],
    }


def classification_data(application, locale):
    return {
        "outcome": application.classification_outcome_snapshot,
        "property_type": property_type_data(application.confirmed_property_type, locale),
        "answers": {
            "rooms": application.rooms_snapshot,
            "guests": application.max_guests_snapshot,
            "has_restaurant": application.restaurant_snapshot,
        },
    }


def application_summary(application, locale):
    requirements = requirement_state(application)
    renewal = None
    try:
        license_record = application.license
    except License.DoesNotExist:
        license_record = None
    if (
        application.status == Application.Status.APPROVED
        and license_record
        and license_record.artifact_kind == License.ArtifactKind.HOTEL_LICENSE
        and license_record.expires_at
    ):
        days_remaining = (license_record.expires_at - timezone.localdate()).days
        action_required = days_remaining <= max(settings.LICENSE_RENEWAL_REMINDER_DAYS)
        renewal = {
            "expires_at": license_record.expires_at,
            "days_remaining": days_remaining,
            "status": "EXPIRED" if days_remaining < 0 else "DUE" if action_required else "UPCOMING",
            "action_required": action_required,
        }
    return {
        "id": application.id,
        "reference_number": application.reference_number,
        "property_name": application.property.name,
        "property_type": property_type_data(application.confirmed_property_type, locale),
        "responsible_authority": authority_data(application.responsible_authority),
        "status": application.status,
        "current_stage": current_stage(application.status),
        "applicant_action_required": application.status == Application.Status.REVISION_REQUIRED,
        "waiting_since": waiting_since(application),
        "requirements": {
            "required": requirements["required"],
            "approved": requirements["approved"],
            "current_uploads": requirements["current_uploads"],
            "complete_for_submission": requirements["complete_for_submission"],
        },
        "renewal": renewal,
        "updated_at": application.updated_at,
    }


def application_detail(application, locale):
    state = requirement_state(application)
    administrative_subdistrict = application.property.administrative_subdistrict
    return {
        "id": application.id,
        "reference_number": application.reference_number,
        "status": application.status,
        "current_stage": current_stage(application.status),
        "applicant_action_required": application.status == Application.Status.REVISION_REQUIRED,
        "waiting_since": waiting_since(application),
        "property": {
            "id": application.property.id,
            "name": application.property.name,
            "address_line": application.property.address_line,
            "province_code": (
                administrative_subdistrict.district.province.code if administrative_subdistrict else None
            ),
            "district_code": administrative_subdistrict.district.code if administrative_subdistrict else None,
            "subdistrict_code": administrative_subdistrict.code if administrative_subdistrict else None,
            "subdistrict": application.property.subdistrict,
            "district": application.property.district,
            "province": application.property.province,
            "postal_code": application.property.postal_code,
            "local_authority": authority_data(application.property.local_authority),
        },
        "classification": classification_data(application, locale),
        "requirements": {
            "required": state["required"],
            "approved": state["approved"],
            "current_uploads": state["current_uploads"],
            "complete_for_submission": state["complete_for_submission"],
        },
        "responsible_authority": authority_data(application.responsible_authority),
        "submitted_at": application.submitted_at,
        "resubmitted_at": application.resubmitted_at,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }


def history_event_data(application, event, locale):
    affected = []
    if event.to_status == Application.Status.REVISION_REQUIRED:
        previous = (
            application.status_history.filter(created_at__lt=event.created_at)
            .order_by("-created_at", "-id")
            .first()
        )
        reviews = DocumentReview.objects.filter(
            application_document__application=application,
            outcome=DocumentReview.Outcome.REVISION_REQUIRED,
            reviewed_at__lte=event.created_at,
        )
        if previous:
            reviews = reviews.filter(reviewed_at__gte=previous.created_at)
        document_types = {
            review.application_document.document_type_id: review.application_document.document_type
            for review in reviews.select_related("application_document__document_type").prefetch_related(
                "application_document__document_type__translations"
            )
        }
        affected = [
            document_type_data(document_type, locale)
            for _, document_type in sorted(document_types.items())
        ]
    return {
        "id": event.id,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "occurred_at": event.created_at,
        "reason": event.reason or None,
        "actor_category": event.actor.role if event.actor_id else "SYSTEM",
        "document_type": (
            {"id": affected[0]["id"], "name": affected[0]["name"]} if len(affected) == 1 else None
        ),
        "affected_documents": [
            {"id": document_type["id"], "name": document_type["name"]}
            for document_type in affected
        ],
    }


def document_data(document, locale, *, officer=False, include_reviews=False):
    latest_review = document.reviews.order_by("-reviewed_at", "-id").first()
    prefix = "/api/v1/officer/documents" if officer else f"/api/v1/applications/{document.application_id}/documents"
    result = {
        "id": document.id,
        "application_id": document.application_id,
        "document_type": document_type_data(document.document_type, locale),
        "version": document.version,
        "attachment_index": document.attachment_index,
        "status": document.status,
        "is_current": document.is_current,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "uploaded_at": document.uploaded_at,
        "category": document.document_type.category,
        "version_label": "CURRENT" if document.is_current else "PRIOR",
        "uploaded_by": {
            "id": document.uploaded_by_id,
            "display_name": document.uploaded_by.display_name,
            "role": document.uploaded_by.role,
        },
        "uploader_role": document.uploaded_by.role,
        "latest_review_reason": latest_review.reason if latest_review else None,
        "download_url": f"{prefix}/{document.id}/file/",
        "preflight": preflight_data(document),
    }
    if include_reviews:
        result["reviews"] = [
            {
                "id": review.id,
                "outcome": review.outcome,
                "reason": review.reason or None,
                "reviewed_at": review.reviewed_at,
                "reviewed_by": {"id": review.reviewer_id, "display_name": review.reviewer.display_name},
            }
            for review in document.reviews.select_related("reviewer").all()
        ]
    return result


def preflight_data(document):
    try:
        preflight = document.preflight
    except DocumentPreflight.DoesNotExist:
        return None
    return {
        "status": preflight.status,
        "issue_codes": preflight.issue_codes,
        "analyzer_version": preflight.analyzer_version,
        "type_check_status": preflight.type_check_status,
        "detected_family": preflight.detected_family or None,
        "type_analyzer_version": preflight.type_analyzer_version or None,
        "analyzed_at": preflight.analyzed_at,
    }


def guidance_data(document_type, authority, locale):
    if document_type.category != DocumentType.Category.EXTERNAL_AGENCY or not document_type.issuing_agency:
        return None
    agency = document_type.issuing_agency
    agency_translation = translated_value(agency, locale, fields=("name", "address", "contact_notes"))
    doc_translation = translated_value(
        document_type, locale, fields=("name", "description", "instructions", "supporting_items")
    )
    support = [item.strip() for item in doc_translation["supporting_items"].splitlines() if item.strip()]
    contact = agency.contact_phone or agency.contact_email or agency.website_url or None
    return {
        "issuing_agency": {"id": agency.id, "code": agency.code, "name": agency_translation["name"]},
        "responsible_local_authority": authority_data(authority),
        "contact": contact,
        "contact_phone": agency.contact_phone or None,
        "contact_email": agency.contact_email or None,
        "source_url": agency.website_url or None,
        "instructions": doc_translation["instructions"] or None,
        "required_supporting_items": support,
        "approximate_processing_days": document_type.approximate_processing_days,
        "translation_fallback": agency_translation["translation_fallback"] or doc_translation["translation_fallback"],
    }


REQUIREMENT_STEP_ORDER = ["APPLICANT", "PREMISES", "FACILITIES", "SAFETY", "MANAGER"]


def aggregate_requirement_status(documents):
    if not documents:
        return "MISSING"
    statuses = {document.status for document in documents}
    if ApplicationDocument.Status.REVISION_REQUIRED in statuses:
        return ApplicationDocument.Status.REVISION_REQUIRED
    if ApplicationDocument.Status.REJECTED in statuses:
        return ApplicationDocument.Status.REJECTED
    if statuses == {ApplicationDocument.Status.APPROVED}:
        return ApplicationDocument.Status.APPROVED
    return ApplicationDocument.Status.UPLOADED


def requirement_item_data(requirement, locale, *, authority=None, state=None):
    documents = state["current_documents"].get(requirement.document_type_id, []) if state else []
    reviews = [
        review
        for document in documents
        for review in document.reviews.order_by("-reviewed_at", "-id")[:1]
    ]
    latest_review = max(reviews, key=lambda review: (review.reviewed_at, review.id), default=None)
    type_payload = document_type_data(requirement.document_type, locale)
    payload = {
        "requirement_id": getattr(requirement, "id", None),
        "document_type": type_payload,
        "required": requirement.is_required,
        "step_code": requirement.step_code,
        "description": type_payload["description"],
        "instructions": type_payload["instructions"],
        "guidance": guidance_data(requirement.document_type, authority, locale),
    }
    if state is not None:
        payload.update(
            {
                "status": aggregate_requirement_status(documents),
                "current_document_id": documents[0].id if documents else None,
                "current_document_ids": [document.id for document in documents],
                "latest_review_reason": latest_review.reason if latest_review else None,
            }
        )
    return payload


def requirement_steps(items, *, include_progress):
    steps = []
    for order, code in enumerate(REQUIREMENT_STEP_ORDER, start=1):
        step_items = [item for item in items if item["step_code"] == code]
        if not step_items:
            continue
        required_items = [item for item in step_items if item["required"]]
        completed = sum(
            item.get("status") in {ApplicationDocument.Status.UPLOADED, ApplicationDocument.Status.APPROVED}
            for item in required_items
        ) if include_progress else 0
        action_required = sum(
            item.get("status") in {"MISSING", ApplicationDocument.Status.REVISION_REQUIRED, ApplicationDocument.Status.REJECTED}
            for item in required_items
        ) if include_progress else len(required_items)
        steps.append(
            {
                "code": code,
                "order": order,
                "required": len(required_items),
                "completed": completed,
                "action_required": action_required,
                "complete": bool(required_items) and completed == len(required_items),
                "items": step_items,
            }
        )
    return steps


def paginated_response(request, queryset, mapper):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([mapper(item) for item in page])


def owned_applications(user):
    return Application.objects.filter(property__owner=user).select_related(
        "property",
        "property__local_authority",
        "property__administrative_subdistrict__district__province",
        "responsible_authority",
        "confirmed_property_type",
        "license",
    )


def officer_applications(user):
    if not user.local_authority_id:
        return Application.objects.none()
    return Application.objects.filter(
        responsible_authority_id=user.local_authority_id,
        status__in={
            Application.Status.SUBMITTED,
            Application.Status.UNDER_REVIEW,
            Application.Status.REVISION_REQUIRED,
            Application.Status.RESUBMITTED,
            Application.Status.APPROVED,
            Application.Status.REJECTED,
        },
    ).select_related(
        "property",
        "property__local_authority",
        "property__administrative_subdistrict__district__province",
        "responsible_authority",
        "confirmed_property_type",
    )


class AuthMeView(ContractAPIView):
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        if request.user.is_authenticated and request.user.email_verified_at is not None:
            return Response({"authenticated": True, "user": user_data(request.user)})
        if request.user.is_authenticated:
            logout(request._request)
        return Response({"authenticated": False, "user": None})


class RegisterView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = RegistrationSerializer
    throttle_classes = [ScopedRateThrottle, AccountEmailRateThrottle]
    throttle_scope = "registration"

    @extend_schema(request=RegistrationSerializer, responses={202: RegistrationAcceptedOutputSerializer})
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        email = values["email"].strip().lower()
        preferred_language = User.Language.ENGLISH if requested_locale(request) == "en" else User.Language.THAI
        display_name = "Applicant" if preferred_language == User.Language.ENGLISH else "ผู้ยื่นคำขอ"
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "display_name": display_name,
                    "role": User.Role.APPLICANT,
                    "preferred_language": preferred_language,
                    "is_active": True,
                },
            )
            if created:
                user.set_password(values["password"])
                user.full_clean(exclude=["password"])
                user.save()
                audit_event(actor=user, action="USER_REGISTERED", obj=user)
            if user.is_active and user.email_verified_at is None:
                queue_activation_email(user)
        return Response({"accepted": True}, status=status.HTTP_202_ACCEPTED)


class ActivationResendView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ActivationResendSerializer
    throttle_classes = [ScopedRateThrottle, AccountEmailRateThrottle]
    throttle_scope = "activation"

    @extend_schema(request=ActivationResendSerializer, responses={202: RegistrationAcceptedOutputSerializer})
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(
            email=email,
            is_active=True,
            email_verified_at__isnull=True,
        ).first()
        if user is not None:
            queue_activation_email(user)
        return Response({"accepted": True}, status=status.HTTP_202_ACCEPTED)


class ActivationConfirmView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ActivationConfirmSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "activation"

    @extend_schema(request=ActivationConfirmSerializer, responses=ActivationCompleteOutputSerializer)
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activate_user_from_token(serializer.validated_data["token"])
        return Response({"activated": True})


class LoginView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle, AccountEmailRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request._request,
            username=serializer.validated_data["email"].strip().lower(),
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            from rest_framework.exceptions import AuthenticationFailed

            raise AuthenticationFailed("Invalid credentials.")
        if user.email_verified_at is None:
            raise DomainError(
                "EMAIL_NOT_VERIFIED",
                "Verify your email before signing in.",
                http_status=status.HTTP_403_FORBIDDEN,
            )
        login(request._request, user)
        return Response({"user": user_data(user)})


class LogoutView(ContractAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PasswordResetRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: PasswordResetAcceptedOutputSerializer})
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(
            email=email,
            is_active=True,
            email_verified_at__isnull=False,
        ).first()
        if user and user.has_usable_password():
            queue_password_reset_email(user)
        return Response({"accepted": True}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PasswordResetConfirmSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetConfirmSerializer, responses=PasswordResetCompleteOutputSerializer)
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        token = serializer.validated_data["token"]
        if user is None or not default_token_generator.check_token(user, token):
            raise DomainError(
                "PASSWORD_RESET_INVALID",
                "This password reset link is invalid or has expired.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        new_password = serializer.validated_data["new_password"]
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as error:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"new_password": error.messages})
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"reset": True})


class ClassificationQuestionsView(ContractAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        locale = requested_locale(request)
        labels = {
            "th": (
                "ที่พักของคุณมีห้องพักทั้งหมดกี่ห้อง?",
                "รองรับผู้เข้าพักได้สูงสุดกี่คน?",
                "มีห้องอาหารหรือไม่?",
            ),
            "en": ("How many rooms does your property have?", "What is the maximum number of guests?", "Does it have a restaurant?"),
        }.get(locale) or (
            "ที่พักของคุณมีห้องพักทั้งหมดกี่ห้อง?",
            "รองรับผู้เข้าพักได้สูงสุดกี่คน?",
            "มีห้องอาหารหรือไม่?",
        )
        version = ClassificationRule.objects.filter(is_active=True).aggregate(value=Max("updated_at"))["value"]
        return Response(
            {
                "version": version,
                "questions": [
                    {"key": "rooms", "order": 1, "type": "integer", "label": labels[0], "required": True, "minimum": 1},
                    {"key": "guests", "order": 2, "type": "integer", "label": labels[1], "required": True, "minimum": 1},
                    {"key": "has_restaurant", "order": 3, "type": "boolean", "label": labels[2], "required": True},
                ],
            }
        )


class ClassificationEvaluateView(ContractAPIView):
    permission_classes = [AllowAny]
    serializer_class = ClassificationInputSerializer

    def post(self, request):
        serializer = ClassificationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        result = evaluate_classification(
            rooms=values["rooms"], max_guests=values["guests"], has_restaurant=values["has_restaurant"]
        )
        locale = requested_locale(request)
        fee = effective_fee(result.property_type) if result.property_type else None
        return Response(
            {
                "outcome": result.outcome,
                "requires_license": result.requires_license,
                "property_type": property_type_data(result.property_type, locale),
                "fee": (
                    {"amount": str(fee.amount), "currency": fee.currency, "validity_years": fee.validity_years}
                    if fee
                    else None
                ),
                "needs_manual_classification_confirmation": result.outcome
                == ClassificationRule.Outcome.REQUIRES_LICENSE_REVIEW,
                "rules_version": result.rule.updated_at,
            }
        )


class LocalAuthorityListView(ContractAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = LocalAuthority.objects.filter(is_active=True)
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(official_name__icontains=search) | Q(code__icontains=search))
        return paginated_response(
            request,
            queryset,
            lambda item: {
                **authority_data(item),
                "contact_phone": item.contact_phone or None,
                "contact_email": item.contact_email or None,
                "translation_fallback": False,
            },
        )


class PhuketLocationCatalogView(ContractAPIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=ThaiLocationCatalogOutputSerializer)
    def get(self, request):
        locale = requested_locale(request)
        province = get_object_or_404(
            ThaiProvince.objects.filter(is_active=True).prefetch_related(
                "districts__subdistricts"
            ),
            code="83",
        )

        def localized_name(item):
            return item.name_en if locale == "en" else item.name_th

        districts = []
        for district in province.districts.filter(is_active=True):
            subdistricts = [
                {
                    "code": subdistrict.code,
                    "name": localized_name(subdistrict),
                    "postal_code": subdistrict.postal_code,
                }
                for subdistrict in district.subdistricts.filter(is_active=True)
            ]
            districts.append(
                {
                    "code": district.code,
                    "name": localized_name(district),
                    "subdistricts": subdistricts,
                }
            )
        return Response(
            {
                "province": {"code": province.code, "name": localized_name(province)},
                "districts": districts,
            }
        )


class PropertyTypeListView(ContractAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        locale = requested_locale(request)
        queryset = PropertyType.objects.filter(is_active=True).prefetch_related("translations", "fee_schedules")

        def serialize(item):
            result = property_type_data(item, locale)
            fee = effective_fee(item)
            result["current_fee"] = (
                {
                    "amount": str(fee.amount),
                    "currency": fee.currency,
                    "validity_years": fee.validity_years,
                    "effective_from": fee.effective_from,
                }
                if fee
                else None
            )
            return result

        return paginated_response(request, queryset, serialize)


class PublicPropertyTypeRequirementsView(ContractAPIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=RequirementsOutputSerializer)
    def get(self, request, pk):
        locale = requested_locale(request)
        property_type = get_object_or_404(
            PropertyType.objects.prefetch_related("translations"), pk=pk, is_active=True
        )
        requirements = PropertyTypeDocumentRequirement.objects.filter(
            property_type=property_type, is_active=True, document_type__is_active=True
        ).select_related("document_type", "document_type__issuing_agency").prefetch_related(
            "document_type__translations", "document_type__issuing_agency__translations"
        )
        items = [requirement_item_data(requirement, locale) for requirement in requirements]
        groups = []
        for category in (DocumentType.Category.OPERATOR_PREPARED, DocumentType.Category.EXTERNAL_AGENCY):
            groups.append(
                {
                    "category": category,
                    "items": [item for item in items if item["document_type"]["category"] == category],
                }
            )
        return Response(
            {
                "property_type": property_type_data(property_type, locale),
                "is_legally_validated_checklist": False,
                "disclaimer": DISCLAIMER_EN if locale == "en" else DISCLAIMER_TH,
                "groups": groups,
                "steps": requirement_steps(items, include_progress=False),
            }
        )


class ApplicationListCreateView(ContractAPIView):
    permission_classes = [IsApplicant]

    def get_serializer_class(self):
        return ApplicationCreateSerializer if self.request.method == "POST" else EmptySerializer

    @extend_schema(operation_id="list_applicant_applications", responses=PaginatedApplicantApplicationOutputSerializer)
    def get(self, request):
        base_queryset = owned_applications(request.user)
        renewal_due = Q(
            status=Application.Status.APPROVED,
            license__artifact_kind=License.ArtifactKind.HOTEL_LICENSE,
            license__expires_at__lte=timezone.localdate() + timedelta(days=max(settings.LICENSE_RENEWAL_REMINDER_DAYS)),
        )
        action_statuses = [
            Application.Status.DRAFT,
            Application.Status.READY_TO_SUBMIT,
            Application.Status.REVISION_REQUIRED,
        ]
        summary = {
            "needs_action": base_queryset.filter(Q(status__in=action_statuses) | renewal_due).count(),
            "in_progress": base_queryset.filter(
                status__in=[Application.Status.SUBMITTED, Application.Status.UNDER_REVIEW, Application.Status.RESUBMITTED]
            ).count(),
            "approved": base_queryset.filter(status=Application.Status.APPROVED).count(),
            "total": base_queryset.count(),
        }
        queryset = base_queryset
        view_filter = request.query_params.get("view", "").strip()
        view_statuses = {
            "action": action_statuses,
            "in_progress": [Application.Status.SUBMITTED, Application.Status.UNDER_REVIEW, Application.Status.RESUBMITTED],
            "completed": [Application.Status.APPROVED, Application.Status.REJECTED],
            "all": Application.Status.values,
        }
        if view_filter:
            if view_filter not in view_statuses:
                raise DomainError("VALIDATION_ERROR", "Unknown application view.", http_status=status.HTTP_400_BAD_REQUEST)
            if view_filter == "action":
                queryset = queryset.filter(Q(status__in=action_statuses) | renewal_due)
            else:
                queryset = queryset.filter(status__in=view_statuses[view_filter])
        status_filter = request.query_params.get("status")
        if status_filter:
            if status_filter not in Application.Status.values:
                raise DomainError("VALIDATION_ERROR", "Unknown status filter.", http_status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(status=status_filter)
        locale = requested_locale(request)
        response = paginated_response(request, queryset, lambda application: application_summary(application, locale))
        response.data["summary"] = summary
        return response

    @transaction.atomic
    def post(self, request):
        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_values = serializer.validated_data["property"]
        answers = serializer.validated_data["classification_answers"]
        authority = get_object_or_404(LocalAuthority, pk=property_values.pop("local_authority_id"), is_active=True)
        administrative_subdistrict = property_values.pop("administrative_subdistrict")
        district = administrative_subdistrict.district
        province = district.province
        result = evaluate_classification(
            rooms=answers["rooms"], max_guests=answers["guests"], has_restaurant=answers["has_restaurant"]
        )
        if result.outcome == ClassificationRule.Outcome.OUT_OF_SCOPE:
            raise DomainError("OUT_OF_SCOPE", "This property is outside the MVP processing scope.")
        property_record = Property.objects.create(
            owner=request.user,
            local_authority=authority,
            property_type=result.property_type,
            administrative_subdistrict=administrative_subdistrict,
            subdistrict=administrative_subdistrict.name_th,
            district=district.name_th,
            province=province.name_th,
            postal_code=administrative_subdistrict.postal_code,
            rooms=answers["rooms"],
            max_guests=answers["guests"],
            has_restaurant=answers["has_restaurant"],
            **property_values,
        )
        application = Application.objects.create(
            property=property_record,
            responsible_authority=authority,
            classification_rule=result.rule,
            confirmed_property_type=result.property_type,
            rooms_snapshot=answers["rooms"],
            max_guests_snapshot=answers["guests"],
            restaurant_snapshot=answers["has_restaurant"],
            classification_outcome_snapshot=result.outcome,
        )
        capture_requirements(application)
        locale = requested_locale(request)
        response = application_detail(application, locale)
        response["requirements_complete"] = response.pop("requirements")["complete_for_submission"]
        return Response(response, status=status.HTTP_201_CREATED)


class ApplicationDetailView(ContractAPIView):
    permission_classes = [IsApplicant]

    def get_serializer_class(self):
        return ApplicationPatchSerializer if self.request.method == "PATCH" else EmptySerializer

    def get_object(self, request, pk):
        return get_object_or_404(owned_applications(request.user), pk=pk)

    @extend_schema(operation_id="retrieve_applicant_application")
    def get(self, request, pk):
        return Response(application_detail(self.get_object(request, pk), requested_locale(request)))

    @transaction.atomic
    def patch(self, request, pk):
        application = get_object_or_404(
            owned_applications(request.user).select_for_update(of=("self",)), pk=pk
        )
        if application.status not in {
            Application.Status.DRAFT,
            Application.Status.READY_TO_SUBMIT,
            Application.Status.REVISION_REQUIRED,
        }:
            raise DomainError("APPLICATION_NOT_EDITABLE", "This application is not editable.")
        serializer = ApplicationPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        property_values = values.get("property", {})
        if application.status == Application.Status.REVISION_REQUIRED and (
            "local_authority_id" in property_values or "classification_answers" in values
        ):
            raise DomainError("APPLICATION_NOT_EDITABLE", "Routing and classification cannot change during revision.")
        if "local_authority_id" in property_values:
            authority = get_object_or_404(
                LocalAuthority, pk=property_values.pop("local_authority_id"), is_active=True
            )
            application.property.local_authority = authority
            application.responsible_authority = authority
        if "administrative_subdistrict" in property_values:
            administrative_subdistrict = property_values.pop("administrative_subdistrict")
            district = administrative_subdistrict.district
            province = district.province
            application.property.administrative_subdistrict = administrative_subdistrict
            application.property.subdistrict = administrative_subdistrict.name_th
            application.property.district = district.name_th
            application.property.province = province.name_th
            application.property.postal_code = administrative_subdistrict.postal_code
        for key, value in property_values.items():
            setattr(application.property, key, value)
        if "classification_answers" in values:
            answers = values["classification_answers"]
            result = evaluate_classification(
                rooms=answers["rooms"], max_guests=answers["guests"], has_restaurant=answers["has_restaurant"]
            )
            if result.outcome == ClassificationRule.Outcome.OUT_OF_SCOPE:
                raise DomainError("OUT_OF_SCOPE", "This property is outside the MVP processing scope.")
            application.property.rooms = answers["rooms"]
            application.property.max_guests = answers["guests"]
            application.property.has_restaurant = answers["has_restaurant"]
            application.property.property_type = result.property_type
            application.classification_rule = result.rule
            application.confirmed_property_type = result.property_type
            application.rooms_snapshot = answers["rooms"]
            application.max_guests_snapshot = answers["guests"]
            application.restaurant_snapshot = answers["has_restaurant"]
            application.classification_outcome_snapshot = result.outcome
            ApplicationRequirement.objects.filter(application=application).delete()
            capture_requirements(application)
        application.property.save()
        application.save()
        refresh_submission_readiness(application, actor=request.user)
        return Response(application_detail(application, requested_locale(request)))


class ApplicationRequirementsView(ContractAPIView):
    permission_classes = [IsApplicant]

    @extend_schema(responses=RequirementsOutputSerializer)
    def get(self, request, pk):
        application = get_object_or_404(owned_applications(request.user), pk=pk)
        if not application.confirmed_property_type_id:
            raise DomainError("CLASSIFICATION_UNRESOLVED", "Classification must be confirmed first.")
        requirements = application.requirements.select_related(
            "document_type", "document_type__issuing_agency"
        ).prefetch_related("document_type__translations", "document_type__issuing_agency__translations")
        if not requirements.exists():
            raise DomainError("REQUIREMENTS_NOT_CONFIGURED", "No requirements are configured.")
        locale = requested_locale(request)
        state = requirement_state(application)
        items = [
            requirement_item_data(
                requirement,
                locale,
                authority=application.responsible_authority,
                state=state,
            )
            for requirement in requirements
        ]
        groups = []
        for category in (DocumentType.Category.OPERATOR_PREPARED, DocumentType.Category.EXTERNAL_AGENCY):
            groups.append(
                {
                    "category": category,
                    "items": [item for item in items if item["document_type"]["category"] == category],
                }
            )
        return Response(
            {
                "application_id": application.id,
                "property_type": property_type_data(application.confirmed_property_type, locale),
                "is_legally_validated_checklist": False,
                "disclaimer": DISCLAIMER_EN if locale == "en" else DISCLAIMER_TH,
                "complete_for_submission": state["complete_for_submission"],
                "groups": groups,
                "steps": requirement_steps(items, include_progress=True),
            }
        )


class ApplicationSubmitView(ContractAPIView):
    permission_classes = [IsApplicant]
    serializer_class = SubmitSerializer

    def post(self, request, pk):
        get_object_or_404(owned_applications(request.user), pk=pk)
        serializer = SubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = submit_application(application_id=pk, actor=request.user)
        payload = {
            "id": application.id,
            "reference_number": application.reference_number,
            "status": application.status,
            "current_stage": current_stage(application.status),
            "submitted_at": application.submitted_at,
        }
        if application.resubmitted_at:
            payload["resubmitted_at"] = application.resubmitted_at
        return Response(payload)


class ApplicationHistoryView(ContractAPIView):
    permission_classes = [IsApplicant]

    @extend_schema(responses=HistoryOutputSerializer)
    def get(self, request, pk):
        application = get_object_or_404(owned_applications(request.user), pk=pk)
        return Response(
            {
                "application_id": application.id,
                "current_status": application.status,
                "waiting_since": waiting_since(application),
                "applicant_action_required": application.status == Application.Status.REVISION_REQUIRED,
                "events": [
                    history_event_data(application, event, requested_locale(request))
                    for event in application.status_history.select_related("actor").all()
                ],
            }
        )


class ApplicationDocumentsView(ContractAPIView):
    permission_classes = [IsApplicant]

    def get_serializer_class(self):
        return UploadSerializer if self.request.method == "POST" else EmptySerializer

    def get(self, request, pk):
        application = get_object_or_404(owned_applications(request.user), pk=pk)
        include_raw = request.query_params.get("include_versions", "false").lower()
        if include_raw not in {"true", "false"}:
            raise DomainError(
                "VALIDATION_ERROR", "include_versions must be true or false.", http_status=status.HTTP_400_BAD_REQUEST
            )
        queryset = application.documents.select_related("document_type", "uploaded_by", "preflight").prefetch_related(
            "document_type__translations", "reviews"
        )
        if include_raw != "true":
            queryset = queryset.filter(is_current=True)
        locale = requested_locale(request)
        return paginated_response(request, queryset, lambda item: document_data(item, locale))

    def post(self, request, pk):
        application = get_object_or_404(owned_applications(request.user), pk=pk)
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploads = serializer.validated_data.get("files")
        if not uploads and serializer.validated_data.get("file"):
            uploads = [serializer.validated_data["file"]]
        documents = upload_document(
            application_id=application.id,
            document_type_id=serializer.validated_data["document_type_id"],
            uploads=uploads,
            actor=request.user,
        )
        refreshed = ApplicationDocument.objects.select_related("document_type", "uploaded_by", "preflight").prefetch_related(
            "document_type__translations", "reviews"
        ).filter(pk__in=[document.pk for document in documents]).order_by("attachment_index")
        payloads = [document_data(document, requested_locale(request)) for document in refreshed]
        payload = {**payloads[0], "bundle_documents": payloads, "bundle_count": len(payloads)}
        return Response(payload, status=status.HTTP_201_CREATED)


class ApplicantDocumentFileView(ContractAPIView):
    permission_classes = [IsApplicant]

    def get(self, request, pk, document_id):
        document = get_object_or_404(
            ApplicationDocument.objects.select_related("application").filter(
                application_id=pk, application__property__owner=request.user
            ),
            pk=document_id,
        )
        return protected_file_response(document)


def protected_file_response(document):
    from django.core.files.storage import default_storage

    if not default_storage.exists(document.storage_key):
        raise Http404
    response = FileResponse(
        default_storage.open(document.storage_key, "rb"),
        as_attachment=True,
        filename=document.original_filename,
        content_type=document.content_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


class OfficerApplicationListView(ContractAPIView):
    permission_classes = [IsLocalOfficer]

    @extend_schema(
        operation_id="list_officer_applications",
        responses=PaginatedOfficerQueueOutputSerializer,
    )
    def get(self, request):
        queryset = officer_applications(request.user)
        statuses = request.query_params.get("status")
        if statuses:
            values = [value.strip() for value in statuses.split(",") if value.strip()]
            if not values or any(value not in Application.Status.values for value in values):
                raise DomainError("VALIDATION_ERROR", "Unknown status filter.", http_status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(status__in=values)
        property_type = request.query_params.get("property_type", "").strip()
        if property_type:
            if property_type == "UNCONFIRMED":
                queryset = queryset.filter(confirmed_property_type__isnull=True)
            elif PropertyType.objects.filter(code=property_type, is_active=True).exists():
                queryset = queryset.filter(confirmed_property_type__code=property_type)
            else:
                raise DomainError(
                    "VALIDATION_ERROR",
                    "Unknown property type filter.",
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
        ordering = request.query_params.get("ordering")
        if ordering:
            ordering_fields = {
                "submitted_at": "submitted_at",
                "-submitted_at": "-submitted_at",
                "updated_at": "updated_at",
                "-updated_at": "-updated_at",
                "property_type": "confirmed_property_type__code",
                "-property_type": "-confirmed_property_type__code",
            }
            if ordering not in ordering_fields:
                raise DomainError("VALIDATION_ERROR", "Unsupported ordering.", http_status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.order_by(ordering_fields[ordering], "submitted_at", "id")
        locale = requested_locale(request)

        def serialize(application):
            required_type_ids = application.requirements.filter(is_required=True).values_list("document_type_id", flat=True)
            pending = application.documents.filter(
                is_current=True,
                document_type_id__in=required_type_ids,
                status=ApplicationDocument.Status.UPLOADED,
            ).count()
            return {
                "id": application.id,
                "reference_number": application.reference_number,
                "property_name": application.property.name,
                "property_type": property_type_data(application.confirmed_property_type, locale),
                "status": application.status,
                "submitted_at": application.submitted_at,
                "resubmitted_at": application.resubmitted_at,
                "waiting_since": waiting_since(application),
                "documents_pending_review": pending,
            }

        return paginated_response(request, queryset, serialize)


class OfficerCaseLibraryView(ContractAPIView):
    permission_classes = [IsLocalOfficer]

    @extend_schema(
        operation_id="list_officer_case_library",
        responses=PaginatedCaseLibraryOutputSerializer,
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) > 100:
            raise DomainError(
                "VALIDATION_ERROR",
                "Search text must be 100 characters or fewer.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        decision = request.query_params.get("decision", "").strip().upper()
        if decision and decision not in {Application.Status.APPROVED, Application.Status.REJECTED}:
            raise DomainError(
                "VALIDATION_ERROR",
                "Decision must be APPROVED or REJECTED.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        property_type = request.query_params.get("property_type", "").strip()
        if property_type and not PropertyType.objects.filter(code=property_type, is_active=True).exists():
            raise DomainError(
                "VALIDATION_ERROR",
                "Unknown property type filter.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = (
            Application.objects.filter(
                status__in=[Application.Status.APPROVED, Application.Status.REJECTED],
                confirmed_property_type__isnull=False,
            )
            .select_related("confirmed_property_type")
            .prefetch_related("confirmed_property_type__translations")
            .annotate(
                decision_at=Coalesce("approved_at", "rejected_at", "updated_at"),
                revision_rounds=Count(
                    "status_history",
                    filter=Q(status_history__to_status=Application.Status.REVISION_REQUIRED),
                    distinct=True,
                ),
                required_count=Count(
                    "requirements",
                    filter=Q(requirements__is_required=True),
                    distinct=True,
                ),
                current_approved_count=Count(
                    "documents",
                    filter=Q(
                        documents__is_current=True,
                        documents__status=ApplicationDocument.Status.APPROVED,
                    ),
                    distinct=True,
                ),
                reviewed_version_count=Count("documents__reviews", distinct=True),
            )
            .order_by("-decision_at", "-id")
        )
        if decision:
            queryset = queryset.filter(status=decision)
        if property_type:
            queryset = queryset.filter(confirmed_property_type__code=property_type)
        if query:
            query_filter = (
                Q(confirmed_property_type__code__icontains=query)
                | Q(confirmed_property_type__translations__name__icontains=query)
                | Q(classification_outcome_snapshot__icontains=query)
                | Q(status__icontains=query)
            )
            normalized_query = query.casefold()
            if query.isdigit():
                query_filter |= Q(rooms_snapshot=int(query)) | Q(max_guests_snapshot=int(query))
            if normalized_query in {"approved", "approve", "อนุมัติ", "ผ่าน"}:
                query_filter |= Q(status=Application.Status.APPROVED)
            if normalized_query in {"rejected", "reject", "ปฏิเสธ", "ไม่ผ่าน"}:
                query_filter |= Q(status=Application.Status.REJECTED)
            if normalized_query in {"restaurant", "ร้านอาหาร", "มีร้านอาหาร"}:
                query_filter |= Q(restaurant_snapshot=True)
            queryset = queryset.filter(query_filter).distinct()

        locale = requested_locale(request)

        def serialize(application):
            decided_at = application.decision_at
            processing_days = None
            if application.submitted_at and decided_at:
                processing_days = max(0, (decided_at.date() - application.submitted_at.date()).days)
            type_translation = translated_value(
                application.confirmed_property_type,
                locale,
                fields=("name",),
            )
            return {
                "case_reference": f"CASE-{salted_hmac('case-library', str(application.pk)).hexdigest()[:10].upper()}",
                "decision": application.status,
                "property_type": {
                    "code": application.confirmed_property_type.code,
                    "name": type_translation["name"],
                },
                "classification": {
                    "rooms": application.rooms_snapshot,
                    "guests": application.max_guests_snapshot,
                    "has_restaurant": application.restaurant_snapshot,
                    "outcome": application.classification_outcome_snapshot,
                },
                "revision_rounds": application.revision_rounds,
                "processing_days": processing_days,
                "decided_at": decided_at,
                "documents": {
                    "required": application.required_count,
                    "current_approved": application.current_approved_count,
                    "versions_reviewed": application.reviewed_version_count,
                },
            }

        response = paginated_response(request, queryset, serialize)
        articles = CaseLibraryArticle.objects.filter(is_active=True)
        if query:
            normalized_query = query.casefold()
            articles = [
                article
                for article in articles
                if normalized_query
                in " ".join(
                    [
                        article.question_th,
                        article.question_en,
                        article.answer_th,
                        article.answer_en,
                        *article.keywords,
                    ]
                ).casefold()
            ]
        response.data["faqs"] = [
            {
                "slug": article.slug,
                "question": article.question_en if locale == "en" else article.question_th,
                "answer": article.answer_en if locale == "en" else article.answer_th,
                "updated_at": article.updated_at,
            }
            for article in articles
        ]
        return response


class OfficerApplicationDetailView(ContractAPIView):
    permission_classes = [IsLocalOfficer]

    @extend_schema(
        operation_id="retrieve_officer_application",
        responses=OfficerApplicationDetailOutputSerializer,
    )
    def get(self, request, pk):
        application = get_object_or_404(officer_applications(request.user), pk=pk)
        locale = requested_locale(request)
        administrative_subdistrict = application.property.administrative_subdistrict
        required_type_ids = set(application.requirements.filter(is_required=True).values_list("document_type_id", flat=True))
        documents = list(application.documents.select_related("document_type", "uploaded_by", "preflight").prefetch_related(
            "document_type__translations", "reviews__reviewer"
        ))
        state = requirement_state(application)
        grouped_documents = []
        document_slots = sorted({(item.document_type_id, item.attachment_index) for item in documents})
        for document_type_id, attachment_index in document_slots:
            versions = sorted(
                [
                    item
                    for item in documents
                    if item.document_type_id == document_type_id
                    and item.attachment_index == attachment_index
                ],
                key=lambda item: item.version,
                reverse=True,
            )
            current = next((item for item in versions if item.is_current), versions[0])
            payload = {
                **document_data(current, locale, officer=True, include_reviews=True),
                "is_in_submitted_checklist": current.document_type_id in required_type_ids,
                "reviewable": current.is_current
                and current.document_type_id in required_type_ids
                and current.status == ApplicationDocument.Status.UPLOADED,
                "versions": [
                    {
                        **document_data(item, locale, officer=True, include_reviews=True),
                        "is_in_submitted_checklist": item.document_type_id in required_type_ids,
                        "reviewable": False,
                    }
                    for item in versions
                    if item.pk != current.pk
                ],
            }
            grouped_documents.append(payload)
        return Response(
            {
                "id": application.id,
                "reference_number": application.reference_number,
                "status": application.status,
                "waiting_since": waiting_since(application),
                "submitted_at": application.submitted_at,
                "resubmitted_at": application.resubmitted_at,
                "property": {
                    "name": application.property.name,
                    "address_line": application.property.address_line,
                    "province_code": (
                        administrative_subdistrict.district.province.code
                        if administrative_subdistrict
                        else None
                    ),
                    "district_code": (
                        administrative_subdistrict.district.code if administrative_subdistrict else None
                    ),
                    "subdistrict_code": administrative_subdistrict.code if administrative_subdistrict else None,
                    "subdistrict": application.property.subdistrict,
                    "district": application.property.district,
                    "province": application.property.province,
                    "postal_code": application.property.postal_code,
                    "local_authority": authority_data(application.responsible_authority),
                },
                "classification": classification_data(application, locale),
                "documents": grouped_documents,
                "all_required_documents_approved": state["required"] > 0 and state["approved"] == state["required"],
                "allowed_actions": officer_allowed_actions(application),
                "central_assistance": [
                    central_assistance_data(item)
                    for item in application.central_assistance_requests.all()
                ],
            }
        )


class OfficerDocumentReviewView(ContractAPIView):
    permission_classes = [IsLocalOfficer]
    serializer_class = DocumentReviewSerializer

    def post(self, request, pk):
        get_object_or_404(
            ApplicationDocument.objects.filter(
                application__responsible_authority_id=request.user.local_authority_id,
                application__status__in={
                    Application.Status.SUBMITTED,
                    Application.Status.RESUBMITTED,
                    Application.Status.UNDER_REVIEW,
                },
            ),
            pk=pk,
        )
        serializer = DocumentReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = review_document(document_id=pk, actor=request.user, **serializer.validated_data)
        return Response(
            {
                "id": review.id,
                "application_document_id": review.application_document_id,
                "outcome": review.outcome,
                "reason": review.reason or None,
                "reviewed_at": review.reviewed_at,
                "reviewed_by": {"id": review.reviewer_id, "display_name": review.reviewer.display_name},
            },
            status=status.HTTP_201_CREATED,
        )


class OfficerDocumentFileView(ContractAPIView):
    permission_classes = [IsLocalOfficer]

    def get(self, request, pk):
        document = get_object_or_404(
            ApplicationDocument.objects.filter(
                application__responsible_authority_id=request.user.local_authority_id,
                application__status__in={
                    Application.Status.SUBMITTED,
                    Application.Status.UNDER_REVIEW,
                    Application.Status.REVISION_REQUIRED,
                    Application.Status.RESUBMITTED,
                    Application.Status.APPROVED,
                    Application.Status.REJECTED,
                },
            ),
            pk=pk,
        )
        return protected_file_response(document)


class OfficerApproveView(ContractAPIView):
    permission_classes = [IsLocalOfficer]
    serializer_class = ApprovalSerializer

    def post(self, request, pk):
        get_object_or_404(officer_applications(request.user), pk=pk)
        serializer = ApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application, license_record = approve_application(
            application_id=pk, actor=request.user, note=serializer.validated_data.get("note", "")
        )
        locale = requested_locale(request)
        return Response(
            {
                "id": application.id,
                "status": application.status,
                "approved_at": application.approved_at,
                "license": {
                    "id": license_record.id,
                    "artifact_kind": license_record.artifact_kind,
                    "license_number": license_record.license_number,
                    "issued_at": license_record.issued_at,
                    "expires_at": license_record.expires_at,
                    "property_type": property_type_data(license_record.property_type, locale),
                    "fee_amount_snapshot": (
                        str(license_record.fee_amount_snapshot)
                        if license_record.fee_amount_snapshot is not None
                        else None
                    ),
                    "currency": license_record.fee_currency_snapshot or None,
                },
            }
        )


class OfficerRequestRevisionView(ContractAPIView):
    permission_classes = [IsLocalOfficer]
    serializer_class = ReasonSerializer

    def post(self, request, pk):
        get_object_or_404(officer_applications(request.user), pk=pk)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = request_application_revision(
            application_id=pk, actor=request.user, reason=serializer.validated_data["reason"]
        )
        return Response(
            {
                "id": application.id,
                "status": application.status,
                "applicant_action_required": True,
                "reason": serializer.validated_data["reason"],
                "changed_at": waiting_since(application),
            }
        )


class OfficerRejectView(ContractAPIView):
    permission_classes = [IsLocalOfficer]
    serializer_class = ReasonSerializer

    def post(self, request, pk):
        get_object_or_404(officer_applications(request.user), pk=pk)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = reject_application(
            application_id=pk, actor=request.user, reason=serializer.validated_data["reason"]
        )
        return Response(
            {
                "id": application.id,
                "status": application.status,
                "reason": serializer.validated_data["reason"],
                "changed_at": waiting_since(application),
            }
        )


def central_timing_analytics(queryset):
    now = timezone.now()
    total_seconds = defaultdict(float)
    sample_counts = Counter()
    overdue_by_stage = Counter()
    overdue_threshold = timedelta(days=settings.CENTRAL_OVERDUE_THRESHOLD_DAYS)

    for application in queryset.prefetch_related("status_history"):
        events = list(application.status_history.all())
        stage_seconds = defaultdict(float)
        if events:
            interval_start = application.created_at
            interval_status = Application.Status.DRAFT
            for event in events:
                interval_end = min(event.created_at, now)
                if interval_end > interval_start:
                    stage = current_stage(interval_status)
                    if stage != "COMPLETED":
                        stage_seconds[stage] += (interval_end - interval_start).total_seconds()
                interval_start = event.created_at
                interval_status = event.to_status
            interval_status = application.status
        else:
            interval_status = application.status
            interval_start = application.submitted_at or application.updated_at

        if current_stage(interval_status) != "COMPLETED" and now > interval_start:
            stage_seconds[current_stage(interval_status)] += (now - interval_start).total_seconds()
        for stage, seconds in stage_seconds.items():
            total_seconds[stage] += seconds
            sample_counts[stage] += 1

        active_stage = current_stage(application.status)
        if active_stage != "COMPLETED":
            waiting_start = events[-1].created_at if events else (application.submitted_at or application.updated_at)
            if now - waiting_start >= overdue_threshold:
                overdue_by_stage[active_stage] += 1

    stage_order = ["APPLICANT_PREPARATION", "LOCAL_OFFICER_REVIEW", "APPLICANT_ACTION"]
    return {
        "average_wait_by_stage": [
            {
                "stage": stage,
                "average_hours": round(total_seconds[stage] / sample_counts[stage] / 3600, 1),
                "sample_count": sample_counts[stage],
            }
            for stage in stage_order
            if sample_counts[stage]
        ],
        "overdue": {
            "threshold_days": settings.CENTRAL_OVERDUE_THRESHOLD_DAYS,
            "total": sum(overdue_by_stage.values()),
            "by_stage": [
                {"stage": stage, "count": overdue_by_stage[stage]}
                for stage in stage_order
                if overdue_by_stage[stage]
            ],
        },
    }


def anonymous_officer_reference(user_id, period):
    return "OFF-" + salted_hmac(
        f"anonymous-workload:{period}",
        str(user_id),
    ).hexdigest()[:8].upper()


def anonymous_workload_analytics():
    period_start = timezone.localtime(timezone.now()).replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    period = period_start.strftime("%Y-%m")
    actions = defaultdict(lambda: {"document_reviews": 0, "application_decisions": 0})
    for row in (
        DocumentReview.objects.filter(
            reviewed_at__gte=period_start,
            reviewer__role=User.Role.LOCAL_OFFICER,
        )
        .values("reviewer_id")
        .annotate(count=Count("id"))
    ):
        actions[row["reviewer_id"]]["document_reviews"] = row["count"]
    for row in (
        ApplicationStatusHistory.objects.filter(
            created_at__gte=period_start,
            actor__role=User.Role.LOCAL_OFFICER,
            to_status__in=[Application.Status.APPROVED, Application.Status.REJECTED],
        )
        .values("actor_id")
        .annotate(count=Count("id"))
    ):
        actions[row["actor_id"]]["application_decisions"] = row["count"]

    minimum_group_size = settings.ANONYMOUS_WORKLOAD_MIN_GROUP_SIZE
    if len(actions) < minimum_group_size:
        return {
            "period": period,
            "minimum_group_size": minimum_group_size,
            "contributor_count": None,
            "suppressed": True,
            "rows": [],
        }
    rows = []
    for user_id, counts in actions.items():
        rows.append(
            {
                "officer_reference": anonymous_officer_reference(user_id, period),
                **counts,
                "total_actions": counts["document_reviews"] + counts["application_decisions"],
            }
        )
    rows.sort(key=lambda item: item["officer_reference"])
    return {
        "period": period,
        "minimum_group_size": minimum_group_size,
        "contributor_count": len(rows),
        "suppressed": False,
        "rows": rows,
    }


def central_assistance_data(item):
    return {
        "reference": str(item.reference_token),
        "question_code": item.question_code,
        "status": item.status,
        "snapshot": {
            "property_type_code": item.property_type_code_snapshot or None,
            "classification_outcome": item.classification_outcome_snapshot,
            "rooms": item.rooms_snapshot,
            "max_guests": item.max_guests_snapshot,
            "has_restaurant": item.restaurant_snapshot,
            "application_status": item.application_status_snapshot,
            "required_documents": item.required_documents_snapshot,
            "approved_documents": item.approved_documents_snapshot,
        },
        "resolution_code": item.resolution_code or None,
        "requested_at": item.requested_at,
        "resolved_at": item.resolved_at,
    }


class OfficerCentralAssistanceView(ContractAPIView):
    permission_classes = [IsLocalOfficer]
    serializer_class = CentralAssistanceRequestSerializer

    def post(self, request, pk):
        application = get_object_or_404(officer_applications(request.user), pk=pk)
        if application.status not in {
            Application.Status.SUBMITTED,
            Application.Status.UNDER_REVIEW,
            Application.Status.RESUBMITTED,
        }:
            raise DomainError(
                "ASSISTANCE_NOT_AVAILABLE",
                "Central assistance is available only while the application is under local review.",
                http_status=status.HTTP_409_CONFLICT,
            )
        serializer = CentralAssistanceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if application.central_assistance_requests.filter(status=CentralAssistanceRequest.Status.OPEN).exists():
            raise DomainError(
                "ASSISTANCE_ALREADY_OPEN",
                "This application already has an open central-assistance request.",
                http_status=status.HTTP_409_CONFLICT,
            )
        state = requirement_state(application)
        with transaction.atomic():
            item = CentralAssistanceRequest.objects.create(
                application=application,
                requested_by=request.user,
                question_code=serializer.validated_data["question_code"],
                property_type_code_snapshot=(
                    application.confirmed_property_type.code if application.confirmed_property_type else ""
                ),
                classification_outcome_snapshot=application.classification_outcome_snapshot,
                rooms_snapshot=application.rooms_snapshot,
                max_guests_snapshot=application.max_guests_snapshot,
                restaurant_snapshot=application.restaurant_snapshot,
                application_status_snapshot=application.status,
                required_documents_snapshot=state["required"],
                approved_documents_snapshot=state["approved"],
            )
            audit_event(actor=request.user, action="CENTRAL_ASSISTANCE_REQUESTED", obj=item)
        return Response(central_assistance_data(item), status=status.HTTP_201_CREATED)


def discussion_message_data(message):
    return {
        "id": message.id,
        "sender_category": message.sender.role,
        "body": message.body,
        "created_at": message.created_at,
    }


class ApplicationDiscussionView(ContractAPIView):
    permission_classes = [IsApplicant]
    serializer_class = DiscussionMessageSerializer

    def get_application(self, request, pk):
        return get_object_or_404(Application.objects.filter(property__owner=request.user), pk=pk)

    def get(self, request, pk):
        application = self.get_application(request, pk)
        return Response({"results": [discussion_message_data(item) for item in application.discussion_messages.all()]})

    def post(self, request, pk):
        application = self.get_application(request, pk)
        return create_discussion_message(request, application)


class OfficerApplicationDiscussionView(ContractAPIView):
    permission_classes = [IsLocalOfficer]
    serializer_class = DiscussionMessageSerializer

    def get_application(self, request, pk):
        return get_object_or_404(officer_applications(request.user), pk=pk)

    def get(self, request, pk):
        application = self.get_application(request, pk)
        return Response({"results": [discussion_message_data(item) for item in application.discussion_messages.all()]})

    def post(self, request, pk):
        application = self.get_application(request, pk)
        return create_discussion_message(request, application)


def create_discussion_message(request, application):
    if application.status not in {
        Application.Status.SUBMITTED,
        Application.Status.UNDER_REVIEW,
        Application.Status.REVISION_REQUIRED,
        Application.Status.RESUBMITTED,
    }:
        raise DomainError(
            "DISCUSSION_CLOSED",
            "Messages are available only while the submitted application is active.",
        )
    serializer = DiscussionMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        message = DiscussionMessage.objects.create(
            application=application,
            sender=request.user,
            body=serializer.validated_data["body"],
        )
        audit_event(actor=request.user, action="DISCUSSION_MESSAGE_CREATED", obj=message)
    return Response(discussion_message_data(message), status=status.HTTP_201_CREATED)


class CentralAssistanceListView(ContractAPIView):
    permission_classes = [IsCentralOfficer]

    def get(self, request):
        queryset = CentralAssistanceRequest.objects.all()
        requested_status = request.query_params.get("status")
        if requested_status:
            if requested_status not in CentralAssistanceRequest.Status.values:
                raise DomainError("INVALID_ASSISTANCE_STATUS", "Unknown assistance status.")
            queryset = queryset.filter(status=requested_status)
        return Response({"results": [central_assistance_data(item) for item in queryset[:100]]})


class CentralAssistanceResolveView(ContractAPIView):
    permission_classes = [IsCentralOfficer]
    serializer_class = CentralAssistanceResolutionSerializer

    def post(self, request, token):
        serializer = CentralAssistanceResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            item = get_object_or_404(
                CentralAssistanceRequest.objects.select_for_update(),
                reference_token=token,
            )
            if item.status != CentralAssistanceRequest.Status.OPEN:
                raise DomainError(
                    "ASSISTANCE_ALREADY_RESOLVED",
                    "This assistance request is already resolved.",
                    http_status=status.HTTP_409_CONFLICT,
                )
            item.status = CentralAssistanceRequest.Status.RESOLVED
            item.resolution_code = serializer.validated_data["resolution_code"]
            item.resolved_by = request.user
            item.resolved_at = timezone.now()
            item.save(update_fields=["status", "resolution_code", "resolved_by", "resolved_at"])
            audit_event(actor=request.user, action="CENTRAL_ASSISTANCE_RESOLVED", obj=item)
        return Response(central_assistance_data(item))


class CentralSummaryView(ContractAPIView):
    permission_classes = [IsCentralOfficer]

    def get(self, request):
        queryset = Application.objects.all()
        locale = requested_locale(request)
        status_counts = Counter(dict(queryset.values_list("status").annotate(count=Count("id"))))
        by_type_rows = queryset.values("confirmed_property_type_id").annotate(count=Count("id")).order_by()
        authority_type_rows = (
            queryset.values("responsible_authority_id", "confirmed_property_type_id")
            .annotate(count=Count("id"))
            .order_by()
        )
        type_ids = {
            row["confirmed_property_type_id"]
            for row in [*by_type_rows, *authority_type_rows]
            if row["confirmed_property_type_id"]
        }
        types = {
            item.id: item
            for item in PropertyType.objects.filter(id__in=type_ids).prefetch_related("translations")
        }

        def property_type_breakdown(rows):
            breakdown = []
            for row in rows:
                property_type = types.get(row["confirmed_property_type_id"])
                if property_type:
                    translated = translated_value(property_type, locale, fields=("name",))
                    breakdown.append(
                        {
                            "code": property_type.code,
                            "name": translated["name"],
                            "count": row["count"],
                        }
                    )
                else:
                    breakdown.append(
                        {
                            "code": "UNCONFIRMED",
                            "name": "ยังไม่ยืนยัน" if locale != "en" else "Unconfirmed",
                            "count": row["count"],
                        }
                    )
            return sorted(breakdown, key=lambda item: (-item["count"], item["code"]))

        def totals_for(counts, application_count):
            return {
                "applications": application_count,
                "waiting_review": sum(
                    counts[item]
                    for item in (
                        Application.Status.SUBMITTED,
                        Application.Status.UNDER_REVIEW,
                        Application.Status.RESUBMITTED,
                    )
                ),
                "waiting_for_applicant_revision": counts[Application.Status.REVISION_REQUIRED],
                "approved": counts[Application.Status.APPROVED],
            }

        by_property_type = property_type_breakdown(by_type_rows)
        authorities = (
            LocalAuthority.objects.filter(Q(is_active=True) | Q(applications__isnull=False))
            .annotate(count=Count("applications", distinct=True))
            .order_by("id")
        )
        stages = Counter()
        for status_code, count in status_counts.items():
            stages[current_stage(status_code)] += count

        authority_status_counts = defaultdict(Counter)
        authority_stages = defaultdict(Counter)
        for row in (
            queryset.values("responsible_authority_id", "status")
            .annotate(count=Count("id"))
            .order_by()
        ):
            authority_id = row["responsible_authority_id"]
            authority_status_counts[authority_id][row["status"]] = row["count"]
            authority_stages[authority_id][current_stage(row["status"])] += row["count"]

        authority_types = defaultdict(list)
        for row in authority_type_rows:
            authority_types[row["responsible_authority_id"]].append(row)

        authority_breakdown = []
        for authority in authorities:
            authority_breakdown.append(
                {
                    **authority_data(authority),
                    "count": authority.count,
                    "totals": totals_for(authority_status_counts[authority.id], authority.count),
                    "by_property_type": property_type_breakdown(authority_types[authority.id]),
                    "by_current_stage": [
                        {"stage": stage, "count": count}
                        for stage, count in sorted(authority_stages[authority.id].items())
                    ],
                }
            )

        return Response(
            {
                "generated_at": timezone.now(),
                "totals": totals_for(status_counts, queryset.count()),
                "by_property_type": by_property_type,
                "by_local_authority": authority_breakdown,
                "authority_count": len(authority_breakdown),
                "expected_authority_count": settings.EXPECTED_LOCAL_AUTHORITY_COUNT,
                "authority_zeroes_included": True,
                "by_current_stage": [
                    {"stage": stage, "count": count} for stage, count in sorted(stages.items())
                ],
                "timing_analytics": central_timing_analytics(queryset),
                "anonymous_workload": anonymous_workload_analytics(),
            }
        )


class ApplicationLicenseView(ContractAPIView):
    permission_classes = [IsVerifiedUser]

    def get(self, request, pk):
        if request.user.role == User.Role.APPLICANT:
            application = get_object_or_404(owned_applications(request.user), pk=pk)
        elif request.user.role == User.Role.LOCAL_OFFICER and request.user.local_authority_id:
            application = get_object_or_404(officer_applications(request.user), pk=pk)
        else:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied()
        try:
            license_record = application.license
        except License.DoesNotExist:
            raise DomainError("LICENSE_NOT_AVAILABLE", "A license is not available for this application.")
        locale = requested_locale(request)
        property_record = application.property
        return Response(
            {
                "id": license_record.id,
                "artifact_kind": license_record.artifact_kind,
                "license_number": license_record.license_number,
                "application_reference_number": application.reference_number,
                "property": {
                    "name": property_record.name,
                    "address": " ".join(
                        filter(
                            None,
                            [
                                property_record.address_line,
                                property_record.subdistrict,
                                property_record.district,
                                property_record.province,
                                property_record.postal_code,
                            ],
                        )
                    ),
                },
                "property_type": property_type_data(license_record.property_type, locale),
                "issuing_authority": authority_data(application.responsible_authority),
                "issued_at": license_record.issued_at,
                "expires_at": license_record.expires_at,
                "fee": (
                    {
                        "amount_snapshot": str(license_record.fee_amount_snapshot),
                        "currency": license_record.fee_currency_snapshot,
                        "fee_schedule_id": license_record.fee_schedule_id,
                    }
                    if license_record.fee_amount_snapshot is not None
                    else None
                ),
                "public_verification": public_verification_links(license_record),
            }
        )


class PublicLicenseVerificationView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: PublicLicenseVerificationOutputSerializer})
    def get(self, request, token):
        license_record = get_object_or_404(
            License.objects.select_related(
                "application__property",
                "application__responsible_authority",
                "property_type",
            ),
            verification_token=token,
        )
        return Response(public_license_data(license_record, requested_locale(request)))


class PublicLicenseQrView(ContractAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={(200, "image/svg+xml"): bytes})
    def get(self, request, token):
        license_record = get_object_or_404(License, verification_token=token)
        image = qrcode.make(
            public_verification_links(license_record)["verification_url"],
            image_factory=SvgPathImage,
            border=2,
        )
        stream = io.BytesIO()
        image.save(stream)
        response = HttpResponse(stream.getvalue(), content_type="image/svg+xml")
        response["Content-Disposition"] = 'inline; filename="license-verification-qr.svg"'
        response["Cache-Control"] = "public, max-age=86400"
        return response
