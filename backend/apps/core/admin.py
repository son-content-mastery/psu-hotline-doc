from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db import transaction

from .notifications import queue_activation_email
from .services import audit_event
from .session_security import invalidate_user_sessions
from .models import (
    Application,
    ApplicationDocument,
    ApplicationRequirement,
    ApplicationStatusHistory,
    AuditLog,
    CaseLibraryArticle,
    ClassificationRule,
    DocumentReview,
    DocumentType,
    DocumentTypeTranslation,
    EmailOutbox,
    FeeSchedule,
    IssuingAgency,
    IssuingAgencyTranslation,
    License,
    LocalAuthority,
    Property,
    PropertyType,
    PropertyTypeDocumentRequirement,
    PropertyTypeTranslation,
    ThaiDistrict,
    ThaiProvince,
    ThaiSubdistrict,
    User,
)


def _super_admin_permission(request):
    return bool(
        request.user.is_active
        and request.user.is_staff
        and request.user.role == User.Role.SUPER_ADMIN
    )


admin.site.has_permission = _super_admin_permission


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "display_name", "role", "local_authority", "email_verified_at", "is_active", "is_staff")
    list_filter = ("role", "preferred_language", "is_active", "is_staff", "local_authority")
    search_fields = ("email", "display_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile and role", {"fields": ("display_name", "role", "local_authority", "preferred_language", "email_verified_at")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "role", "local_authority", "preferred_language", "email_verified_at", "password1", "password2", "is_staff"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        tracked_fields = ("email", "role", "local_authority_id", "is_active", "email_verified_at")
        before = None
        if change:
            before = User.objects.filter(pk=obj.pk).values(*tracked_fields).first()

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if before is None:
                audit_event(actor=request.user, action="USER_ADMIN_CREATED", obj=obj)
                invalidate_user_sessions(obj.pk)
                if obj.is_active and obj.email_verified_at is None:
                    queue_activation_email(obj)
                return

            changed = {field for field in tracked_fields if before[field] != getattr(obj, field)}
            actions = {
                "email": "USER_EMAIL_CHANGED",
                "role": "USER_ROLE_CHANGED",
                "local_authority_id": "USER_AUTHORITY_CHANGED",
                "is_active": "USER_ACTIVE_STATUS_CHANGED",
                "email_verified_at": "USER_VERIFICATION_CHANGED",
            }
            for field in sorted(changed):
                audit_event(actor=request.user, action=actions[field], obj=obj)
            if changed:
                invalidate_user_sessions(obj.pk)
            if "email" in changed and obj.is_active and obj.email_verified_at is None:
                queue_activation_email(obj)


class PropertyTypeTranslationInline(admin.TabularInline):
    model = PropertyTypeTranslation
    extra = 0


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "issues_license", "is_active")
    list_filter = ("issues_license", "is_active")
    inlines = [PropertyTypeTranslationInline]


class IssuingAgencyTranslationInline(admin.TabularInline):
    model = IssuingAgencyTranslation
    extra = 0


@admin.register(IssuingAgency)
class IssuingAgencyAdmin(admin.ModelAdmin):
    list_display = ("code", "contact_phone", "contact_email", "is_active")
    inlines = [IssuingAgencyTranslationInline]


class DocumentTypeTranslationInline(admin.TabularInline):
    model = DocumentTypeTranslation
    extra = 0


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "category", "issuing_agency", "allows_multiple_files", "is_active")
    list_filter = ("category", "allows_multiple_files", "is_active")
    inlines = [DocumentTypeTranslationInline]


@admin.register(ClassificationRule)
class ClassificationRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "priority", "outcome_code", "result_property_type", "is_active", "updated_at")
    list_editable = ("priority", "is_active")


@admin.register(CaseLibraryArticle)
class CaseLibraryArticleAdmin(admin.ModelAdmin):
    list_display = ("slug", "question_th", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("slug", "question_th", "question_en", "answer_th", "answer_en")
    list_editable = ("display_order", "is_active")


@admin.register(PropertyTypeDocumentRequirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ("property_type", "document_type", "step_code", "is_required", "display_order", "is_active")
    list_filter = ("property_type", "step_code", "is_active")


@admin.register(FeeSchedule)
class FeeScheduleAdmin(admin.ModelAdmin):
    list_display = ("property_type", "amount", "currency", "validity_years", "effective_from", "effective_to")

    def get_readonly_fields(self, request, obj=None):
        if not obj:
            return ()
        if obj.effective_to is not None:
            return tuple(field.name for field in self.model._meta.fields)
        return tuple(field.name for field in self.model._meta.fields if field.name != "effective_to")

    def save_model(self, request, obj, form, change):
        previous_end = None
        if change:
            previous_end = FeeSchedule.objects.filter(pk=obj.pk).values_list("effective_to", flat=True).first()
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if change and previous_end is None and obj.effective_to is not None:
                audit_event(actor=request.user, action="FEE_SCHEDULE_CLOSED", obj=obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LocalAuthority)
class LocalAuthorityAdmin(admin.ModelAdmin):
    list_display = ("code", "official_name", "contact_phone", "is_active")
    search_fields = ("code", "official_name")
    list_filter = ("is_active",)


class ReadOnlyReferenceAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ThaiProvince)
class ThaiProvinceAdmin(ReadOnlyReferenceAdmin):
    list_display = ("code", "name_th", "name_en", "is_active")


@admin.register(ThaiDistrict)
class ThaiDistrictAdmin(ReadOnlyReferenceAdmin):
    list_display = ("code", "name_th", "name_en", "province", "is_active")
    list_filter = ("province", "is_active")


@admin.register(ThaiSubdistrict)
class ThaiSubdistrictAdmin(ReadOnlyReferenceAdmin):
    list_display = ("code", "name_th", "name_en", "district", "postal_code", "is_active")
    list_filter = ("district", "is_active")


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "local_authority", "property_type", "rooms", "max_guests")
    list_filter = ("local_authority", "property_type")

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "reference_number", "property", "responsible_authority", "status", "updated_at")
    list_filter = ("status", "responsible_authority", "confirmed_property_type")
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApplicationRequirement)
class ApplicationRequirementAdmin(admin.ModelAdmin):
    list_display = ("application", "document_type", "step_code", "is_required", "display_order", "captured_at")
    readonly_fields = ("application", "document_type", "step_code", "is_required", "display_order", "captured_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApplicationDocument)
class ApplicationDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "document_type", "version", "status", "is_current", "uploaded_at")
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ImmutableAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(ImmutableAdmin):
    list_display = ("application", "from_status", "to_status", "actor", "created_at")


@admin.register(DocumentReview)
class DocumentReviewAdmin(ImmutableAdmin):
    list_display = ("application_document", "outcome", "reviewer", "reviewed_at")


@admin.register(AuditLog)
class AuditLogAdmin(ImmutableAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "object_id", "from_status", "to_status")
    list_filter = ("action", "object_type")


@admin.register(EmailOutbox)
class EmailOutboxAdmin(ImmutableAdmin):
    list_display = ("created_at", "template_code", "recipient", "status", "attempt_count", "sent_at")
    list_filter = ("template_code", "status", "locale")
    search_fields = ("event_key", "recipient__email")


@admin.register(License)
class LicenseAdmin(ImmutableAdmin):
    list_display = ("license_number", "application", "property_type", "fee_amount_snapshot", "issued_at", "expires_at")
