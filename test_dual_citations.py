import os
import sys
import django
import json

# Add project root to python path
sys.path.append("d:/My Projects/Django/Prahari")

# Set up django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.signals.models import Signal
from apps.agents.agents import RightsAgent
from apps.tenants.models import Tenant

def test_run():
    # Set stdout to UTF-8
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(name="Default Tenant", api_key_hash=Tenant.hash_api_key("dummy_key"))

    agent = RightsAgent()
    agent.max_tokens = 4000

    # Test A: FIR Refusal
    text_a = "Shop broken into in Bhopal. Police refused to register FIR twice. Goods worth 80000 stolen."
    sig_a = Signal.objects.create(raw_text=text_a, source_type="text", tenant_id=tenant.id)
    sentinel_a = {"domain": "legal"}
    print("\n================ RUNNING TEST A (FIR REFUSAL) ================")
    res_a = agent.run(sig_a, sentinel_a)
    print(json.dumps(res_a, indent=2, ensure_ascii=False))

    # Test B: Unlawful Arrest
    text_b = "My brother arrested yesterday. No lawyer assigned. Not produced before magistrate. Family not informed."
    sig_b = Signal.objects.create(raw_text=text_b, source_type="text", tenant_id=tenant.id)
    sentinel_b = {"domain": "legal"}
    print("\n================ RUNNING TEST B (UNLAWFUL ARREST) ================")
    res_b = agent.run(sig_b, sentinel_b)
    print(json.dumps(res_b, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_run()
