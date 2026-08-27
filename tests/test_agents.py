import pytest
import json
from unittest.mock import MagicMock
from apps.agents.base import BaseAgent
from apps.agents.agents import SentinelAgent, LanguageAgent
from apps.signals.models import Signal, SourceType
from apps.tenants.models import Tenant

class MockConcreteAgent(BaseAgent):
    prompt_name = "sentinel"
    def run(self, signal):
        return {}

# 1. BaseAgent JSON Parsing tests
def test_base_agent_json_parsing():
    agent = MockConcreteAgent()
    assert agent.parse_json_response('{"test": "val"}') == {"test": "val"}
    assert agent.parse_json_response('```json\n{"test": "val"}\n```') == {"test": "val"}
    assert agent.parse_json_response('{"test": "val\\nline"}') == {"test": "val\nline"}
    with pytest.raises(ValueError):
        agent.parse_json_response('{"test": "val"')

# 2. Comprehensive Fallback and Error Handling tests
@pytest.fixture
def mock_groq_custom(monkeypatch):
    instantiations = []
    completion_calls = []
    exceptions_to_raise = []
    success_responses = []

    class MockCompletions:
        def create(self, *args, **kwargs):
            completion_calls.append(kwargs)
            if exceptions_to_raise:
                exc = exceptions_to_raise.pop(0)
                if exc:
                    raise exc
            
            resp_content = '{"status": "success", "domain": "legal"}'
            if success_responses:
                resp_content = success_responses.pop(0)
                
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = resp_content
            mock_resp.choices = [mock_choice]
            return mock_resp

    class MockChat:
        def __init__(self):
            self.completions = MockCompletions()

    class MockGroqClient:
        def __init__(self, api_key=None, *args, **kwargs):
            instantiations.append(api_key)
            self.chat = MockChat()

    monkeypatch.setattr("apps.agents.base.Groq", MockGroqClient)
    return instantiations, completion_calls, exceptions_to_raise, success_responses

@pytest.mark.django_db
def test_call_groq_success(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    settings.GROQ_API_KEY_2 = "key_2"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    agent = MockConcreteAgent()
    
    res = agent.call_groq("Hello")
    assert "success" in res
    assert instantiations == ["key_1"]
    assert completion_calls[0]["model"] == "openai/gpt-oss-120b"

@pytest.mark.django_db
def test_call_groq_rate_limit_key_rotation(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    settings.GROQ_API_KEY_2 = "key_2"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    # Configure key 1 to throw 429
    exc = Exception("Rate limit hit 429")
    exc.status_code = 429
    exceptions.append(exc)
    
    agent = MockConcreteAgent()
    res = agent.call_groq("Hello")
    assert "success" in res
    # Should try key_1 (fail), then key_2 (succeed) for primary model
    assert instantiations == ["key_1", "key_2"]
    assert completion_calls[0]["model"] == "openai/gpt-oss-120b"
    assert completion_calls[1]["model"] == "openai/gpt-oss-120b"

@pytest.mark.django_db
def test_call_groq_model_decommissioned_skips_keys(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    settings.GROQ_API_KEY_2 = "key_2"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    # Primary model throws decommissioned (404/not found)
    exc = Exception("Model not found 404")
    exc.status_code = 404
    exceptions.append(exc)
    
    agent = MockConcreteAgent()
    res = agent.call_groq("Hello")
    assert "success" in res
    # Should immediately skip to next model without trying key_2 on first model
    assert instantiations == ["key_1", "key_1"]
    assert completion_calls[0]["model"] == "openai/gpt-oss-120b"
    assert completion_calls[1]["model"] == "openai/gpt-oss-20b"

@pytest.mark.django_db
def test_call_groq_400_bad_request_aborts(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    settings.GROQ_API_KEY_2 = "key_2"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    # Primary model throws 400 Bad Request
    exc = Exception("Bad Request 400")
    exc.status_code = 400
    exceptions.append(exc)
    
    agent = MockConcreteAgent()
    with pytest.raises(Exception) as excinfo:
        agent.call_groq("Hello")
    
    assert "400" in str(excinfo.value)
    # Should abort immediately without key or model fallback
    assert instantiations == ["key_1"]
    assert len(completion_calls) == 1

@pytest.mark.django_db
def test_call_groq_auth_failure_key_rotation(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    settings.GROQ_API_KEY_2 = "key_2"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    # Key 1 throws 401 Unauthorized
    exc = Exception("Unauthorized 401")
    exc.status_code = 401
    exceptions.append(exc)
    
    agent = MockConcreteAgent()
    res = agent.call_groq("Hello")
    assert "success" in res
    # Should rotate keys
    assert instantiations == ["key_1", "key_2"]

@pytest.mark.django_db
def test_call_groq_all_exhausted_raises(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    settings.GROQ_API_KEY_2 = "key_2"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    # Make all attempts (2 models * 2 keys = 4 attempts) raise 429 rate limit
    for _ in range(4):
        exc = Exception("Rate Limit 429")
        exc.status_code = 429
        exceptions.append(exc)
        
    agent = MockConcreteAgent()
    with pytest.raises(Exception) as excinfo:
        agent.call_groq("Hello")
        
    assert "Rate Limit 429" in str(excinfo.value)
    assert len(instantiations) == 4

# 3. SentinelAgent domain normalization test (preserving functional requirement)
@pytest.mark.django_db
def test_sentinel_agent_normalization(mock_groq_custom):
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    successes.append(json.dumps({
        "severity_score": 0.5,
        "severity_label": "medium",
        "domain": "medical",
        "escalate": False,
        "reasoning": "test"
    }))
    
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="medical emergency", source_type=SourceType.TEXT)
    
    agent = SentinelAgent()
    result = agent.run(signal)
    
    # Custom Sentinel run monkeypatch in apps/incidents/apps.py normalizes 'medical' -> 'health'
    assert result["domain"] == "health"

# 4. LanguageAgent Translation tests
@pytest.mark.django_db
def test_language_agent_translation_logic(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    settings.GROQ_API_KEY_2 = "key_2"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    
    # We will return the input JSON back for mock translation sub-calls
    # This validates LanguageAgent's chunking execution flow
    agent = LanguageAgent()
    coord_payload = {
        "situation_title": "Emergency Situation",
        "what_is_happening": "Incident details...",
        "situation_brief": "Summary...",
        "resources_needed": ["Ambulance"],
        "authorities_to_notify": ["DLSA"],
        "legal_provisions": [{"provision": "Article 21", "description": "Life and liberty", "relevance": "Direct"}],
        "legal_timeline": [{"step": 1, "action": "FIR", "timeframe": "Within 24 hours", "why_urgent": "evidence"}]
    }
    
    result = agent.run(coord_payload, target_language="hindi")
    
    # Check that output matches the key structure and Hindi terms post-processed
    assert result["situation_title"] == "Emergency Situation"
    # Ensure regex replaced "Within 24 hours" -> "24 घंटे के भीतर"
    assert result["legal_timeline"][0]["timeframe"] == "24 घंटे के भीतर"
    # Action contains "FIR"
    assert result["legal_timeline"][0]["action"] == "FIR"
    # Authorities to notify contains "DLSA" -> "डीएलएसए"
    assert result["authorities_to_notify"] == ["डीएलएसए"]

def test_triage_agent_max_tokens_limit():
    from apps.agents.agents import TriageAgent
    agent = TriageAgent()
    assert agent.max_tokens == 2000
    assert agent.prompt_name == "triage"

@pytest.mark.django_db
def test_call_groq_structured_output_payload(settings, mock_groq_custom):
    settings.GROQ_API_KEY = "key_1"
    instantiations, completion_calls, exceptions, successes = mock_groq_custom
    
    from apps.agents.agents import TriageAgent, CoordinationAgent, TriageSchema, CoordinationSchema
    
    agent_triage = TriageAgent()
    # Mock retrieve_medical_protocols
    import apps.agents.agents
    orig_retrieve = apps.agents.agents.retrieve_medical_protocols
    apps.agents.agents.retrieve_medical_protocols = MagicMock(return_value=[])
    
    # We need a mock signal
    mock_signal = MagicMock()
    mock_signal.raw_text = "Patient is suffering from heart attack"
    mock_signal.source_type = "web"
    
    successes.append('{"triage_severity": "immediate", "primary_concern": "Cardiac", "interventions": [], "required_facility": "trauma_center", "response_time": "immediate", "hospital_denial_detected": false, "confidence": 0.9, "escalate_to_rights_agent": false, "golden_window": {"time_remaining": "90m", "consequence_of_delay": "tissue damage"}, "emergency_contacts": []}')
    
    agent_triage.run(mock_signal)
    
    # Check Triage completion call parameters
    assert len(completion_calls) == 1
    triage_call = completion_calls[0]
    assert "response_format" in triage_call
    rf = triage_call["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["name"] == "triageschema"
    schema = rf["json_schema"]["schema"]
    assert "triage_severity" in schema["properties"]
    assert schema["additionalProperties"] is False
    
    # Reset and test CoordinationAgent
    completion_calls.clear()
    successes.clear()
    
    agent_coord = CoordinationAgent()
    # Mock other agent outputs
    sentinel_res = {"domain": "health", "requires_immediate_action": True}
    agent_outputs = {"triage": {"triage_severity": "immediate"}}
    
    successes.append('{"situation_title": "Title", "overall_severity": "immediate", "overall_severity_score": 0.9, "what_is_happening": "x", "immediate_actions": [], "resources_needed": [], "authorities_to_notify": [], "situation_brief": "brief", "escalation_required": false, "estimated_resolution_time": "hours", "conflict_resolution": null, "escalation_path": [], "evidence_to_collect": []}')
    
    agent_coord.run(mock_signal, sentinel_res, agent_outputs)
    
    # Check Coordination completion call parameters
    assert len(completion_calls) == 1
    coord_call = completion_calls[0]
    assert "response_format" in coord_call
    rf_coord = coord_call["response_format"]
    assert rf_coord["type"] == "json_schema"
    assert rf_coord["json_schema"]["strict"] is True
    assert rf_coord["json_schema"]["name"] == "coordinationschema"
    schema_coord = rf_coord["json_schema"]["schema"]
    assert "situation_title" in schema_coord["properties"]
    assert schema_coord["additionalProperties"] is False
    
    # Restore retriever mock
    apps.agents.agents.retrieve_medical_protocols = orig_retrieve


# ---------------------------------------------------------------------------
# Phase 2B Reliability & Safety Tests
# ---------------------------------------------------------------------------

def test_rag_threshold_filtering(settings, monkeypatch):
    from rag.retriever import retrieve_legal_provisions
    settings.RAG_LEGAL_DISTANCE_THRESHOLD = 0.5
    settings.RAG_MEDICAL_DISTANCE_THRESHOLD = 0.5
    
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["Relevant provision", "Irrelevant provision"]],
        "metadatas": [[{"category": "test", "act": "test_act", "section": "1"}, {"category": "test", "act": "test_act", "section": "2"}]],
        "distances": [[0.2, 0.8]]
    }
    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection
    monkeypatch.setattr("chromadb.PersistentClient", lambda *args, **kwargs: mock_client)
    
    results = retrieve_legal_provisions("test query")
    assert len(results) == 1
    assert results[0]["distance"] == 0.2
    assert results[0]["text"] == "Relevant provision"


def test_rag_empty_retrieval_behavior(monkeypatch):
    from rag.retriever import retrieve_legal_provisions
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]]
    }
    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection
    monkeypatch.setattr("chromadb.PersistentClient", lambda *args, **kwargs: mock_client)
    
    legal_results = retrieve_legal_provisions("test query")
    assert legal_results == []
    
    from apps.agents.agents import RightsAgent
    agent = RightsAgent()
    mock_signal = MagicMock()
    mock_signal.raw_text = "emergency"
    
    completion_called = False
    def mock_call_groq(user_msg, **kwargs):
        nonlocal completion_called
        completion_called = True
        assert "No sufficiently relevant knowledge-base material was retrieved." in user_msg
        return "{}"
    monkeypatch.setattr(agent, "call_groq", mock_call_groq)
    agent.run(mock_signal)
    assert completion_called is True


def test_authority_contact_sanitization():
    from apps.agents.directory import sanitize_contact_number
    
    assert sanitize_contact_number("01234-567890") == "Verified contact unavailable"
    assert sanitize_contact_number("1800-HOME-SEC") == "Verified contact unavailable"
    assert sanitize_contact_number("please call 9876543210") == "Verified contact unavailable"
    assert sanitize_contact_number("") == "Verified contact unavailable"
    
    assert sanitize_contact_number("108") == "108"
    assert sanitize_contact_number("100") == "100"


def test_evidence_checklist_cases():
    def bringChecklist_python(domain, nearest_authority_type, title, brief):
        domainL = (domain or '').lower()
        auth = (nearest_authority_type or '').strip()
        textToMatch = ((title or '') + ' ' + (brief or '')).lower()
        isTenantDispute = any(k in textToMatch for k in ['evict', 'tenant', 'rent', 'landlord', 'lease'])
        
        if auth == 'Police Complaint Authority' or 'fir refusal' in textToMatch or 'police refused' in textToMatch:
            return 'fir_refusal'
        elif isTenantDispute:
            return 'eviction'
        elif auth == 'Labour Court' or domainL == 'labour':
            return 'wage_theft'
        return 'general'
        
    assert bringChecklist_python("cross_domain", "DLSA", "Mass Shooting", "Emergency active shooter situation") == "general"
    assert bringChecklist_python("legal", "DLSA", "Eviction notice", "Landlord threatened to lock me out of my apartment") == "eviction"


def test_coordination_agent_emergency_priority():
    from apps.agents.agents import reorder_actions_by_safety
    
    actions = [
        {"priority": 1, "action": "File a civil lawsuit against landlord", "responsible_party": "Citizen", "time_window": "3 days"},
        {"priority": 2, "action": "Call 108 ambulance immediately", "responsible_party": "Citizen", "time_window": "1 minute"}
    ]
    reordered = reorder_actions_by_safety(actions, "Active shooter incident, patient bleeding and needs hospital")
    assert reordered[0]["priority"] == 1
    assert "ambulance" in reordered[0]["action"]
    assert reordered[1]["priority"] == 2
    assert "lawsuit" in reordered[1]["action"]


def test_coordination_agent_severity_protection():
    from apps.agents.agents import CoordinationAgent
    agent = CoordinationAgent()
    mock_signal = MagicMock()
    mock_signal.raw_text = "Mass casualty event"
    
    sentinel_res = {"domain": "health", "requires_immediate_action": True, "severity_score": 0.9}
    agent_outputs = {"triage": {"triage_severity": "immediate"}}
    
    import json
    def mock_call_groq(*args, **kwargs):
        return json.dumps({
            "situation_title": "Title",
            "overall_severity": "low",
            "overall_severity_score": 0.2,
            "what_is_happening": "x",
            "immediate_actions": [],
            "resources_needed": [],
            "authorities_to_notify": [],
            "situation_brief": "brief",
            "escalation_required": False,
            "estimated_resolution_time": "hours",
            "conflict_resolution": None,
            "escalation_path": [],
            "evidence_to_collect": []
        })
        
    agent.call_groq = mock_call_groq
    result = agent.run(mock_signal, sentinel_res, agent_outputs)
    assert result["overall_severity_score"] == 0.9
    assert result["overall_severity"] == "critical"
