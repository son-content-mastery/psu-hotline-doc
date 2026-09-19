import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def verify_existing_users(apps, schema_editor):
    User = apps.get_model("core", "User")
    User.objects.filter(email_verified_at__isnull=True).update(
        email_verified_at=django.utils.timezone.now()
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alter_applicationdocument_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="preferred_language",
            field=models.CharField(
                choices=[("th", "Thai"), ("en", "English")],
                default="th",
                max_length=10,
            ),
        ),
        migrations.RunPython(verify_existing_users, migrations.RunPython.noop),
        migrations.CreateModel(
            name="EmailOutbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(max_length=255, unique=True)),
                (
                    "template_code",
                    models.CharField(
                        choices=[
                            ("ACCOUNT_ACTIVATION", "Account activation"),
                            ("APPLICATION_SUBMITTED", "Application submitted"),
                            ("APPLICATION_REVISION_REQUESTED", "Application revision requested"),
                            ("APPLICATION_RESUBMITTED", "Application resubmitted"),
                            ("APPLICATION_APPROVED", "Application approved"),
                            ("APPLICATION_REJECTED", "Application rejected"),
                        ],
                        max_length=50,
                    ),
                ),
                ("locale", models.CharField(choices=[("th", "Thai"), ("en", "English")], default="th", max_length=10)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("SENT", "Sent"), ("FAILED", "Failed")], default="PENDING", max_length=20)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("application", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="email_notifications", to="core.application")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="email_notifications", to="core.user")),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [models.Index(fields=["status", "next_attempt_at"], name="email_status_next_idx")],
            },
        ),
    ]
