from django.core.management.base import BaseCommand

from apps.core.notifications import queue_license_renewal_reminders


class Command(BaseCommand):
    help = "Queue due hotel-license renewal reminders without duplicating prior thresholds."

    def handle(self, *args, **options):
        queued = queue_license_renewal_reminders()
        self.stdout.write(self.style.SUCCESS(f"Queued {queued} license renewal reminder(s)."))
