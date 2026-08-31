from django.core.management.base import BaseCommand
from pipeline.tasks import cleanup_stale_signals

class Command(BaseCommand):
    help = "Clean up stuck/stale signals and mark them as failed after timeout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=15,
            help="Timeout threshold in minutes (default: 15)",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        self.stdout.write(f"Scanning for stale signals older than {timeout} minutes...")
        cleaned = cleanup_stale_signals(timeout_minutes=timeout)
        self.stdout.write(self.style.SUCCESS(f"Successfully cleaned up {cleaned} stale signals."))
