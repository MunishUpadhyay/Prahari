"""
Prahari Celery Task Chain
=========================

Execution flow:

    ingest_signal(signal_id)
        └─► classify_domain(signal_id)
                └─► route_to_agents(signal_id)
                        └─► coordination_agent(signal_id)
                                └─► push_to_websocket(incident_id)

Each task is currently a stub.  Business logic will be added after the
scaffold review.  The chaining uses Celery's `.si()` (immutable signature)
to pass only explicit arguments — not the previous task's return value.

Usage:
    from pipeline.tasks import ingest_signal
    ingest_signal.delay(str(signal.id))
"""

import logging
from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Ingest
# ---------------------------------------------------------------------------

@shared_task(name="pipeline.ingest_signal")
def ingest_signal(signal_id: str):
    """
    Step 1 — Entry point for the processing pipeline.
    """
    logger.info("[ingest_signal] Processing signal_id=%s", signal_id)
    from apps.signals.models import Signal
    signal = Signal.objects.get(id=signal_id)
    signal.status = 'processing'
    signal.save(update_fields=['status'])
    return classify_domain.delay(signal_id)


# ---------------------------------------------------------------------------
# 2. Classify
# ---------------------------------------------------------------------------

@shared_task(name="pipeline.classify_domain")
def classify_domain(signal_id: str):
    """
    Step 2 — Domain classification.
    """
    logger.info("[classify_domain] Classifying signal_id=%s", signal_id)
    from apps.signals.models import Signal
    from apps.agents.agents import SentinelAgent
    
    signal = Signal.objects.get(id=signal_id)
    agent = SentinelAgent()
    
    start_time = datetime.now(timezone.utc)
    result = agent.run(signal)
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)
    
    # Add timing info to sentinel result dictionary
    result['timing'] = {
        'start': start_time.isoformat(),
        'end': end_time.isoformat(),
        'duration_ms': duration_ms
    }
    
    # Update signal with classified domain
    # Ensure "cross_domain" is mapped to "cross" to fit within max_length=10
    domain_val = result.get('domain')
    if domain_val == 'cross_domain':
        domain_val = 'cross'
    
    signal.domain = domain_val
    signal.status = 'classified'
    signal.save(update_fields=['domain', 'status'])
    
    # Store result and chain to next task
    return route_to_agents.delay(signal_id, result)


# ---------------------------------------------------------------------------
# 3. Route to agents
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=5, name="pipeline.route_to_agents")
def route_to_agents(self, signal_id: str, sentinel_result: dict = None):
    """
    Step 3 — Parallel agent dispatch.
    """
    logger.info("[route_to_agents] signal_id=%s, sentinel_result=%s", signal_id, sentinel_result)
    from apps.signals.models import Signal
    from apps.incidents.models import Incident, SeverityLevel
    from apps.agents.agents import RightsAgent, TriageAgent

    signal = Signal.objects.get(id=signal_id)
    sentinel_result = sentinel_result or {}
    domain = sentinel_result.get("domain") or signal.domain

    # Normalize domain to match Domain choices
    domain_val = domain
    if domain_val == 'cross_domain':
        domain_val = 'cross'

    is_legal_domain = domain_val in ["legal", "cross"]
    is_health_domain = domain_val in ["health", "emergency", "cross"]
    
    # Extract sentinel timing from sentinel result
    sentinel_timing = sentinel_result.pop('timing', None)

    agent_outputs = {
        "sentinel": sentinel_result,
        "timing": {}
    }
    if sentinel_timing:
        agent_outputs["timing"]["sentinel"] = sentinel_timing

    # Run TriageAgent if health, emergency, or cross
    if is_health_domain:
        logger.info("[route_to_agents] Running TriageAgent for signal_id=%s", signal_id)
        triage_agent = TriageAgent()
        start_time = datetime.now(timezone.utc)
        triage_result = triage_agent.run(signal, sentinel_result)
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        agent_outputs["triage"] = triage_result
        agent_outputs["timing"]["triage"] = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'duration_ms': duration_ms
        }

    # Run RightsAgent if legal or cross
    if is_legal_domain:
        logger.info("[route_to_agents] Running RightsAgent for signal_id=%s", signal_id)
        rights_agent = RightsAgent()
        start_time = datetime.now(timezone.utc)
        rights_result = rights_agent.run(signal, sentinel_result)
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        agent_outputs["rights"] = rights_result
        agent_outputs["timing"]["rights"] = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'duration_ms': duration_ms
        }

    # Cross-domain handoff/escalation: if triage results recommend rights escalation and rights agent has not run
    if "triage" in agent_outputs and agent_outputs["triage"].get("escalate_to_rights_agent") and "rights" not in agent_outputs:
        logger.info("[route_to_agents] Escalating to RightsAgent for signal_id=%s due to triage recommendation", signal_id)
        rights_agent = RightsAgent()
        start_time = datetime.now(timezone.utc)
        rights_result = rights_agent.run(signal, sentinel_result)
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        agent_outputs["rights"] = rights_result
        agent_outputs["timing"]["rights"] = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'duration_ms': duration_ms
        }

    # Determine severity properties using a predefined mapping
    SEVERITY_MAP = {
        "critical": 1.0,
        "high": 0.75,
        "medium": 0.5,
        "low": 0.25,
        "immediate": 1.0,
        "delayed": 0.75,
        "minor": 0.25,
        "deceased": 0.0,
    }

    scores = []
    
    # 1. Sentinel Score
    sent_score = sentinel_result.get("severity_score")
    if sent_score is not None:
        try:
            scores.append(float(sent_score))
        except (ValueError, TypeError):
            pass

    # 1b. Sentinel Requires Immediate Action
    if sentinel_result.get("requires_immediate_action") is True:
        scores.append(0.75)
    
    # 2. Sentinel Label Mapped
    sent_label = sentinel_result.get("severity_label", "").lower()
    if sent_label in SEVERITY_MAP:
        scores.append(SEVERITY_MAP[sent_label])

    # 3. Triage Severity Mapped
    if "triage" in agent_outputs:
        triage_sev = agent_outputs["triage"].get("triage_severity", "").lower()
        if triage_sev in SEVERITY_MAP:
            scores.append(SEVERITY_MAP[triage_sev])

    # 4. Rights Severity Mapped
    if "rights" in agent_outputs:
        rights_sev = agent_outputs["rights"].get("severity", "").lower()
        if rights_sev in SEVERITY_MAP:
            scores.append(SEVERITY_MAP[rights_sev])

    # Fallback if no scores collected
    if not scores:
        scores.append(0.0)

    severity_score = max(scores)

    # Normalize back to SeverityLevel choices
    if severity_score >= 0.9:
        severity_label = "critical"
    elif severity_score >= 0.6:
        severity_label = "high"
    elif severity_score >= 0.3:
        severity_label = "medium"
    else:
        severity_label = "low"

    incident, created = Incident.objects.update_or_create(
        signal=signal,
        defaults={
            "severity_score": severity_score,
            "severity_label": severity_label,
            "domain": domain_val,
            "agent_outputs": agent_outputs,
        }
    )

    logger.info("[route_to_agents] Incident %s (created=%s) updated with domain=%s, severity=%s (score=%s). Chaining to coordination_agent.", 
                incident.id, created, domain_val, severity_label, severity_score)

    return coordination_agent.delay(str(incident.id), agent_outputs)


# ---------------------------------------------------------------------------
# 4. Coordination
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=5, name="pipeline.coordination_agent")
def coordination_agent(self, incident_id: str, agent_outputs: dict = None):
    """
    Step 4 — Resource coordination and situation brief.

    Args:
        incident_id (str): UUID string of the Incident.
        agent_outputs (dict): Outputs of preceding agents.
    """
    logger.info("[coordination_agent] Running for incident_id=%s", incident_id)
    from apps.incidents.models import Incident
    from apps.signals.models import Signal
    from apps.agents.agents import CoordinationAgent

    agent_outputs = agent_outputs or {}

    incident = Incident.objects.select_related('signal').get(
        id=incident_id
    )
    signal = incident.signal

    # Rebuild sentinel result from signal fields and preceding outputs
    sentinel_from_outputs = agent_outputs.get('sentinel', {})
    requires_immediate = sentinel_from_outputs.get('requires_immediate_action', True)
    keywords = sentinel_from_outputs.get('keywords', [])

    sentinel_result = {
        'domain': signal.domain,
        'requires_immediate_action': requires_immediate,
        'keywords': keywords
    }

    coord_agent = CoordinationAgent()
    start_time = datetime.now(timezone.utc)
    coord_result = coord_agent.run(signal, sentinel_result, agent_outputs)
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    # Update incident with coordination output
    agent_outputs['coordination'] = coord_result
    if 'timing' not in agent_outputs:
        agent_outputs['timing'] = {}
    agent_outputs['timing']['coordination'] = {
        'start': start_time.isoformat(),
        'end': end_time.isoformat(),
        'duration_ms': duration_ms
    }
    incident.agent_outputs = agent_outputs
    incident.situation_brief = coord_result.get('situation_brief', '')
    incident.severity_score = coord_result.get('overall_severity_score', incident.severity_score)
    incident.save(update_fields=[
        'agent_outputs', 'situation_brief', 'severity_score'
    ])

    # Chain to websocket/language agent
    return push_to_websocket.delay(str(incident_id), coord_result)


# ---------------------------------------------------------------------------
# 5. WebSocket push
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=5, name="pipeline.push_to_websocket")
def push_to_websocket(self, incident_id: str, coord_result: dict = None):
    """
    Step 5 — Push live update to all dashboard WebSocket clients.

    Responsibilities:
        - Load Incident from DB.
        - Run Language Agent to translate the coordination brief to Hindi.
        - Push a message to the channel group ``dashboard_<tenant_id>``
          so all connected DashboardConsumer instances forward it to clients.
    """
    logger.info("[push_to_websocket] incident_id=%s, coord_result=%s", incident_id, coord_result)
    from apps.incidents.models import Incident
    from apps.agents.agents import LanguageAgent
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    import json

    incident = Incident.objects.select_related('signal').get(
        id=incident_id
    )

    # Run Language Agent to get Hindi translation
    hindi_brief = None
    if coord_result:
        agent_outputs = incident.agent_outputs or {}
        if 'timing' not in agent_outputs:
            agent_outputs['timing'] = {}
        
        start_time = datetime.now(timezone.utc)
        try:
            lang_agent = LanguageAgent()
            
            # Construct unified translation payload containing all user-facing text fields
            translation_payload = {
                "situation_title": coord_result.get("situation_title", ""),
                "what_is_happening": coord_result.get("what_is_happening", ""),
                "situation_brief": coord_result.get("situation_brief", ""),
                "resources_needed": coord_result.get("resources_needed", []),
                "authorities_to_notify": coord_result.get("authorities_to_notify", []),
                "conflict_resolution": coord_result.get("conflict_resolution"),
                "escalation_path": coord_result.get("escalation_path", []),
                "immediate_actions": coord_result.get("immediate_actions", []),
            }
            
            triage_out = agent_outputs.get("triage", {})
            if triage_out:
                translation_payload["golden_window"] = triage_out.get("golden_window", {})
                translation_payload["emergency_contacts"] = triage_out.get("emergency_contacts", [])
                translation_payload["primary_concern"] = triage_out.get("primary_concern", "")
                
            rights_out = agent_outputs.get("rights", {})
            if rights_out:
                translation_payload["legal_provisions"] = rights_out.get("legal_provisions", [])
                translation_payload["legal_timeline"] = rights_out.get("legal_timeline", [])

            signal = incident.signal
            print(f"[Language Agent] Running for language: {signal.preferred_language}")
            preferred_lang = signal.preferred_language or 'hindi'
            
            def extract_json_from_text(text: str) -> dict:
                import json
                
                # 1. Brace counter to extract exact JSON block
                def find_json_substring(t: str) -> str:
                    start = t.find("{")
                    if start == -1:
                        return ""
                    brace_count = 0
                    in_string = False
                    escaped = False
                    for idx in range(start, len(t)):
                        char = t[idx]
                        if char == '"' and not escaped:
                            in_string = not in_string
                        elif in_string:
                            if char == '\\':
                                escaped = not escaped
                            else:
                                escaped = False
                        else:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    return t[start:idx+1]
                            escaped = False
                    return ""

                # 2. Devanagari digits replacement
                def clean_json_string(t: str) -> str:
                    devanagari_escapes = {
                        '\\u0966': '0', '\\u0967': '1', '\\u0968': '2', '\\u0969': '3', '\\u096a': '4',
                        '\\u096b': '5', '\\u096c': '6', '\\u096d': '7', '\\u096e': '8', '\\u096f': '9'
                    }
                    for k, v in devanagari_escapes.items():
                        t = t.replace(k, v)
                        t = t.replace(k.upper(), v)
                    devanagari_chars = {
                        '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
                        '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
                    }
                    for k, v in devanagari_chars.items():
                        t = t.replace(k, v)
                    return t

                json_block = find_json_substring(text)
                if not json_block:
                    raise ValueError("No curly braces found in raw LLM response.")
                    
                cleaned_block = clean_json_string(json_block)
                try:
                    return json.loads(cleaned_block)
                except Exception as first_err:
                    # Final attempt: manual escaping of control chars inside string literals
                    try:
                        cleaned_for_json = []
                        in_string = False
                        escaped = False
                        for char in cleaned_block:
                            if char == '"' and not escaped:
                                in_string = not in_string
                                cleaned_for_json.append(char)
                            elif in_string:
                                if char == '\\':
                                    escaped = not escaped
                                    cleaned_for_json.append(char)
                                else:
                                    if char == '\n':
                                        cleaned_for_json.append('\\n')
                                    elif char == '\r':
                                        cleaned_for_json.append('\\r')
                                    elif char == '\t':
                                        cleaned_for_json.append('\\t')
                                    else:
                                        cleaned_for_json.append(char)
                                    escaped = False
                            else:
                                cleaned_for_json.append(char)
                                escaped = False
                        return json.loads("".join(cleaned_for_json))
                    except Exception:
                        raise first_err

            try:
                hindi_brief = lang_agent.run(translation_payload, preferred_lang)
            except ValueError as ve:
                err_msg = str(ve)
                if "Raw content:" in err_msg:
                    raw_content = err_msg.split("Raw content:", 1)[1].strip()
                    try:
                        hindi_brief = extract_json_from_text(raw_content)
                        logger.info("Successfully extracted JSON translation after parsing failure.")
                    except Exception as extract_err:
                        logger.error("Failed to extract JSON translation: %s", extract_err)
                        raise ve
                else:
                    raise ve
            
            # Store translated brief in agent_outputs
            agent_outputs['language'] = {
                signal.preferred_language: hindi_brief,
                'preferred': signal.preferred_language
            }
        except Exception as e:
            # Language translation is non-critical — log and continue
            logger.error("Language agent error (non-critical): %s", e)
        finally:
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            agent_outputs['timing']['language'] = {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'duration_ms': duration_ms
            }
            incident.agent_outputs = agent_outputs
            incident.save(update_fields=['agent_outputs'])

            # Ingest incident to history collection for RAG
            try:
                from rag.ingest import ingest_incident_to_history
                ingest_incident_to_history(
                    str(incident.id),
                    incident.situation_brief or '',
                    incident.domain,
                    incident.severity_label,
                    incident.is_resolved
                )
            except Exception as e:
                logger.error("Failed to ingest incident to history (non-critical): %s", e)

    # Push to WebSocket dashboard
    channel_layer = get_channel_layer()
    tenant_id = str(incident.signal.tenant_id)

    message = {
        'type': 'incident_update',
        'incident_id': str(incident.id),
        'severity': str(incident.severity_score),
        'domain': incident.domain,
        'situation_brief': incident.situation_brief,
        'situation_brief_hindi': hindi_brief.get('situation_brief', '') if hindi_brief else '',
        'agent_outputs': incident.agent_outputs,
        'timestamp': incident.updated_at.isoformat() if incident.updated_at else incident.created_at.isoformat()
    }

    try:
        async_to_sync(channel_layer.group_send)(
            f"dashboard_{tenant_id}",
            {
                'type': 'dashboard.update',
                'message': message
            }
        )
        incident.signal.status = 'processed'
        incident.signal.save(update_fields=['status'])
    except Exception as e:
        logger.error("WebSocket push error (non-critical): %s", e)

    # Trigger SMS notification if contact number is available
    contact_number = incident.signal.contact_number or incident.signal.metadata.get("contact_number")
    if contact_number:
        logger.info("[push_to_websocket] Dispatching send_notification task for signal %s", incident.signal.id)
        from apps.notifications.tasks import send_notification
        send_notification.delay(str(incident.signal.id), str(incident.id))

    return {'incident_id': str(incident_id), 'status': 'complete'}
