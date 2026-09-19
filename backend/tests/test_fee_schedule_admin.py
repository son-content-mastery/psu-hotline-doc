from datetime import date
from types import SimpleNamespace

import pytest
from django.contrib.admin.sites import AdminSite

from apps.core.admin import FeeScheduleAdmin
from apps.core.models import AuditLog, FeeSchedule


@pytest.mark.django_db
def test_admin_can_only_close_an_open_fee_schedule_and_audits_it(seeded):
    schedule = FeeSchedule.objects.filter(effective_to__isnull=True).first()
    model_admin = FeeScheduleAdmin(FeeSchedule, AdminSite())
    request = SimpleNamespace(user=seeded["admin"])
    readonly = set(model_admin.get_readonly_fields(request, schedule))

    assert "effective_to" not in readonly
    assert {"property_type", "amount", "currency", "validity_years", "effective_from"} <= readonly

    schedule.effective_to = date(2026, 12, 31)
    model_admin.save_model(request, schedule, form=None, change=True)

    assert AuditLog.objects.filter(
        actor=seeded["admin"],
        action="FEE_SCHEDULE_CLOSED",
        object_type="core.FeeSchedule",
        object_id=str(schedule.pk),
    ).exists()
    assert set(model_admin.get_readonly_fields(request, schedule)) == {
        field.name for field in FeeSchedule._meta.fields
    }
