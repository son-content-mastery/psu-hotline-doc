from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0010_license_verification_token")]

    operations = [
        migrations.CreateModel(
            name="CaseLibraryArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("question_th", models.CharField(max_length=255)),
                ("question_en", models.CharField(max_length=255)),
                ("answer_th", models.TextField()),
                ("answer_en", models.TextField()),
                ("keywords", models.JSONField(blank=True, default=list)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["display_order", "id"]},
        ),
    ]
