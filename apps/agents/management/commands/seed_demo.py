import time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from apps.tenants.models import Tenant
from apps.signals.models import Signal
from apps.incidents.models import Incident
from pipeline.tasks import ingest_signal


class Command(BaseCommand):
    help = "Seeds Prahari with a coordinator user, demo tenant, and ingests 6 demo incidents through the live Celery agent pipeline."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== STARTING PRAHARI DEMO SEEDING ==="))

        # 1. Create coordinator user
        username = "coordinator"
        password = "prahari2024"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "email": "coordinator@prahari.org"
            }
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created coordinator user: {username} / {password}"))
        else:
            self.stdout.write(self.style.WARNING(f"Coordinator user '{username}' already exists."))

        # 2. Create demo tenant
        tenant, t_created = Tenant.objects.get_or_create(
            name="Prahari Demo NGO",
            defaults={
                "webhook_url": "http://localhost:9999/webhook",
                "api_key_hash": Tenant.hash_api_key("demo_key_123"),
                "is_active": True
            }
        )
        if t_created:
            self.stdout.write(self.style.SUCCESS(f"Created demo tenant: {tenant.name}"))
        else:
            self.stdout.write(self.style.WARNING(f"Tenant '{tenant.name}' already exists."))

        # 3. List of signals to ingest
        signals_data = [
            {
                "text": "My father was arrested yesterday morning and police are not telling us where he is being held. No lawyer has been assigned. We have not been allowed to meet him.",
                "contact": "+919876543210",
                "location": "Delhi"
            },
            {
                "text": "72 year old woman brought to government hospital with severe chest pain. Hospital staff saying they cannot admit her without a deposit of 10000 rupees. She is deteriorating.",
                "contact": "+919876543211",
                "location": "Mumbai"
            },
            {
                "text": "Building collapse in Dharavi. At least 3 floors have fallen. People trapped inside. We can hear voices. Fire brigade not yet arrived.",
                "contact": "+919876543212",
                "location": "Dharavi, Mumbai"
            },
            {
                "text": "Accident victim on NH48. Man unconscious. Private hospital refused admission. We tried calling 108 but no response for 20 minutes.",
                "contact": "+919876543213",
                "location": "NH48 Highway"
            },
            {
                "text": "Landlord has illegally locked our house while we were away. All belongings inside. Police refusing to file FIR saying it is a civil matter.",
                "contact": "+919876543214",
                "location": "Pune"
            },
            {
                "text": "Village health worker refusing to give vaccines to children from our community saying they need documents. 15 children affected.",
                "contact": "+919876543215",
                "location": "Wayanad District"
            }
        ]

        self.stdout.write("\n" + "="*80)
        self.stdout.write("Ingesting 6 signals sequentially. Make sure Celery worker is active!")
        self.stdout.write("="*80 + "\n")

        for idx, item in enumerate(signals_data, 1):
            self.stdout.write(self.style.HTTP_INFO(f"[{idx}/6] Submitting Signal: '{item['text'][:60]}...'"))
            
            # Create Signal object
            signal = Signal.objects.create(
                tenant=tenant,
                raw_text=item["text"],
                source_type="text",
                contact_number=item["contact"],
                metadata={
                    "location": item["location"],
                    "contact_number": item["contact"]
                }
            )

            # Trigger processing pipeline
            ingest_signal.delay(str(signal.id))

            # Poll for completion
            completed = False
            start_time = time.time()
            max_wait = 40  # seconds
            
            while time.time() - start_time < max_wait:
                time.sleep(2)
                signal.refresh_from_db()
                incident = getattr(signal, "incident", None)
                if incident:
                    outputs = incident.agent_outputs or {}
                    if "language" in outputs:
                        completed = True
                        break
            
            if completed:
                incident = signal.incident
                outputs = incident.agent_outputs or {}
                coord = outputs.get("coordination", {})
                lang = outputs.get("language", {}).get("hindi", {})
                
                self.stdout.write(self.style.SUCCESS(f" [OK] Processed Successfully!"))
                self.stdout.write(f"   - Domain Classified: {incident.domain.upper()}")
                self.stdout.write(f"   - Severity:          {incident.severity_label.upper()} (Score: {incident.severity_score:.2f})")
                self.stdout.write(f"   - Brief (EN):        {incident.situation_brief}")
                if lang and isinstance(lang, dict):
                    try:
                        self.stdout.write(f"   - Brief (HI):        {lang.get('situation_brief', '')}")
                    except UnicodeEncodeError:
                        safe_hi = lang.get('situation_brief', '').encode('ascii', errors='backslashreplace').decode('ascii')
                        self.stdout.write(f"   - Brief (HI) [Raw]:  {safe_hi} (Windows console encoding fallback)")
            else:
                self.stdout.write(self.style.ERROR(f" [TIMEOUT] Pipeline timed out for Signal {signal.id} after {max_wait}s."))
            
            self.stdout.write("-"*80)

        self.stdout.write(self.style.SUCCESS("\n=== DEMO SEEDING COMPLETED ==="))
