from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0007_alter_emailoutbox_template_code")]

    operations = [
        migrations.CreateModel(
            name="DocumentPreflight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PASS", "No quality warning detected"),
                            ("WARNING", "Quality warning detected"),
                            ("LIMITED", "Automated quality check is limited"),
                        ],
                        max_length=20,
                    ),
                ),
                ("issue_codes", models.JSONField(default=list)),
                ("analyzer_version", models.CharField(max_length=30)),
                ("analyzed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "application_document",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="preflight",
                        to="core.applicationdocument",
                    ),
                ),
            ],
        )
    ]
