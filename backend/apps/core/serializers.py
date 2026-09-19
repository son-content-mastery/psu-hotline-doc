from collections.abc import Mapping

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import CentralAssistanceRequest, DocumentReview, ThaiSubdistrict, User


class StrictSerializer(serializers.Serializer):
    """Reject fields outside the explicit API allowlist instead of silently dropping them."""

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data.keys()) - set(self.fields.keys())
        if unknown:
            raise serializers.ValidationError({key: ["This field is not allowed."] for key in sorted(unknown)})
        return super().to_internal_value(data)


class EmptySerializer(serializers.Serializer):
    pass


class StrictBooleanField(serializers.BooleanField):
    default_error_messages = {"invalid": "Must be a JSON boolean."}

    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid")
        return data


class LoginSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class RegistrationSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    password_confirmation = serializers.CharField(trim_whitespace=False, write_only=True)
    terms_accepted = StrictBooleanField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError({"password_confirmation": ["Passwords do not match."]})
        if attrs["terms_accepted"] is not True:
            raise serializers.ValidationError({"terms_accepted": ["Acceptance is required."]})
        candidate = User(
            email=attrs["email"].strip().lower(),
            display_name="Applicant",
            role=User.Role.APPLICANT,
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages})
        return attrs


class ActivationResendSerializer(StrictSerializer):
    email = serializers.EmailField()


class ActivationConfirmSerializer(StrictSerializer):
    token = serializers.CharField(max_length=1024)


class RegistrationAcceptedOutputSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()


class ActivationCompleteOutputSerializer(serializers.Serializer):
    activated = serializers.BooleanField()


class PasswordResetRequestSerializer(StrictSerializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(StrictSerializer):
    uid = serializers.CharField(max_length=255)
    token = serializers.CharField(max_length=255)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)


class PasswordResetAcceptedOutputSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()


class PasswordResetCompleteOutputSerializer(serializers.Serializer):
    reset = serializers.BooleanField()


class ClassificationInputSerializer(StrictSerializer):
    rooms = serializers.IntegerField(min_value=1)
    guests = serializers.IntegerField(min_value=1)
    has_restaurant = StrictBooleanField()


class PropertyInputSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255)
    address_line = serializers.CharField(max_length=255)
    subdistrict_code = serializers.SlugRelatedField(
        slug_field="code",
        source="administrative_subdistrict",
        queryset=ThaiSubdistrict.objects.filter(
            is_active=True,
            district__is_active=True,
            district__province__is_active=True,
            district__province__code="83",
        ).select_related("district__province"),
    )
    local_authority_id = serializers.IntegerField(min_value=1)


class ApplicationCreateSerializer(StrictSerializer):
    property = PropertyInputSerializer()
    classification_answers = ClassificationInputSerializer()


class PropertyPatchSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, required=False)
    address_line = serializers.CharField(max_length=255, required=False)
    subdistrict_code = serializers.SlugRelatedField(
        slug_field="code",
        source="administrative_subdistrict",
        queryset=ThaiSubdistrict.objects.filter(
            is_active=True,
            district__is_active=True,
            district__province__is_active=True,
            district__province__code="83",
        ).select_related("district__province"),
        required=False,
    )
    local_authority_id = serializers.IntegerField(min_value=1, required=False)


class ApplicationPatchSerializer(StrictSerializer):
    property = PropertyPatchSerializer(required=False)
    classification_answers = ClassificationInputSerializer(required=False)


class SubmitSerializer(StrictSerializer):
    confirm_information_is_correct = serializers.BooleanField()

    def validate_confirm_information_is_correct(self, value):
        if value is not True:
            raise serializers.ValidationError("Confirmation is required.")
        return value


class UploadSerializer(StrictSerializer):
    document_type_id = serializers.IntegerField(min_value=1)
    file = serializers.FileField(required=False)
    files = serializers.ListField(child=serializers.FileField(), required=False, allow_empty=False, max_length=10)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("file") and not attrs.get("files"):
            raise serializers.ValidationError({"files": ["Select at least one file."]})
        if attrs.get("file") and attrs.get("files"):
            raise serializers.ValidationError({"files": ["Use either file or files, not both."]})
        return attrs


class DocumentReviewSerializer(StrictSerializer):
    outcome = serializers.ChoiceField(choices=DocumentReview.Outcome.choices)
    reason = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class ReasonSerializer(StrictSerializer):
    reason = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True, default="")


class ApprovalSerializer(StrictSerializer):
    note = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class CentralAssistanceRequestSerializer(StrictSerializer):
    question_code = serializers.ChoiceField(choices=CentralAssistanceRequest.QuestionCode.choices)


class CentralAssistanceResolutionSerializer(StrictSerializer):
    resolution_code = serializers.ChoiceField(choices=CentralAssistanceRequest.ResolutionCode.choices)


# Explicit response schemas keep drf-spectacular aligned with the richer MVP payloads.
class AuthorityOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class ThaiSubdistrictOutputSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    postal_code = serializers.CharField()


class ThaiDistrictOutputSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    subdistricts = ThaiSubdistrictOutputSerializer(many=True)


class ThaiLocationCatalogOutputSerializer(serializers.Serializer):
    province = serializers.DictField()
    districts = ThaiDistrictOutputSerializer(many=True)


class PropertyTypeOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True)
    issues_license = serializers.BooleanField()


class PublicLicenseVerificationOutputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["VALID", "EXPIRED", "RECORDED"])
    artifact_kind = serializers.ChoiceField(choices=["HOTEL_LICENSE", "NOTIFICATION_ACKNOWLEDGEMENT"])
    license_number = serializers.CharField()
    property = serializers.DictField()
    property_type = PropertyTypeOutputSerializer()
    issuing_authority = AuthorityOutputSerializer()
    issued_at = serializers.DateTimeField()
    expires_at = serializers.DateField(allow_null=True)
    checked_at = serializers.DateTimeField()


class DocumentTypeOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    instructions = serializers.CharField(allow_null=True)
    category = serializers.ChoiceField(choices=["OPERATOR_PREPARED", "EXTERNAL_AGENCY"])
    allows_multiple_files = serializers.BooleanField()
    translation_fallback = serializers.BooleanField()


class ReviewerOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class DocumentReviewOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    outcome = serializers.ChoiceField(choices=["APPROVED", "REVISION_REQUIRED", "REJECTED"])
    reason = serializers.CharField(allow_null=True)
    reviewed_at = serializers.DateTimeField()
    reviewed_by = ReviewerOutputSerializer()


class UploaderOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()
    role = serializers.ChoiceField(choices=["APPLICANT", "LOCAL_OFFICER", "CENTRAL_OFFICER", "SUPER_ADMIN"])


class DocumentPreflightOutputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["PASS", "WARNING", "LIMITED"])
    issue_codes = serializers.ListField(child=serializers.CharField())
    analyzer_version = serializers.CharField()
    type_check_status = serializers.ChoiceField(
        choices=["NOT_RUN", "MATCH", "POSSIBLE_MISMATCH", "INCONCLUSIVE", "UNAVAILABLE", "NOT_APPLICABLE"]
    )
    detected_family = serializers.CharField(allow_null=True)
    type_analyzer_version = serializers.CharField(allow_null=True)
    analyzed_at = serializers.DateTimeField()


class OfficerDocumentVersionOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    application_id = serializers.IntegerField()
    document_type = DocumentTypeOutputSerializer()
    version = serializers.IntegerField()
    attachment_index = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["UPLOADED", "APPROVED", "REVISION_REQUIRED", "REJECTED"])
    is_current = serializers.BooleanField()
    version_label = serializers.ChoiceField(choices=["CURRENT", "PRIOR"])
    category = serializers.ChoiceField(choices=["OPERATOR_PREPARED", "EXTERNAL_AGENCY"])
    original_filename = serializers.CharField()
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    uploaded_at = serializers.DateTimeField()
    uploaded_by = UploaderOutputSerializer()
    uploader_role = serializers.CharField()
    latest_review_reason = serializers.CharField(allow_null=True)
    download_url = serializers.CharField()
    preflight = DocumentPreflightOutputSerializer(allow_null=True)
    reviews = DocumentReviewOutputSerializer(many=True)
    is_in_submitted_checklist = serializers.BooleanField()
    reviewable = serializers.BooleanField()


class OfficerDocumentOutputSerializer(OfficerDocumentVersionOutputSerializer):
    versions = OfficerDocumentVersionOutputSerializer(many=True)


class ApplicationPropertyOutputSerializer(serializers.Serializer):
    name = serializers.CharField()
    address_line = serializers.CharField()
    province_code = serializers.CharField(allow_null=True)
    district_code = serializers.CharField(allow_null=True)
    subdistrict_code = serializers.CharField(allow_null=True)
    subdistrict = serializers.CharField()
    district = serializers.CharField()
    province = serializers.CharField()
    postal_code = serializers.CharField()
    local_authority = AuthorityOutputSerializer()


class ClassificationAnswersOutputSerializer(serializers.Serializer):
    rooms = serializers.IntegerField()
    guests = serializers.IntegerField()
    has_restaurant = serializers.BooleanField()


class ClassificationOutputSerializer(serializers.Serializer):
    outcome = serializers.CharField()
    property_type = PropertyTypeOutputSerializer(allow_null=True)
    answers = ClassificationAnswersOutputSerializer()


class OfficerApplicationDetailOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_number = serializers.CharField()
    status = serializers.CharField()
    waiting_since = serializers.DateTimeField(allow_null=True)
    submitted_at = serializers.DateTimeField(allow_null=True)
    resubmitted_at = serializers.DateTimeField(allow_null=True)
    property = ApplicationPropertyOutputSerializer()
    classification = ClassificationOutputSerializer()
    documents = OfficerDocumentOutputSerializer(many=True)
    all_required_documents_approved = serializers.BooleanField()
    allowed_actions = serializers.ListField(child=serializers.ChoiceField(choices=["REVIEW_DOCUMENTS", "REQUEST_REVISION", "APPROVE", "REJECT"]))


class OfficerQueueItemOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_number = serializers.CharField()
    property_name = serializers.CharField()
    property_type = PropertyTypeOutputSerializer(allow_null=True)
    status = serializers.CharField()
    submitted_at = serializers.DateTimeField(allow_null=True)
    resubmitted_at = serializers.DateTimeField(allow_null=True)
    waiting_since = serializers.DateTimeField(allow_null=True)
    documents_pending_review = serializers.IntegerField()


class PaginatedOfficerQueueOutputSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = OfficerQueueItemOutputSerializer(many=True)


class CaseStudyClassificationOutputSerializer(serializers.Serializer):
    rooms = serializers.IntegerField()
    guests = serializers.IntegerField()
    has_restaurant = serializers.BooleanField()
    outcome = serializers.CharField()


class CaseStudyDocumentSummaryOutputSerializer(serializers.Serializer):
    required = serializers.IntegerField()
    current_approved = serializers.IntegerField()
    versions_reviewed = serializers.IntegerField()


class CaseStudyPropertyTypeOutputSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class CaseStudyOutputSerializer(serializers.Serializer):
    case_reference = serializers.CharField()
    decision = serializers.ChoiceField(choices=["APPROVED", "REJECTED"])
    property_type = CaseStudyPropertyTypeOutputSerializer()
    classification = CaseStudyClassificationOutputSerializer()
    revision_rounds = serializers.IntegerField()
    processing_days = serializers.IntegerField(allow_null=True)
    decided_at = serializers.DateTimeField()
    documents = CaseStudyDocumentSummaryOutputSerializer()


class CaseLibraryFaqOutputSerializer(serializers.Serializer):
    slug = serializers.CharField()
    question = serializers.CharField()
    answer = serializers.CharField()
    updated_at = serializers.DateTimeField()


class PaginatedCaseLibraryOutputSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = CaseStudyOutputSerializer(many=True)
    faqs = CaseLibraryFaqOutputSerializer(many=True)


class RequirementsSummaryOutputSerializer(serializers.Serializer):
    required = serializers.IntegerField()
    approved = serializers.IntegerField()
    current_uploads = serializers.IntegerField()
    complete_for_submission = serializers.BooleanField()


class LicenseRenewalSummaryOutputSerializer(serializers.Serializer):
    expires_at = serializers.DateField()
    days_remaining = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["UPCOMING", "DUE", "EXPIRED"])
    action_required = serializers.BooleanField()


class ApplicantApplicationListItemOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_number = serializers.CharField(allow_null=True)
    property_name = serializers.CharField()
    property_type = PropertyTypeOutputSerializer(allow_null=True)
    responsible_authority = AuthorityOutputSerializer(allow_null=True)
    status = serializers.CharField()
    current_stage = serializers.CharField()
    applicant_action_required = serializers.BooleanField()
    waiting_since = serializers.DateTimeField(allow_null=True)
    requirements = RequirementsSummaryOutputSerializer()
    renewal = LicenseRenewalSummaryOutputSerializer(allow_null=True)
    updated_at = serializers.DateTimeField()


class ApplicantApplicationSummaryOutputSerializer(serializers.Serializer):
    needs_action = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    approved = serializers.IntegerField()
    total = serializers.IntegerField()


class PaginatedApplicantApplicationOutputSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = ApplicantApplicationListItemOutputSerializer(many=True)
    summary = ApplicantApplicationSummaryOutputSerializer()


class RequirementGuidanceOutputSerializer(serializers.Serializer):
    issuing_agency = serializers.DictField(allow_null=True)
    responsible_local_authority = serializers.DictField(allow_null=True)
    contact = serializers.CharField(allow_null=True)
    contact_phone = serializers.CharField(allow_null=True)
    contact_email = serializers.CharField(allow_null=True)
    source_url = serializers.CharField(allow_null=True)
    instructions = serializers.CharField(allow_null=True)
    required_supporting_items = serializers.ListField(child=serializers.CharField())
    approximate_processing_days = serializers.IntegerField(allow_null=True)
    translation_fallback = serializers.BooleanField()


class RequirementItemOutputSerializer(serializers.Serializer):
    requirement_id = serializers.IntegerField(required=False)
    document_type = DocumentTypeOutputSerializer()
    required = serializers.BooleanField()
    step_code = serializers.ChoiceField(choices=["APPLICANT", "PREMISES", "FACILITIES", "SAFETY", "MANAGER"])
    status = serializers.CharField(required=False)
    current_document_id = serializers.IntegerField(required=False, allow_null=True)
    current_document_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    latest_review_reason = serializers.CharField(required=False, allow_null=True)
    description = serializers.CharField(allow_null=True)
    instructions = serializers.CharField(allow_null=True)
    guidance = RequirementGuidanceOutputSerializer(allow_null=True)


class RequirementGroupOutputSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=["OPERATOR_PREPARED", "EXTERNAL_AGENCY"])
    items = RequirementItemOutputSerializer(many=True)


class RequirementStepOutputSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=["APPLICANT", "PREMISES", "FACILITIES", "SAFETY", "MANAGER"])
    order = serializers.IntegerField()
    required = serializers.IntegerField()
    completed = serializers.IntegerField()
    action_required = serializers.IntegerField()
    complete = serializers.BooleanField()
    items = RequirementItemOutputSerializer(many=True)


class RequirementsOutputSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(required=False)
    property_type = PropertyTypeOutputSerializer(required=False)
    is_legally_validated_checklist = serializers.BooleanField()
    disclaimer = serializers.CharField()
    complete_for_submission = serializers.BooleanField(required=False)
    groups = RequirementGroupOutputSerializer(many=True)
    steps = RequirementStepOutputSerializer(many=True)


class HistoryDocumentTypeOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class HistoryEventOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    from_status = serializers.CharField(allow_null=True)
    to_status = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    reason = serializers.CharField(allow_null=True)
    actor_category = serializers.CharField()
    document_type = HistoryDocumentTypeOutputSerializer(allow_null=True)
    affected_documents = HistoryDocumentTypeOutputSerializer(many=True)


class HistoryOutputSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    current_status = serializers.CharField()
    waiting_since = serializers.DateTimeField(allow_null=True)
    applicant_action_required = serializers.BooleanField()
    events = HistoryEventOutputSerializer(many=True)
