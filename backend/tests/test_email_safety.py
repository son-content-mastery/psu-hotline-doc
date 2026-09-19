import pytest

from apps.core.models import EmailOutbox, User
from apps.core.notifications import deliver_email_outbox


@pytest.mark.django_db
def test_smtp_never_attempts_reserved_demo_recipient(settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_SUPPRESSED_DOMAINS = ["example.test", "example.com", "example.org"]
    user = User.objects.create_user(
        email="seed-user@example.test",
        password="StrongRegistrationPass123!",
        display_name="Seed User",
    )
    entry = EmailOutbox.objects.create(
        event_key="activation:reserved-domain:recipient:1",
        recipient=user,
        template_code=EmailOutbox.Template.ACCOUNT_ACTIVATION,
        locale="en",
    )

    send_mail = monkeypatch.setattr(
        "apps.core.notifications.send_mail",
        lambda **kwargs: pytest.fail("SMTP must not be called for a reserved demo domain"),
    )

    assert send_mail is None
    assert deliver_email_outbox(entry.pk) is True
    entry.refresh_from_db()
    assert entry.status == EmailOutbox.Status.SENT
    assert entry.last_error_code == "RECIPIENT_DOMAIN_SUPPRESSED"
