from django.core.management.base import BaseCommand
from rag.ingest import ingest_legal_documents, ingest_medical_protocols

class Command(BaseCommand):
    help = 'Ingest Indian legal provisions and medical protocols into ChromaDB collections'

    def handle(self, *args, **options):
        self.stdout.write("Starting ingestion of legal documents...")
        try:
            ingest_legal_documents()
            self.stdout.write(self.style.SUCCESS("Successfully ingested legal documents into ChromaDB."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Legal ingestion failed: {e}"))

        self.stdout.write("Starting ingestion of medical protocols...")
        try:
            ingest_medical_protocols()
            self.stdout.write(self.style.SUCCESS("Successfully ingested medical protocols into ChromaDB."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Medical ingestion failed: {e}"))
