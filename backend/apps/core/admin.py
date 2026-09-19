from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Application,
    ApplicationDocument,
    ApplicationRequirement,
    ApplicationStatusHistory,
    AuditLog,
    ClassificationRule,
    DocumentReview,
    DocumentType,
    DocumentTypeTranslation,
    FeeSchedule,
    IssuingAgency,
    IssuingAgencyTranslation,
    License,
    LocalAuthority,
    Property,
    PropertyType,
    PropertyTypeDocumentRequirement,
    PropertyTypeTranslation,
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
    list_display = ("email", "display_name", "role", "local_authority", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "local_authority")
    search_fields = ("email", "display_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile and role", {"fields": ("display_name", "role", "local_authority")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "role", "local_authority", "password1", "password2", "is_staff"),
            },
        ),
    )


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


@admin.register(PropertyTypeDocumentRequirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ("property_type", "document_type", "step_code", "is_required", "display_order", "is_active")
    list_filter = ("property_type", "step_code", "is_active")


@admin.register(FeeSchedule)
class FeeScheduleAdmin(admin.ModelAdmin):
    list_display = ("property_type", "amount", "currency", "validity_years", "effective_from", "effective_to")

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields) if obj else ()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LocalAuthority)
class LocalAuthorityAdmin(admin.ModelAdmin):
    list_display = ("code", "official_name", "contact_phone", "is_active")
    search_fields = ("code", "official_name")
    list_filter = ("is_active",)


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
    list_display = ("application", "document_type", "is_required", "display_order", "captured_at")
    readonly_fields = ("application", "document_type", "is_required", "display_order", "captured_at")

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


@admin.register(License)
class LicenseAdmin(ImmutableAdmin):
    list_display = ("license_number", "application", "property_type", "fee_amount_snapshot", "issued_at", "expires_at")
