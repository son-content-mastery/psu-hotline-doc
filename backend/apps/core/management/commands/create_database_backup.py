from django.core.management.base import BaseCommand

from apps.core.backups import create_database_backup


class Command(BaseCommand):
    help = "Create and verify a PostgreSQL custom-format backup with checksum and retention."

    def handle(self, *args, **options):
        path = create_database_backup()
        self.stdout.write(self.style.SUCCESS(f"Created verified backup: {path.name}"))
