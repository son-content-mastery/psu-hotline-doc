from rest_framework.permissions import BasePermission

from .models import User


class RolePermission(BasePermission):
    allowed_roles = set()

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in self.allowed_roles)


class IsApplicant(RolePermission):
    allowed_roles = {User.Role.APPLICANT}


class IsLocalOfficer(RolePermission):
    allowed_roles = {User.Role.LOCAL_OFFICER}

    def has_permission(self, request, view):
        return super().has_permission(request, view) and bool(
            request.user.local_authority_id and request.user.local_authority.is_active
        )


class IsCentralOfficer(RolePermission):
    allowed_roles = {User.Role.CENTRAL_OFFICER}
