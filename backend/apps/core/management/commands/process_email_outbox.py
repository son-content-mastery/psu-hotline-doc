from django.core.management.base import BaseCommand, CommandError

from apps.core.notifications import process_due_email_outbox


class Command(BaseCommand):
    help = "Deliver due HoTLinE Doc email outbox records with bounded retries."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1 or limit > 500:
            raise CommandError("--limit must be between 1 and 500")
        sent = process_due_email_outbox(limit=limit)
        self.stdout.write(self.style.SUCCESS(f"Delivered {sent} email notification(s)."))
