from django.core.management.base import BaseCommand

from apps.core.backups import verify_backup


class Command(BaseCommand):
    help = "Verify a HoTLinE Doc PostgreSQL backup archive and checksum."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        path = verify_backup(options["path"])
        self.stdout.write(self.style.SUCCESS(f"Verified backup: {path.name}"))
