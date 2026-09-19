import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .exceptions import DomainError
from .models import Application, AuditLog, EmailOutbox, License, User


logger = logging.getLogger(__name__)
ACTIVATION_SALT = "hotline-doc.account-activation.v1"


SUBJECTS = {
    EmailOutbox.Template.ACCOUNT_ACTIVATION: {
        "th": "ยืนยันอีเมลสำหรับ HoTLinE Doc",
        "en": "Verify your HoTLinE Doc email",
    },
    EmailOutbox.Template.PASSWORD_RESET: {
        "th": "ตั้งรหัสผ่าน HoTLinE Doc ใหม่",
        "en": "Reset your HoTLinE Doc password",
    },
    EmailOutbox.Template.APPLICATION_SUBMITTED: {
        "th": "HoTLinE Doc ได้รับคำขอแล้ว",
        "en": "HoTLinE Doc application submitted",
    },
    EmailOutbox.Template.APPLICATION_REVISION_REQUESTED: {
        "th": "คำขอ HoTLinE Doc ต้องดำเนินการเพิ่มเติม",
        "en": "Action required on your HoTLinE Doc application",
    },
    EmailOutbox.Template.APPLICATION_RESUBMITTED: {
        "th": "HoTLinE Doc ได้รับคำขอที่แก้ไขแล้ว",
        "en": "HoTLinE Doc application resubmitted",
    },
    EmailOutbox.Template.APPLICATION_APPROVED: {
        "th": "คำขอ HoTLinE Doc ได้รับการอนุมัติ",
        "en": "HoTLinE Doc application approved",
    },
    EmailOutbox.Template.APPLICATION_REJECTED: {
        "th": "มีผลการพิจารณาคำขอ HoTLinE Doc",
        "en": "HoTLinE Doc application decision",
    },
    EmailOutbox.Template.LICENSE_EXPIRY_REMINDER: {
        "th": "แจ้งเตือนวันหมดอายุใบอนุญาต HoTLinE Doc",
        "en": "HoTLinE Doc license expiry reminder",
    },
}


WORKFLOW_MESSAGES = {
    EmailOutbox.Template.APPLICATION_SUBMITTED: {
        "th": "ระบบได้รับคำขอแล้ว โปรดติดตามสถานะในระบบ",
        "en": "The application has been received. Track its status in the service.",
    },
    EmailOutbox.Template.APPLICATION_REVISION_REQUESTED: {
        "th": "คำขอนี้ต้องให้ผู้ยื่นดำเนินการเพิ่มเติม โปรดเข้าสู่ระบบเพื่อดูรายละเอียดที่ได้รับอนุญาต",
        "en": "This application needs applicant action. Sign in to view the authorized details.",
    },
    EmailOutbox.Template.APPLICATION_RESUBMITTED: {
        "th": "ระบบได้รับคำขอที่แก้ไขแล้วและส่งกลับเข้าสู่กระบวนการตรวจสอบ",
        "en": "The revised application has been received and returned to review.",
    },
    EmailOutbox.Template.APPLICATION_APPROVED: {
        "th": "คำขอได้รับการอนุมัติแล้ว โปรดเข้าสู่ระบบเพื่อดูเอกสารผลการพิจารณา",
        "en": "The application has been approved. Sign in to view the decision artifact.",
    },
    EmailOutbox.Template.APPLICATION_REJECTED: {
        "th": "มีผลการพิจารณาคำขอแล้ว โปรดเข้าสู่ระบบเพื่อดูสถานะและรายละเอียดที่ได้รับอนุญาต",
        "en": "A decision has been recorded. Sign in to view the authorized status and details.",
    },
}


def make_activation_token(user):
    return signing.dumps(
        {"user_id": user.pk, "email": user.email},
        salt=ACTIVATION_SALT,
        compress=True,
    )


def activate_user_from_token(token):
    try:
        payload = signing.loads(
            token,
            salt=ACTIVATION_SALT,
            max_age=settings.ACCOUNT_ACTIVATION_TOKEN_MAX_AGE_SECONDS,
        )
        user_id = int(payload["user_id"])
        email = str(payload["email"]).strip().lower()
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise DomainError(
            "ACTIVATION_INVALID",
            "This activation link is invalid or has expired.",
            http_status=400,
        )

    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=user_id, is_active=True).first()
        if user is None or user.email != email or user.email_verified_at is not None:
            raise DomainError(
                "ACTIVATION_INVALID",
                "This activation link is invalid or has expired.",
                http_status=400,
            )
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        AuditLog.objects.create(
            actor=user,
            action="USER_EMAIL_VERIFIED",
            object_type=user._meta.label,
            object_id=str(user.pk),
        )
    return user


def _event_key(template_code, recipient_id, event_identifier):
    return f"{template_code}:{event_identifier}:recipient:{recipient_id}"


def queue_email(*, template_code, recipient, event_identifier, application=None):
    entry, created = EmailOutbox.objects.get_or_create(
        event_key=_event_key(template_code, recipient.pk, event_identifier),
        defaults={
            "recipient": recipient,
            "application": application,
            "template_code": template_code,
            "locale": recipient.preferred_language,
        },
    )
    if created:
        transaction.on_commit(lambda entry_id=entry.pk: deliver_email_outbox(entry_id))
    return entry, created


def queue_activation_email(user):
    minute_bucket = int(timezone.now().timestamp() // 60)
    return queue_email(
        template_code=EmailOutbox.Template.ACCOUNT_ACTIVATION,
        recipient=user,
        event_identifier=f"user:{user.pk}:minute:{minute_bucket}",
    )


def queue_password_reset_email(user):
    minute_bucket = int(timezone.now().timestamp() // 60)
    return queue_email(
        template_code=EmailOutbox.Template.PASSWORD_RESET,
        recipient=user,
        event_identifier=f"user:{user.pk}:minute:{minute_bucket}",
    )


def queue_application_event(application, template_code, status_history_id):
    if not settings.WORKFLOW_NOTIFICATION_EMAIL_ENABLED:
        return []
    recipients = []
    owner = application.property.owner
    if owner.is_active and owner.email_verified_at is not None:
        recipients.append(owner)
    if template_code in {
        EmailOutbox.Template.APPLICATION_SUBMITTED,
        EmailOutbox.Template.APPLICATION_RESUBMITTED,
    }:
        recipients.extend(
            User.objects.filter(
                role=User.Role.LOCAL_OFFICER,
                local_authority=application.responsible_authority,
                is_active=True,
                email_verified_at__isnull=False,
            ).order_by("id")
        )
    queued = []
    seen = set()
    for recipient in recipients:
        if recipient.pk in seen:
            continue
        seen.add(recipient.pk)
        queued.append(
            queue_email(
                template_code=template_code,
                recipient=recipient,
                event_identifier=f"status-history:{status_history_id}",
                application=application,
            )[0]
        )
    return queued


def _renewal_threshold(expires_at, on_date):
    days_remaining = (expires_at - on_date).days
    if days_remaining < 0:
        return None
    eligible = [threshold for threshold in settings.LICENSE_RENEWAL_REMINDER_DAYS if days_remaining <= threshold]
    return min(eligible) if eligible else None


def queue_license_renewal_reminders(*, on_date=None):
    """Queue at most one due reminder per license and configured threshold."""
    if not settings.LICENSE_RENEWAL_REMINDERS_ENABLED:
        return 0
    on_date = on_date or timezone.localdate()
    latest_due_date = on_date + timedelta(days=max(settings.LICENSE_RENEWAL_REMINDER_DAYS))
    licenses = (
        License.objects.filter(
            artifact_kind=License.ArtifactKind.HOTEL_LICENSE,
            application__status=Application.Status.APPROVED,
            expires_at__gte=on_date,
            expires_at__lte=latest_due_date,
            application__property__owner__is_active=True,
            application__property__owner__email_verified_at__isnull=False,
        )
        .select_related("application__property__owner")
        .order_by("expires_at", "id")
    )
    created_count = 0
    for license_record in licenses:
        threshold = _renewal_threshold(license_record.expires_at, on_date)
        if threshold is None:
            continue
        _, created = queue_email(
            template_code=EmailOutbox.Template.LICENSE_EXPIRY_REMINDER,
            recipient=license_record.application.property.owner,
            event_identifier=f"license:{license_record.pk}:threshold:{threshold}",
            application=license_record.application,
        )
        created_count += int(created)
    return created_count


def _render_message(entry):
    locale = entry.locale if entry.locale in {User.Language.THAI, User.Language.ENGLISH} else User.Language.THAI
    if entry.template_code == EmailOutbox.Template.ACCOUNT_ACTIVATION:
        if not entry.recipient.is_active or entry.recipient.email_verified_at is not None:
            return None
        token = make_activation_token(entry.recipient)
        activation_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/activate-account?token={token}"
        body = render_to_string(
            "emails/account_activation.txt",
            {
                "display_name": entry.recipient.display_name,
                "activation_url": activation_url,
                "expiry_hours": max(1, settings.ACCOUNT_ACTIVATION_TOKEN_MAX_AGE_SECONDS // 3600),
                "locale": locale,
            },
        )
    elif entry.template_code == EmailOutbox.Template.PASSWORD_RESET:
        if not entry.recipient.is_active or entry.recipient.email_verified_at is None:
            return None
        uid = urlsafe_base64_encode(force_bytes(entry.recipient.pk))
        token = default_token_generator.make_token(entry.recipient)
        reset_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"
        body = render_to_string(
            "emails/password_reset.txt",
            {
                "display_name": entry.recipient.display_name,
                "reset_url": reset_url,
                "locale": locale,
            },
        )
    else:
        application = entry.application
        if application is None:
            raise ValueError("Workflow email requires an application")
        if entry.template_code == EmailOutbox.Template.LICENSE_EXPIRY_REMINDER:
            try:
                license_record = application.license
            except License.DoesNotExist:
                return None
            if (
                license_record.artifact_kind != License.ArtifactKind.HOTEL_LICENSE
                or license_record.expires_at is None
                or application.status != Application.Status.APPROVED
            ):
                return None
            days_remaining = (license_record.expires_at - timezone.localdate()).days
            if days_remaining < 0:
                message = (
                    f"ใบอนุญาตหมดอายุเมื่อ {license_record.expires_at.isoformat()} กรุณาติดต่อหน่วยงานที่รับผิดชอบ"
                    if locale == User.Language.THAI
                    else f"The license expired on {license_record.expires_at.isoformat()}. Contact the responsible authority."
                )
            else:
                message = (
                    f"ใบอนุญาตจะหมดอายุวันที่ {license_record.expires_at.isoformat()} (เหลือ {days_remaining} วัน) กรุณาเตรียมการต่ออายุ"
                    if locale == User.Language.THAI
                    else f"The license expires on {license_record.expires_at.isoformat()} ({days_remaining} days remaining). Prepare for renewal."
                )
            action_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/applications/{application.pk}/license"
        elif entry.recipient.role == User.Role.LOCAL_OFFICER:
            action_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/officer/applications/{application.pk}"
        elif entry.template_code == EmailOutbox.Template.APPLICATION_APPROVED:
            action_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/applications/{application.pk}/license"
        else:
            action_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/applications/{application.pk}/tracking"
        body = render_to_string(
            "emails/workflow_notification.txt",
            {
                "display_name": entry.recipient.display_name,
                "reference_number": application.reference_number or f"#{application.pk}",
                "message": (
                    message
                    if entry.template_code == EmailOutbox.Template.LICENSE_EXPIRY_REMINDER
                    else WORKFLOW_MESSAGES[entry.template_code][locale]
                ),
                "action_url": action_url,
                "locale": locale,
            },
        )
    return SUBJECTS[entry.template_code][locale], body


def _recipient_domain_is_suppressed(email):
    if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
        return False
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return any(
        domain == suppressed.lower() or domain.endswith(f".{suppressed.lower()}")
        for suppressed in settings.EMAIL_SUPPRESSED_DOMAINS
    )


def deliver_email_outbox(entry_id):
    with transaction.atomic():
        entry = (
            EmailOutbox.objects.select_for_update(of=("self",))
            .select_related("recipient", "application")
            .get(pk=entry_id)
        )
        if entry.status != EmailOutbox.Status.PENDING or entry.next_attempt_at > timezone.now():
            return False
        entry.attempt_count += 1
        try:
            if _recipient_domain_is_suppressed(entry.recipient.email):
                entry.status = EmailOutbox.Status.SENT
                entry.sent_at = timezone.now()
                entry.last_error_code = "RECIPIENT_DOMAIN_SUPPRESSED"
            else:
                rendered = _render_message(entry)
                if rendered is None:
                    entry.status = EmailOutbox.Status.SENT
                    entry.sent_at = timezone.now()
                    entry.last_error_code = "RECIPIENT_NO_LONGER_ELIGIBLE"
                else:
                    subject, body = rendered
                    accepted = send_mail(
                        subject=subject,
                        message=body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[entry.recipient.email],
                        fail_silently=False,
                    )
                    if accepted != 1:
                        raise RuntimeError("Email backend did not accept the message")
                    entry.status = EmailOutbox.Status.SENT
                    entry.sent_at = timezone.now()
                    entry.last_error_code = ""
        except Exception as error:
            entry.last_error_code = type(error).__name__[:120]
            if entry.attempt_count >= settings.EMAIL_OUTBOX_MAX_ATTEMPTS:
                entry.status = EmailOutbox.Status.FAILED
            else:
                delay = settings.EMAIL_OUTBOX_RETRY_BASE_SECONDS * (2 ** (entry.attempt_count - 1))
                entry.next_attempt_at = timezone.now() + timedelta(seconds=delay)
            logger.warning(
                "Email outbox delivery failed entry_id=%s error_type=%s attempt=%s",
                entry.pk,
                entry.last_error_code,
                entry.attempt_count,
            )
        entry.save(
            update_fields=[
                "attempt_count",
                "status",
                "next_attempt_at",
                "sent_at",
                "last_error_code",
                "updated_at",
            ]
        )
        return entry.status == EmailOutbox.Status.SENT


def process_due_email_outbox(limit=50):
    ids = list(
        EmailOutbox.objects.filter(
            status=EmailOutbox.Status.PENDING,
            next_attempt_at__lte=timezone.now(),
        )
        .order_by("next_attempt_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    return sum(1 for entry_id in ids if deliver_email_outbox(entry_id))
