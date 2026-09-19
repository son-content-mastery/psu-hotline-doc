import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class LocalAuthority(models.Model):
    code = models.CharField(max_length=80, unique=True)
    official_name = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "local authorities"

    def __str__(self):
        return f"{self.code} — {self.official_name}"


class ThaiProvince(models.Model):
    code = models.CharField(max_length=2, unique=True)
    name_th = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name_th}"


class ThaiDistrict(models.Model):
    code = models.CharField(max_length=4, unique=True)
    province = models.ForeignKey(ThaiProvince, on_delete=models.PROTECT, related_name="districts")
    name_th = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name_th}"


class ThaiSubdistrict(models.Model):
    code = models.CharField(max_length=6, unique=True)
    district = models.ForeignKey(ThaiDistrict, on_delete=models.PROTECT, related_name="subdistricts")
    name_th = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name_th}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.SUPER_ADMIN)
        extra_fields.setdefault("email_verified_at", timezone.now())
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Language(models.TextChoices):
        THAI = "th", "Thai"
        ENGLISH = "en", "English"

    class Role(models.TextChoices):
        APPLICANT = "APPLICANT", "Applicant"
        LOCAL_OFFICER = "LOCAL_OFFICER", "Local officer"
        CENTRAL_OFFICER = "CENTRAL_OFFICER", "Central officer"
        SUPER_ADMIN = "SUPER_ADMIN", "Super admin"

    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=255)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.APPLICANT)
    preferred_language = models.CharField(max_length=10, choices=Language.choices, default=Language.THAI)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    local_authority = models.ForeignKey(
        LocalAuthority,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="officers",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]
    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
            models.CheckConstraint(
                check=(Q(role="LOCAL_OFFICER", local_authority__isnull=False) | ~Q(role="LOCAL_OFFICER")),
                name="local_officer_has_authority",
            ),
            models.CheckConstraint(
                check=(Q(role="LOCAL_OFFICER") | Q(local_authority__isnull=True)),
                name="only_local_officer_authority",
            ),
            models.CheckConstraint(
                check=(~Q(role="SUPER_ADMIN") | Q(is_staff=True)),
                name="super_admin_is_staff",
            ),
        ]
        indexes = [models.Index(fields=["role", "local_authority"], name="user_role_authority_idx")]

    def clean(self):
        super().clean()
        self.email = self.email.lower().strip()
        if self.role == self.Role.LOCAL_OFFICER and not self.local_authority_id:
            raise ValidationError({"local_authority": "Local officers require an authority."})
        if self.role != self.Role.LOCAL_OFFICER and self.local_authority_id:
            raise ValidationError({"local_authority": "Only local officers may have an authority."})
        if self.role == self.Role.SUPER_ADMIN and not self.is_staff:
            raise ValidationError({"is_staff": "Super admins must be staff users."})

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        if self.pk:
            previous_email = type(self).objects.filter(pk=self.pk).values_list("email", flat=True).first()
            if previous_email is not None and previous_email != self.email:
                self.email_verified_at = None
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"email_verified_at"}
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class PropertyType(models.Model):
    code = models.CharField(max_length=50, unique=True)
    issues_license = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class PropertyTypeTranslation(models.Model):
    property_type = models.ForeignKey(PropertyType, on_delete=models.CASCADE, related_name="translations")
    language_code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["property_type", "language_code"], name="uniq_property_type_lang")
        ]

    def __str__(self):
        return f"{self.property_type.code}:{self.language_code}"


class ClassificationRule(models.Model):
    class Outcome(models.TextChoices):
        NOT_HOTEL = "NOT_HOTEL", "Not a hotel"
        TYPE_1 = "TYPE_1", "Type 1"
        TYPE_2 = "TYPE_2", "Type 2"
        OUT_OF_SCOPE = "OUT_OF_SCOPE", "Out of scope"
        REQUIRES_LICENSE_REVIEW = "REQUIRES_LICENSE_REVIEW", "Requires license review"

    code = models.CharField(max_length=80, unique=True)
    priority = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    min_rooms = models.PositiveIntegerField(null=True, blank=True)
    max_rooms = models.PositiveIntegerField(null=True, blank=True)
    min_guests = models.PositiveIntegerField(null=True, blank=True)
    max_guests = models.PositiveIntegerField(null=True, blank=True)
    restaurant_value = models.BooleanField(null=True, blank=True)
    outcome_code = models.CharField(max_length=50, choices=Outcome.choices)
    result_property_type = models.ForeignKey(
        PropertyType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="classification_rules",
    )
    guidance_key = models.CharField(max_length=120, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["priority"], condition=Q(is_active=True), name="uniq_active_rule_priority"
            ),
            models.CheckConstraint(
                check=Q(min_rooms__isnull=True) | Q(max_rooms__isnull=True) | Q(min_rooms__lte=models.F("max_rooms")),
                name="rule_valid_room_bounds",
            ),
            models.CheckConstraint(
                check=Q(min_guests__isnull=True) | Q(max_guests__isnull=True) | Q(min_guests__lte=models.F("max_guests")),
                name="rule_valid_guest_bounds",
            ),
        ]

    def clean(self):
        errors = {}
        if self.min_rooms and self.max_rooms and self.min_rooms > self.max_rooms:
            errors["max_rooms"] = "Must be at least min_rooms."
        if self.min_guests and self.max_guests and self.min_guests > self.max_guests:
            errors["max_guests"] = "Must be at least min_guests."
        needs_type = self.outcome_code in {self.Outcome.TYPE_1, self.Outcome.TYPE_2}
        allows_type = needs_type or self.outcome_code == self.Outcome.NOT_HOTEL
        if needs_type and not self.result_property_type_id:
            errors["result_property_type"] = "A licensed outcome requires a property type."
        if not allows_type and self.result_property_type_id:
            errors["result_property_type"] = "This outcome must not assign a property type."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.code


class IssuingAgency(models.Model):
    code = models.CharField(max_length=80, unique=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    website_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "issuing agencies"

    def __str__(self):
        return self.code


class IssuingAgencyTranslation(models.Model):
    issuing_agency = models.ForeignKey(IssuingAgency, on_delete=models.CASCADE, related_name="translations")
    language_code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    contact_notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issuing_agency", "language_code"], name="uniq_agency_lang")
        ]


class DocumentType(models.Model):
    class Category(models.TextChoices):
        OPERATOR_PREPARED = "OPERATOR_PREPARED", "Operator prepared"
        EXTERNAL_AGENCY = "EXTERNAL_AGENCY", "External agency"

    code = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=30, choices=Category.choices)
    issuing_agency = models.ForeignKey(
        IssuingAgency,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_types",
    )
    approximate_processing_days = models.PositiveIntegerField(null=True, blank=True)
    allows_multiple_files = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def clean(self):
        if self.category == self.Category.EXTERNAL_AGENCY and not self.issuing_agency_id:
            raise ValidationError({"issuing_agency": "External documents require an issuing agency."})

    def __str__(self):
        return self.code


class DocumentTypeTranslation(models.Model):
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name="translations")
    language_code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    supporting_items = models.TextField(blank=True, help_text="One display item per line.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document_type", "language_code"], name="uniq_document_type_lang")
        ]


class RequirementStep(models.TextChoices):
    APPLICANT = "APPLICANT", "Applicant and business"
    PREMISES = "PREMISES", "Premises and legal right"
    FACILITIES = "FACILITIES", "Rooms and facilities"
    SAFETY = "SAFETY", "Safety and compliance"
    MANAGER = "MANAGER", "Accommodation manager"


class PropertyTypeDocumentRequirement(models.Model):
    property_type = models.ForeignKey(PropertyType, on_delete=models.PROTECT, related_name="document_requirements")
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name="property_requirements")
    is_required = models.BooleanField(default=True)
    step_code = models.CharField(
        max_length=30,
        choices=RequirementStep.choices,
        default=RequirementStep.APPLICANT,
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["property_type", "document_type"], name="uniq_type_document_req")
        ]


class FeeSchedule(models.Model):
    property_type = models.ForeignKey(PropertyType, on_delete=models.PROTECT, related_name="fee_schedules")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="THB")
    validity_years = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["property_type", "-effective_from"]
        constraints = [
            models.CheckConstraint(check=Q(amount__gte=0), name="fee_nonnegative"),
            models.CheckConstraint(check=Q(validity_years__gt=0), name="fee_validity_positive"),
            models.CheckConstraint(
                check=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from")),
                name="fee_valid_dates",
            ),
            models.UniqueConstraint(
                fields=["property_type", "currency", "effective_from"], name="uniq_fee_effective_start"
            ),
        ]

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Must not precede effective_from."})
        overlap = FeeSchedule.objects.filter(property_type=self.property_type, currency=self.currency).exclude(pk=self.pk)
        if self.effective_to:
            overlap = overlap.filter(effective_from__lte=self.effective_to)
        overlap = overlap.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=self.effective_from))
        if overlap.exists():
            raise ValidationError("Fee schedule periods may not overlap.")


class Property(models.Model):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="properties")
    local_authority = models.ForeignKey(LocalAuthority, on_delete=models.PROTECT, related_name="properties")
    administrative_subdistrict = models.ForeignKey(
        ThaiSubdistrict,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="properties",
    )
    property_type = models.ForeignKey(
        PropertyType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="properties",
    )
    name = models.CharField(max_length=255)
    address_line = models.CharField(max_length=255)
    subdistrict = models.CharField(max_length=120)
    district = models.CharField(max_length=120)
    province = models.CharField(max_length=120, default="ภูเก็ต")
    postal_code = models.CharField(max_length=10)
    rooms = models.PositiveIntegerField()
    max_guests = models.PositiveIntegerField()
    has_restaurant = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Application(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY_TO_SUBMIT = "READY_TO_SUBMIT", "Ready to submit"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        REVISION_REQUIRED = "REVISION_REQUIRED", "Revision required"
        RESUBMITTED = "RESUBMITTED", "Resubmitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="applications")
    responsible_authority = models.ForeignKey(LocalAuthority, on_delete=models.PROTECT, related_name="applications")
    classification_rule = models.ForeignKey(ClassificationRule, on_delete=models.PROTECT, related_name="applications")
    confirmed_property_type = models.ForeignKey(
        PropertyType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    reference_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    rooms_snapshot = models.PositiveIntegerField()
    max_guests_snapshot = models.PositiveIntegerField()
    restaurant_snapshot = models.BooleanField()
    classification_outcome_snapshot = models.CharField(max_length=50, choices=ClassificationRule.Outcome.choices)
    submitted_at = models.DateTimeField(null=True, blank=True)
    resubmitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["property", "status"], name="app_property_status_idx"),
            models.Index(fields=["responsible_authority", "status"], name="app_authority_status_idx"),
        ]

class ApplicationRequirement(models.Model):
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="requirements")
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name="application_requirements")
    is_required = models.BooleanField(default=True)
    step_code = models.CharField(
        max_length=30,
        choices=RequirementStep.choices,
        default=RequirementStep.APPLICANT,
    )
    display_order = models.PositiveIntegerField(default=0)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["application", "document_type"], name="uniq_application_document_req")
        ]


class ImmutableEventMixin(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(f"{type(self).__name__} records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(f"{type(self).__name__} records are immutable.")


class ApplicationStatusHistory(ImmutableEventMixin):
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="status_history")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="status_events")
    from_status = models.CharField(max_length=30, choices=Application.Status.choices)
    to_status = models.CharField(max_length=30, choices=Application.Status.choices)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["application", "-created_at"], name="status_app_created_idx")]


class ApplicationDocument(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        APPROVED = "APPROVED", "Approved"
        REVISION_REQUIRED = "REVISION_REQUIRED", "Revision required"
        REJECTED = "REJECTED", "Rejected"

    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="documents")
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name="application_documents")
    version = models.PositiveIntegerField()
    attachment_index = models.PositiveIntegerField(default=1)
    original_filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=500, unique=True)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.UPLOADED)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="uploaded_documents")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ["document_type_id", "-version", "attachment_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "document_type", "version", "attachment_index"],
                name="uniq_document_attachment_version",
            ),
            models.UniqueConstraint(
                fields=["application", "document_type", "attachment_index"],
                condition=Q(is_current=True),
                name="uniq_current_document_attachment",
            ),
            models.CheckConstraint(check=Q(version__gt=0), name="document_version_positive"),
            models.CheckConstraint(check=Q(attachment_index__gt=0), name="document_attachment_index_positive"),
            models.CheckConstraint(check=Q(size_bytes__gt=0), name="document_size_positive"),
        ]
        indexes = [
            models.Index(fields=["application", "document_type", "is_current"], name="document_current_idx")
        ]


class DocumentPreflight(models.Model):
    class Status(models.TextChoices):
        PASS = "PASS", "No quality warning detected"
        WARNING = "WARNING", "Quality warning detected"
        LIMITED = "LIMITED", "Automated quality check is limited"

    class TypeCheckStatus(models.TextChoices):
        NOT_RUN = "NOT_RUN", "Document-type check was not run"
        MATCH = "MATCH", "Document family appears consistent"
        POSSIBLE_MISMATCH = "POSSIBLE_MISMATCH", "Possible document-family mismatch"
        INCONCLUSIVE = "INCONCLUSIVE", "Document-type check was inconclusive"
        UNAVAILABLE = "UNAVAILABLE", "Document-type check was unavailable"
        NOT_APPLICABLE = "NOT_APPLICABLE", "Document-type OCR is not applicable"

    application_document = models.OneToOneField(
        ApplicationDocument,
        on_delete=models.PROTECT,
        related_name="preflight",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    issue_codes = models.JSONField(default=list)
    analyzer_version = models.CharField(max_length=30)
    type_check_status = models.CharField(
        max_length=30,
        choices=TypeCheckStatus.choices,
        default=TypeCheckStatus.NOT_RUN,
    )
    detected_family = models.CharField(max_length=40, blank=True)
    type_analyzer_version = models.CharField(max_length=30, blank=True)
    analyzed_at = models.DateTimeField(auto_now_add=True)


class DocumentReview(ImmutableEventMixin):
    class Outcome(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REVISION_REQUIRED = "REVISION_REQUIRED", "Revision required"
        REJECTED = "REJECTED", "Rejected"

    application_document = models.ForeignKey(ApplicationDocument, on_delete=models.PROTECT, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="document_reviews")
    outcome = models.CharField(max_length=30, choices=Outcome.choices)
    reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["reviewed_at", "id"]


class DiscussionMessage(ImmutableEventMixin):
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="discussion_messages")
    sender = models.ForeignKey(User, on_delete=models.PROTECT, related_name="discussion_messages")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["application", "created_at"], name="discussion_app_time_idx")]


class CaseLibraryArticle(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    question_th = models.CharField(max_length=255)
    question_en = models.CharField(max_length=255)
    answer_th = models.TextField()
    answer_en = models.TextField()
    keywords = models.JSONField(default=list, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "id"]

    def clean(self):
        super().clean()
        if not isinstance(self.keywords, list) or any(
            not isinstance(item, str) or not item.strip() for item in self.keywords
        ):
            raise ValidationError({"keywords": "Use a JSON list of non-empty strings."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.slug


class CentralAssistanceRequest(models.Model):
    class QuestionCode(models.TextChoices):
        CLASSIFICATION_AMBIGUITY = "CLASSIFICATION_AMBIGUITY", "Classification ambiguity"
        REQUIREMENT_APPLICABILITY = "REQUIREMENT_APPLICABILITY", "Document requirement applicability"
        WORKFLOW_EXCEPTION = "WORKFLOW_EXCEPTION", "Workflow exception"
        POLICY_INTERPRETATION = "POLICY_INTERPRETATION", "Policy interpretation"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"

    class ResolutionCode(models.TextChoices):
        FOLLOW_CURRENT_RULES = "FOLLOW_CURRENT_RULES", "Follow the current rules"
        REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE", "Request more evidence"
        ESCALATE_OFFLINE = "ESCALATE_OFFLINE", "Escalate through the official offline channel"
        NO_CENTRAL_DECISION = "NO_CENTRAL_DECISION", "Central office cannot decide from this snapshot"

    reference_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.PROTECT,
        related_name="central_assistance_requests",
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="central_assistance_requests",
    )
    question_code = models.CharField(max_length=40, choices=QuestionCode.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    property_type_code_snapshot = models.CharField(max_length=40, blank=True)
    classification_outcome_snapshot = models.CharField(max_length=50)
    rooms_snapshot = models.PositiveIntegerField()
    max_guests_snapshot = models.PositiveIntegerField()
    restaurant_snapshot = models.BooleanField()
    application_status_snapshot = models.CharField(max_length=30, choices=Application.Status.choices)
    required_documents_snapshot = models.PositiveIntegerField()
    approved_documents_snapshot = models.PositiveIntegerField()
    resolution_code = models.CharField(max_length=40, choices=ResolutionCode.choices, blank=True)
    resolved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="resolved_central_assistance_requests",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["application"],
                condition=Q(status="OPEN"),
                name="uniq_open_central_assistance_per_app",
            ),
            models.CheckConstraint(
                check=(
                    Q(status="OPEN", resolution_code="", resolved_by__isnull=True, resolved_at__isnull=True)
                    | Q(
                        status="RESOLVED",
                        resolution_code__gt="",
                        resolved_by__isnull=False,
                        resolved_at__isnull=False,
                    )
                ),
                name="central_assistance_resolution_state",
            ),
        ]
        indexes = [models.Index(fields=["status", "-requested_at"], name="central_help_status_idx")]


class MaintenanceNotice(models.Model):
    title_th = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200)
    message_th = models.TextField()
    message_en = models.TextField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at", "-id"]
        indexes = [models.Index(fields=["is_active", "starts_at", "ends_at"], name="maintenance_active_idx")]

    def clean(self):
        super().clean()
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Maintenance end must be after its start."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title_en


class ProviderDirectoryEntry(models.Model):
    class ServiceCode(models.TextChoices):
        APPLICATION_SUPPORT = "APPLICATION_SUPPORT", "Application preparation support"
        TECHNICAL_DRAWING = "TECHNICAL_DRAWING", "Technical drawing"
        FIRE_SAFETY = "FIRE_SAFETY", "Fire-safety documentation"
        LEGAL_ADVICE = "LEGAL_ADVICE", "Legal advice"

    class SourceStatus(models.TextChoices):
        DEMO_ONLY = "DEMO_ONLY", "Fictional demo entry"
        SELF_DECLARED = "SELF_DECLARED", "Provider self-declared"
        PUBLIC_SOURCE = "PUBLIC_SOURCE", "Published public source"

    name = models.CharField(max_length=255)
    services = models.JSONField(default=list)
    price_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="THB")
    price_note_th = models.CharField(max_length=255, blank=True)
    price_note_en = models.CharField(max_length=255, blank=True)
    contact_url = models.URLField(blank=True)
    source_url = models.URLField(blank=True)
    source_status = models.CharField(max_length=20, choices=SourceStatus.choices)
    source_checked_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["is_active", "name"], name="provider_active_name_idx")]

    def clean(self):
        super().clean()
        allowed_services = set(self.ServiceCode.values)
        if not isinstance(self.services, list) or not self.services or any(
            item not in allowed_services for item in self.services
        ):
            raise ValidationError({"services": "Use a non-empty list of supported service codes."})
        if len(self.services) != len(set(self.services)):
            raise ValidationError({"services": "Service codes must be unique."})
        if self.price_min is not None and self.price_min < 0:
            raise ValidationError({"price_min": "Price cannot be negative."})
        if self.price_max is not None and self.price_max < 0:
            raise ValidationError({"price_max": "Price cannot be negative."})
        if self.price_min is not None and self.price_max is not None and self.price_max < self.price_min:
            raise ValidationError({"price_max": "Maximum price cannot be below minimum price."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class License(models.Model):
    class ArtifactKind(models.TextChoices):
        HOTEL_LICENSE = "HOTEL_LICENSE", "Hotel license"
        NOTIFICATION_ACKNOWLEDGEMENT = "NOTIFICATION_ACKNOWLEDGEMENT", "Notification acknowledgement"

    application = models.OneToOneField(Application, on_delete=models.PROTECT, related_name="license")
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    artifact_kind = models.CharField(
        max_length=40,
        choices=ArtifactKind.choices,
        default=ArtifactKind.HOTEL_LICENSE,
    )
    license_number = models.CharField(max_length=30, unique=True)
    property_type = models.ForeignKey(PropertyType, on_delete=models.PROTECT, related_name="licenses")
    fee_schedule = models.ForeignKey(
        FeeSchedule,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="licenses",
    )
    fee_amount_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    fee_currency_snapshot = models.CharField(max_length=3, blank=True)
    validity_years_snapshot = models.PositiveIntegerField(null=True, blank=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(fee_amount_snapshot__isnull=True) | Q(fee_amount_snapshot__gte=0),
                name="license_fee_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(validity_years_snapshot__isnull=True) | Q(validity_years_snapshot__gt=0),
                name="license_validity_positive",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        artifact_kind="HOTEL_LICENSE",
                        fee_schedule__isnull=False,
                        fee_amount_snapshot__isnull=False,
                        validity_years_snapshot__isnull=False,
                        expires_at__isnull=False,
                    )
                    | Q(
                        artifact_kind="NOTIFICATION_ACKNOWLEDGEMENT",
                        fee_schedule__isnull=True,
                        fee_amount_snapshot__isnull=True,
                        fee_currency_snapshot="",
                        validity_years_snapshot__isnull=True,
                        expires_at__isnull=True,
                    )
                ),
                name="license_artifact_fields_match_kind",
            ),
        ]


class AuditLog(ImmutableEventMixin):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["object_type", "object_id", "-created_at"], name="audit_object_created_idx")]


class EmailOutbox(models.Model):
    class Template(models.TextChoices):
        ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION", "Account activation"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"
        APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED", "Application submitted"
        APPLICATION_REVISION_REQUESTED = "APPLICATION_REVISION_REQUESTED", "Application revision requested"
        APPLICATION_RESUBMITTED = "APPLICATION_RESUBMITTED", "Application resubmitted"
        APPLICATION_APPROVED = "APPLICATION_APPROVED", "Application approved"
        APPLICATION_REJECTED = "APPLICATION_REJECTED", "Application rejected"
        LICENSE_EXPIRY_REMINDER = "LICENSE_EXPIRY_REMINDER", "License expiry reminder"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    event_key = models.CharField(max_length=255, unique=True)
    recipient = models.ForeignKey(User, on_delete=models.PROTECT, related_name="email_notifications")
    application = models.ForeignKey(
        Application,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="email_notifications",
    )
    template_code = models.CharField(max_length=50, choices=Template.choices)
    locale = models.CharField(max_length=10, choices=User.Language.choices, default=User.Language.THAI)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="email_status_next_idx")]
