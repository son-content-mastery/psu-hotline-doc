from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_thaiprovince_thaidistrict_thaisubdistrict_and_more")]

    operations = [
        migrations.AlterField(
            model_name="emailoutbox",
            name="template_code",
            field=models.CharField(
                choices=[
                    ("ACCOUNT_ACTIVATION", "Account activation"),
                    ("PASSWORD_RESET", "Password reset"),
                    ("APPLICATION_SUBMITTED", "Application submitted"),
                    ("APPLICATION_REVISION_REQUESTED", "Application revision requested"),
                    ("APPLICATION_RESUBMITTED", "Application resubmitted"),
                    ("APPLICATION_APPROVED", "Application approved"),
                    ("APPLICATION_REJECTED", "Application rejected"),
                    ("LICENSE_EXPIRY_REMINDER", "License expiry reminder"),
                ],
                max_length=50,
            ),
        )
    ]
