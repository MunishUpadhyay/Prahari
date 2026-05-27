import os
import sys
import django
import json

# Add project root to python path
sys.path.append("d:/My Projects/Django/Prahari")

# Set up django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.conf import settings
settings.CELERY_TASK_ALWAYS_EAGER = True
settings.CELERY_TASK_EAGER_PROPAGATES = True

from pipeline.tasks import ingest_signal
from apps.signals.models import Signal
from apps.incidents.models import Incident
from apps.tenants.models import Tenant

def run_test():
    # Get or create a default tenant
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(name="Default Tenant", api_key_hash=Tenant.hash_api_key("dummy_key"))
    print(f"Using Tenant: {tenant.name} ({tenant.id})")

    # Create the test signal
    raw_text = (
        "Our shop was broken into in Bhopal and goods worth 80000 rupees were stolen. "
        "Police refused to register FIR twice. Officer said resolve it yourself."
    )
    sig = Signal.objects.create(
        raw_text=raw_text, 
        source_type="text",
        tenant_id=tenant.id,
        metadata={"contact_number": "+919876543210", "location": "Bhopal"}
    )
    print(f"Created Signal ID: {sig.id}")

    print("Running pipeline task chain synchronously...")
    ingest_signal(str(sig.id))
    print("Pipeline finished!")

    # Query the incident and its agent_outputs
    try:
        incident = Incident.objects.get(signal=sig)
        print("\n================ INCIDENT INFO ================")
        print("Incident ID:", incident.id)
        print("Incident Domain:", incident.domain)
        print("Incident Severity Label:", incident.severity_label)
        print("Incident Severity Score:", incident.severity_score)
        print("Coordinator Status:", incident.coordinator_status)
        # Reconfigure stdout to support UTF-8 printing in windows terminal
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

        print("Situation Title (EN):", incident.agent_outputs.get("coordination", {}).get("situation_title"))
        print("Situation Title (HI):", incident.agent_outputs.get("language", {}).get("situation_title"))
        
        print("\n================ RAG RETRIEVED LEGAL PROVISIONS ================")
        rights_out = incident.agent_outputs.get("rights", {})
        provisions = rights_out.get("legal_provisions", [])
        for p in provisions:
            print(f"- Provision: {p.get('provision')}")
            print(f"  Relevance: {p.get('relevance')}")
            print(f"  Description: {p.get('description')}")
            
        print("\n================ COORDINATION ACTIONS ================")
        coord_out = incident.agent_outputs.get("coordination", {})
        print("Immediate Actions:")
        for action in coord_out.get("immediate_actions", []):
            print(f"- [{action.get('priority')}] {action.get('action')} (Timeframe: {action.get('timeframe')}, Role: {action.get('responsible_role')})")
        
        print("\nAuthorities to Notify:", coord_out.get("authorities_to_notify"))
        print("Nearest Authority Type:", rights_out.get("nearest_authority_type"))
        
        print("\n================ WRITING COMPLETE AGENT OUTPUTS TO FILE ================")
        out_file = "d:/My Projects/Django/Prahari/fir_refusal_outputs.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(incident.agent_outputs, f, indent=2, ensure_ascii=False)
        print(f"Saved complete agent outputs to {out_file}")
        
        return sig.id
    except Incident.DoesNotExist:
        print("Error: Incident was not created.")
        return None

if __name__ == "__main__":
    run_test()
