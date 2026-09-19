import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.backups import create_database_backup


class Command(BaseCommand):
    help = "Create verified database backups on a fixed local-demo schedule."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            path = create_database_backup()
            self.stdout.write(self.style.SUCCESS(f"Created verified backup: {path.name}"))
            if options["once"]:
                return
            time.sleep(settings.BACKUP_INTERVAL_SECONDS)
