from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "HoTLinE Doc"

    def ready(self):
        from . import schema  # noqa: F401
