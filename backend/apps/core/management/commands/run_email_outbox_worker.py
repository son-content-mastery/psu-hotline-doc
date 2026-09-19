import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.notifications import process_due_email_outbox


class Command(BaseCommand):
    help = "Poll and deliver due HoTLinE Doc email outbox records."

    def add_arguments(self, parser):
        parser.add_argument("--poll-seconds", type=int, default=settings.EMAIL_OUTBOX_POLL_SECONDS)
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        poll_seconds = options["poll_seconds"]
        limit = options["limit"]
        if poll_seconds < 1 or poll_seconds > 3600:
            raise CommandError("--poll-seconds must be between 1 and 3600")
        if limit < 1 or limit > 500:
            raise CommandError("--limit must be between 1 and 500")

        while True:
            sent = process_due_email_outbox(limit=limit)
            if sent:
                self.stdout.write(self.style.SUCCESS(f"Delivered {sent} email notification(s)."))
            if options["once"]:
                return
            time.sleep(poll_seconds)
