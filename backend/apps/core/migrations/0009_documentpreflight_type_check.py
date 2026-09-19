from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0008_documentpreflight")]

    operations = [
        migrations.AddField(
            model_name="documentpreflight",
            name="detected_family",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="documentpreflight",
            name="type_analyzer_version",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="documentpreflight",
            name="type_check_status",
            field=models.CharField(
                choices=[
                    ("NOT_RUN", "Document-type check was not run"),
                    ("MATCH", "Document family appears consistent"),
                    ("POSSIBLE_MISMATCH", "Possible document-family mismatch"),
                    ("INCONCLUSIVE", "Document-type check was inconclusive"),
                    ("UNAVAILABLE", "Document-type check was unavailable"),
                    ("NOT_APPLICABLE", "Document-type OCR is not applicable"),
                ],
                default="NOT_RUN",
                max_length=30,
            ),
        ),
    ]
