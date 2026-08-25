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
