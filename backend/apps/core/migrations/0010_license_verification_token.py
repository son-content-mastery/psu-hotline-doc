import uuid

from django.db import migrations, models


def populate_verification_tokens(apps, schema_editor):
    License = apps.get_model("core", "License")
    for license_record in License.objects.filter(verification_token__isnull=True).iterator():
        license_record.verification_token = uuid.uuid4()
        license_record.save(update_fields=["verification_token"])


class Migration(migrations.Migration):
    dependencies = [("core", "0009_documentpreflight_type_check")]

    operations = [
        migrations.AddField(
            model_name="license",
            name="verification_token",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_verification_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="license",
            name="verification_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
