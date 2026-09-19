from importlib import import_module
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.sessions.models import Session

from apps.core.admin import UserAdmin
from apps.core.models import AuditLog, EmailOutbox, User


@pytest.mark.django_db
def test_admin_email_change_audits_invalidates_sessions_and_queues_activation(seeded):
    target = User.objects.get(pk=seeded["applicant"].pk)
    session = import_module(settings.SESSION_ENGINE).SessionStore()
    session["_auth_user_id"] = str(target.pk)
    session.create()
    session_key = session.session_key

    target.email = "changed-applicant@example.test"
    model_admin = UserAdmin(User, AdminSite())
    request = SimpleNamespace(user=seeded["admin"])
    model_admin.save_model(request, target, form=None, change=True)

    target.refresh_from_db()
    assert target.email_verified_at is None
    assert not Session.objects.filter(session_key=session_key).exists()
    assert AuditLog.objects.filter(
        actor=seeded["admin"],
        action="USER_EMAIL_CHANGED",
        object_type="core.User",
        object_id=str(target.pk),
    ).exists()
    assert AuditLog.objects.filter(
        actor=seeded["admin"],
        action="USER_VERIFICATION_CHANGED",
        object_id=str(target.pk),
    ).exists()
    assert EmailOutbox.objects.filter(
        recipient=target,
        template_code=EmailOutbox.Template.ACCOUNT_ACTIVATION,
    ).exists()


@pytest.mark.django_db
def test_admin_role_change_audits_and_invalidates_sessions(seeded):
    target = User.objects.get(pk=seeded["central"].pk)
    session = import_module(settings.SESSION_ENGINE).SessionStore()
    session["_auth_user_id"] = str(target.pk)
    session.create()
    session_key = session.session_key

    target.role = User.Role.APPLICANT
    model_admin = UserAdmin(User, AdminSite())
    model_admin.save_model(SimpleNamespace(user=seeded["admin"]), target, form=None, change=True)

    assert not Session.objects.filter(session_key=session_key).exists()
    assert AuditLog.objects.filter(
        actor=seeded["admin"],
        action="USER_ROLE_CHANGED",
        object_id=str(target.pk),
    ).exists()
