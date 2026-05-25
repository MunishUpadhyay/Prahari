"""
All five Prahari domain agents.

Each agent:
    1. Loads its system prompt from prompts/<name>.txt
    2. Will call the Groq API (logic pending review)
    3. Returns a structured dict stored in Incident.agent_outputs

Agents:
    SentinelAgent    — threat detection, severity scoring, domain classification
    RightsAgent      — legal rights identification and advice
    TriageAgent      — medical/emergency triage and urgency scoring
    CoordinationAgent — resource matching and dispatch recommendations
    LanguageAgent    — multilingual situation brief generation
"""

import logging

from .base import BaseAgent
from rag.retriever import retrieve_legal_provisions, retrieve_medical_protocols

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentinel Agent
# ---------------------------------------------------------------------------

class SentinelAgent(BaseAgent):
    """
    Threat detection and initial classification agent.

    Responsibilities:
        - Analyse the raw signal for threat indicators.
        - Assign a severity score in [0.0, 1.0].
        - Classify the domain (legal / health / emergency / cross).
        - Flag whether the signal requires immediate escalation.

    Output schema:
        {
            "severity_score": float,       # 0.0–1.0
            "severity_label": str,         # "low" | "medium" | "high" | "critical"
            "domain": str,                 # "legal" | "health" | "emergency" | "cross"
            "escalate": bool,
            "reasoning": str
        }
    """

    prompt_name = "sentinel"

    def run(self, signal) -> dict:
        logger.info("[SentinelAgent] Running domain classification on signal %s", getattr(signal, 'id', 'mock_id'))
        
        user_message = f"Classify this signal:\n\nText: {signal.raw_text}\nSource: {signal.source_type}"
        raw_response = self.call_groq(user_message)
        result = self.parse_json_response(raw_response)
        
        valid_domains = {"legal", "health", "emergency", "cross_domain"}
        domain = result.get("domain")
        if domain not in valid_domains:
            raise ValueError(f"Invalid domain returned: {domain}. Expected one of {valid_domains}")
            
        return result


# ---------------------------------------------------------------------------
# Rights Agent
# ---------------------------------------------------------------------------

class RightsAgent(BaseAgent):
    """
    Legal rights identification and advisory agent.

    Responsibilities:
        - Identify which legal rights are relevant to the signal.
        - Cite applicable laws, articles, or provisions.
        - Suggest immediate legal actions the affected party can take.

    Output schema:
        {
            "rights_violated": [str],
            "severity": str,             # "critical" | "high" | "medium" | "low"
            "legal_provisions": [
                {
                    "provision": str,
                    "description": str,
                    "relevance": str
                }
            ],
            "immediate_actions": [str],
            "authority_to_contact": str,
            "case_strength": float       # 0.0 - 1.0
        }
    """

    prompt_name = "rights"

    def run(self, signal, sentinel_result=None) -> dict:
        logger.info("[RightsAgent] Running on signal %s", getattr(signal, 'id', 'mock_id'))

        # 1. Retrieve relevant legal provisions from local ChromaDB vector store
        provisions = retrieve_legal_provisions(signal.raw_text, n_results=3)
        
        # 2. Format provisions context
        provisions_text = ""
        for i, prov in enumerate(provisions, 1):
            provisions_text += f"\nProvision {i}:\n"
            provisions_text += f"Text: {prov['text']}\n"
            provisions_text += f"Metadata: {prov['metadata']}\n"

        # 3. Construct user message
        sentinel_domain = sentinel_result.get("domain") if sentinel_result else "legal"
        user_message = (
            f"Signal text: {signal.raw_text}\n"
            f"Sentinel domain classification: {sentinel_domain}\n\n"
            f"Retrieved relevant Indian legal provisions context:\n{provisions_text}"
        )

        # 4. Call Groq LLM
        raw_response = self.call_groq(user_message)
        result = self.parse_json_response(raw_response)

        # 5. Validate output schema structure
        if not isinstance(result.get("rights_violated"), list):
            result["rights_violated"] = []
        if not isinstance(result.get("legal_provisions"), list):
            result["legal_provisions"] = []
        if not isinstance(result.get("immediate_actions"), list):
            result["immediate_actions"] = []
        if "severity" not in result:
            result["severity"] = "medium"
        if "authority_to_contact" not in result:
            result["authority_to_contact"] = "Local Legal Services Authority"
        try:
            result["case_strength"] = float(result.get("case_strength", 0.5))
        except (ValueError, TypeError):
            result["case_strength"] = 0.5

        # Validate nearest_authority_type
        valid_authorities = {"DLSA", "High Court", "Consumer Forum", "Labour Court", "Police Complaint Authority", "Magistrate Court"}
        nat = result.get("nearest_authority_type")
        if nat not in valid_authorities:
            result["nearest_authority_type"] = "DLSA"

        # Validate legal_timeline
        timeline = result.get("legal_timeline")
        if not isinstance(timeline, list):
            # Try to build a basic one from immediate_actions if empty
            actions = result.get("immediate_actions") or ["Contact local legal aid panel advocate."]
            timeline = []
            for i, act in enumerate(actions[:4], 1):
                timeline.append({
                    "step": i,
                    "action": act,
                    "timeframe": "Within 24-48 hours",
                    "why_urgent": "To prevent delay in seeking remedy."
                })
        else:
            validated_timeline = []
            for item in timeline:
                if isinstance(item, dict):
                    try:
                        step_num = int(item.get("step", len(validated_timeline) + 1))
                    except (ValueError, TypeError):
                        step_num = len(validated_timeline) + 1
                    validated_timeline.append({
                        "step": step_num,
                        "action": str(item.get("action", "Consult DLSA panel advocate.")),
                        "timeframe": str(item.get("timeframe", "Immediate")),
                        "why_urgent": str(item.get("why_urgent", "Action is time critical."))
                    })
            timeline = validated_timeline[:4]
        result["legal_timeline"] = timeline

        return result


# ---------------------------------------------------------------------------
# Triage Agent
# ---------------------------------------------------------------------------

class TriageAgent(BaseAgent):
    """
    Medical and emergency triage agent.

    Responsibilities:
        - Assess the medical or physical urgency of the signal.
        - Recommend appropriate emergency response level.
        - Identify symptoms or emergency indicators.

    Output schema:
        {
            "triage_severity": str,       # "immediate" | "delayed" | "minor" | "deceased"
            "primary_concern": str,
            "interventions": [str],
            "required_facility": str,     # "trauma_center" | "general_hospital" | "clinic" | "mental_health" | "obstetric"
            "response_time": str,         # "immediate" | "urgent" | "semi_urgent" | "non_urgent"
            "hospital_denial_detected": bool,
            "confidence": float,
            "escalate_to_rights_agent": bool
        }
    """

    prompt_name = "triage"

    def run(self, signal, sentinel_result=None) -> dict:
        logger.info("[TriageAgent] Running on signal %s", getattr(signal, 'id', 'mock_id'))

        # 1. Retrieve relevant medical protocols from local ChromaDB vector store
        protocols = retrieve_medical_protocols(signal.raw_text, n_results=3)
        
        # 2. Format protocols context
        protocols_text = ""
        for i, prot in enumerate(protocols, 1):
            protocols_text += f"\nProtocol {i}:\n"
            protocols_text += f"Text: {prot['text']}\n"
            protocols_text += f"Metadata: {prot['metadata']}\n"

        # 3. Construct user message
        sentinel_domain = sentinel_result.get("domain") if sentinel_result else "health"
        user_message = (
            f"Signal text: {signal.raw_text}\n"
            f"Sentinel domain classification: {sentinel_domain}\n\n"
            f"Retrieved relevant medical protocols context:\n{protocols_text}"
        )

        # 4. Call Groq LLM
        raw_response = self.call_groq(user_message)
        result = self.parse_json_response(raw_response)

        # 5. Validate output schema structure and fallback
        if "triage_severity" not in result:
            result["triage_severity"] = "minor"
        if "primary_concern" not in result:
            result["primary_concern"] = "Unknown medical concern."
        if not isinstance(result.get("interventions"), list):
            result["interventions"] = []
        if "required_facility" not in result:
            result["required_facility"] = "general_hospital"
        if "response_time" not in result:
            result["response_time"] = "non_urgent"
        if "hospital_denial_detected" not in result:
            result["hospital_denial_detected"] = False
        try:
            result["confidence"] = float(result.get("confidence", 0.5))
        except (ValueError, TypeError):
            result["confidence"] = 0.5
        if "escalate_to_rights_agent" not in result:
            result["escalate_to_rights_agent"] = bool(result.get("hospital_denial_detected", False))
        else:
            result["escalate_to_rights_agent"] = bool(result["escalate_to_rights_agent"])

        # Validate golden_window
        gw = result.get("golden_window")
        if not isinstance(gw, dict):
            result["golden_window"] = {
                "time_remaining": "Unknown",
                "consequence_of_delay": "Delayed treatment may cause the patient's condition to deteriorate."
            }
        else:
            result["golden_window"] = {
                "time_remaining": str(gw.get("time_remaining", "Unknown")),
                "consequence_of_delay": str(gw.get("consequence_of_delay", "Delayed treatment may cause the patient's condition to deteriorate."))
            }

        # Validate emergency_contacts
        contacts = result.get("emergency_contacts")
        if not isinstance(contacts, list):
            result["emergency_contacts"] = [
                {"name": "National Ambulance", "number": "108", "when_to_call": "Immediately for life threatening medical emergencies"},
                {"name": "Police", "number": "100", "when_to_call": "If access is being blocked or safety is threatened"}
            ]
        else:
            validated_contacts = []
            for item in contacts:
                if isinstance(item, dict):
                    validated_contacts.append({
                        "name": str(item.get("name", "Emergency Service")),
                        "number": str(item.get("number", "108")),
                        "when_to_call": str(item.get("when_to_call", "Immediately"))
                    })
            result["emergency_contacts"] = validated_contacts

        return result


# ---------------------------------------------------------------------------
# Coordination Agent
# ---------------------------------------------------------------------------

class CoordinationAgent(BaseAgent):
    """
    Resource matching and dispatch coordination agent.

    Responsibilities:
        - Receives outputs from Sentinel, Triage, and Rights agents.
        - Synthesizes all inputs into a single situation brief.
        - Produces a prioritized list of immediate actions.
        - Recommends resources and authorities to notify.

    Output schema:
        {
            "situation_title": str,
            "overall_severity": str,
            "overall_severity_score": float,
            "what_is_happening": str,
            "immediate_actions": [dict],
            "resources_needed": [str],
            "authorities_to_notify": [str],
            "situation_brief": str,
            "escalation_required": bool,
            "estimated_resolution_time": str
        }
    """

    prompt_name = "coordination"

    def run(self, signal, sentinel_result: dict, agent_outputs: dict) -> dict:
        logger.info("[CoordinationAgent] Running on signal %s", getattr(signal, 'id', 'mock_id'))

        # Build context from all available agent outputs
        context_parts = [
            f"Original signal: {signal.raw_text}",
            f"Domain: {sentinel_result.get('domain')}",
            f"Requires immediate action: {sentinel_result.get('requires_immediate_action')}",
        ]

        if 'rights' in agent_outputs:
            r = agent_outputs['rights']
            context_parts.append(
                f"Legal assessment:\n"
                f"  Rights violated: {r.get('rights_violated', [])}\n"
                f"  Severity: {r.get('severity')}\n"
                f"  Immediate actions: {r.get('immediate_actions', [])}\n"
                f"  Authority: {r.get('authority_to_contact')}"
            )

        if 'triage' in agent_outputs:
            t = agent_outputs['triage']
            context_parts.append(
                f"Medical assessment:\n"
                f"  Triage severity: {t.get('triage_severity')}\n"
                f"  Primary concern: {t.get('primary_concern')}\n"
                f"  Interventions needed: {t.get('interventions', [])}\n"
                f"  Required facility: {t.get('required_facility')}\n"
                f"  Response time: {t.get('response_time')}\n"
                f"  Hospital denial: {t.get('hospital_denial_detected')}"
            )

        user_message = "\n\n".join(context_parts)
        user_message += "\n\nSynthesize all of the above into a unified coordination brief."

        raw = self.call_groq(user_message)
        result = self.parse_json_response(raw)

        # Fallbacks/Validations for coordination output schema
        if "situation_title" not in result:
            result["situation_title"] = "Unified Situation Brief"
        if "overall_severity" not in result:
            result["overall_severity"] = "medium"
        try:
            result["overall_severity_score"] = float(result.get("overall_severity_score", 0.5))
        except (ValueError, TypeError):
            result["overall_severity_score"] = 0.5
        if "what_is_happening" not in result:
            result["what_is_happening"] = signal.raw_text
        
        if not isinstance(result.get("immediate_actions"), list):
            result["immediate_actions"] = []
        else:
            validated_actions = []
            for action in result["immediate_actions"]:
                if isinstance(action, dict):
                    try:
                        prio = int(action.get("priority", 1))
                    except (ValueError, TypeError):
                        prio = 1
                    validated_actions.append({
                        "priority": prio,
                        "action": str(action.get("action", "")),
                        "responsible_party": str(action.get("responsible_party", "")),
                        "time_window": str(action.get("time_window", ""))
                    })
            validated_actions.sort(key=lambda x: x["priority"])
            result["immediate_actions"] = validated_actions[:5]

        if not isinstance(result.get("resources_needed"), list):
            result["resources_needed"] = []
        if not isinstance(result.get("authorities_to_notify"), list):
            result["authorities_to_notify"] = []
        if "situation_brief" not in result:
            result["situation_brief"] = result.get("what_is_happening", "")[:100]
        if "escalation_required" not in result:
            result["escalation_required"] = False
        else:
            result["escalation_required"] = bool(result["escalation_required"])
        if "estimated_resolution_time" not in result:
            result["estimated_resolution_time"] = "hours"

        # Validate conflict_resolution for cross_domain/cross signals
        is_cross = sentinel_result.get("domain") in ["cross", "cross_domain"]
        cr = result.get("conflict_resolution")
        if is_cross:
            if not isinstance(cr, dict):
                result["conflict_resolution"] = {
                    "primary_priority": "medical",
                    "reasoning": "A life-threatening medical emergency takes absolute precedence over legal proceedings.",
                    "sequence": "First, stabilize patient and secure admission. Second, initiate legal/police complaint against the hospital's denial."
                }
            else:
                result["conflict_resolution"] = {
                    "primary_priority": str(cr.get("primary_priority", "medical")),
                    "reasoning": str(cr.get("reasoning", "Medical stabilization is prioritized over legal remedy.")),
                    "sequence": str(cr.get("sequence", "Handle medical needs first, then proceed with legal remedies."))
                }
        else:
            result["conflict_resolution"] = None

        # Validate escalation_path
        ep = result.get("escalation_path")
        if not isinstance(ep, list):
            result["escalation_path"] = [
                {
                    "level": 1,
                    "authority": "Chief Medical Officer / District Magistrate",
                    "trigger": "If hospital refuses admission after 15 minutes",
                    "contact": "CMO Office / District Legal Services Authority (DLSA) helpline 15100"
                }
            ]
        else:
            validated_ep = []
            for item in ep:
                if isinstance(item, dict):
                    try:
                        level_num = int(item.get("level", len(validated_ep) + 1))
                    except (ValueError, TypeError):
                        level_num = len(validated_ep) + 1
                    validated_ep.append({
                        "level": level_num,
                        "authority": str(item.get("authority", "District Authority")),
                        "trigger": str(item.get("trigger", "Immediate if no response")),
                        "contact": str(item.get("contact", "Call 15100 DLSA / National helpline"))
                    })
            result["escalation_path"] = validated_ep[:3]

        return result


class LanguageAgent(BaseAgent):
    """
    Multilingual situation brief generation agent.

    Responsibilities:
        - Receives the English coordination brief JSON object.
        - Translates specific fields into the target language (e.g. Hindi).
        - Keeps severity scores, priority labels, time windows, and booleans in their original format.

    Output schema:
        Matches the input coordination brief structure.
    """

    prompt_name = "language"
    max_tokens = 1500

    def run(self, coord_result: dict, target_language: str = "hindi") -> dict:
        import json
        logger.info("[LanguageAgent] Running on incident coordination result to translate to %s", target_language)

        user_message = f"""Translate the following coordination
brief fields into {target_language}. Return the complete JSON
with translated fields. Keep all numeric values, severity labels,
boolean values, and time values unchanged.

Input JSON:
{json.dumps(coord_result, indent=2, ensure_ascii=False)}

Return the complete translated JSON."""

        raw = self.call_groq(user_message)
        result = self.parse_json_response(raw)

        # Fallbacks/Validations to ensure schema structure matches the input coordination brief
        for key in ["situation_title", "overall_severity", "overall_severity_score", 
                    "what_is_happening", "resources_needed", "authorities_to_notify", 
                    "situation_brief", "escalation_required", "estimated_resolution_time"]:
            if key not in result:
                result[key] = coord_result.get(key)

        try:
            result["overall_severity_score"] = float(result.get("overall_severity_score", coord_result.get("overall_severity_score", 0.5)))
        except (ValueError, TypeError):
            result["overall_severity_score"] = coord_result.get("overall_severity_score", 0.5)

        result["escalation_required"] = bool(result.get("escalation_required", coord_result.get("escalation_required", False)))

        # Validate immediate_actions structure
        if not isinstance(result.get("immediate_actions"), list):
            result["immediate_actions"] = coord_result.get("immediate_actions", [])
        else:
            validated_actions = []
            orig_actions = coord_result.get("immediate_actions", [])
            for i, action in enumerate(result["immediate_actions"]):
                if isinstance(action, dict):
                    orig_action = orig_actions[i] if i < len(orig_actions) else {}
                    validated_actions.append({
                        "priority": orig_action.get("priority", action.get("priority", i+1)),
                        "action": str(action.get("action", orig_action.get("action", ""))),
                        "responsible_party": str(action.get("responsible_party", orig_action.get("responsible_party", ""))),
                        "time_window": orig_action.get("time_window", action.get("time_window", ""))
                    })
            result["immediate_actions"] = validated_actions

        return result
