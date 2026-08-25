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
    max_tokens = 2000

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
    max_tokens = 2000

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

        # Validate evidence_to_collect (Upgrade 2)
        etc = result.get("evidence_to_collect")
        if not isinstance(etc, list):
            result["evidence_to_collect"] = []
        else:
            validated_etc = []
            for item in etc:
                if isinstance(item, dict) and "item" in item:
                    validated_etc.append({
                        "item": str(item.get("item", "")),
                        "why_important": str(item.get("why_important", "")),
                        "how_to_collect": str(item.get("how_to_collect", "")),
                        "time_sensitive": bool(item.get("time_sensitive", False))
                    })
            result["evidence_to_collect"] = validated_etc[:5]

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
    max_tokens = 2500

    def _translate_payload(self, payload: dict, target_language: str) -> dict:
        import json
        if not payload:
            return payload
        user_message = f"""Translate all text values in the following JSON object into {target_language} (Devanagari script for Hindi).
Return a valid JSON object matching the input structure exactly with translated values.
Translate all texts, descriptions, names of laws/sections, legal provisions, citations, and time values (like "within 24 hours", "immediate", "immediately", "within 10 minutes", etc.) into natural {target_language}.
Do NOT keep legal references, names of laws, or timeframes in English. Translate them fully.
Keep only numeric values, severity labels, and boolean values unchanged.

Input JSON:
{json.dumps(payload, indent=2, ensure_ascii=False)}

Return only the valid JSON object."""
        try:
            raw = self.call_groq(user_message)
            return self.parse_json_response(raw)
        except Exception as exc:
            logger.error("[LanguageAgent] Sub-translation failed: %s", exc)
            return payload

    def _force_hindi_translation(self, val: str) -> str:
        import re
        if not isinstance(val, str):
            return val
        replacements = [
            # Laws/Sections/Citations
            (r'\b[Ss]ection\s+(\d+)\s+[Cc]r[Pp][Cc]\s*\(\s*now\s+[Ss]ection\s+(\d+)\s+[Bb][Nn][Ss][Ss]\s*\)', r'धारा \1 सीआरपीसी (अब धारा \2 बीएनएसएस)'),
            (r'\b[Ss]ection\s+(\d+)\s+[Cc]r[Pp][Cc]', r'धारा \1 सीआरपीसी'),
            (r'\b[Ss]ection\s+(\d+)\s+[Bb][Nn][Ss][Ss]', r'धारा \1 बीएनएसएस'),
            (r'\b[Aa]rticle\s+(\d+)\s+of\s+[Cc]onstitution', r'संविधान का अनुच्छेद \1'),
            (r'\b[Aa]rticle\s+(\d+)', r'अनुच्छेद \1'),
            (r'\b[Dd]\.?[Kk]\.?\s+[Bb]asu\s+[Gg]uidelines\b', 'डी.के. बसु दिशानिर्देश'),
            (r'\b[Cc]r[Pp][Cc]\b', 'सीआरपीसी'),
            (r'\b[Bb][Nn][Ss][Ss]\b', 'बीएनएसएस'),
            
            # Timeframes
            (r'\b[Ww]ithin\s+(\d+)\s+hours\b', r'\1 घंटे के भीतर'),
            (r'\b[Ww]ithin\s+(\d+)\s+hour\b', r'\1 घंटे के भीतर'),
            (r'\b[Ww]ithin\s+(\d+)\s+minutes\b', r'\1 मिनट के भीतर'),
            (r'\b[Ww]ithin\s+(\d+)\s+minute\b', r'\1 मिनट के भीतर'),
            (r'\b[Ww]ithin\s+(\d+)-(\d+)\s+minutes\b', r'\1-\2 मिनट के भीतर'),
            (r'\b[Ww]ithin\s+(\d+)-(\d+)\s+hours\b', r'\1-\2 घंटे के भीतर'),
            (r'\b[Ii]mmediately\b', 'तुरंत'),
            (r'\b[Ii]mmediate\b', 'तुरंत'),
            (r'\b[Nn]ow\b', 'अब'),
            (r'\b(\d+)\s+minutes\b', r'\1 मिनट'),
            (r'\b(\d+)\s+hours\b', r'\1 घंटे'),
            (r'\b(\d+)\s+days\b', r'\1 दिन'),
            
            # Authorities
            (r'\bDistrict Legal Services Authority\s*\(\s*DLSA\s*\)', 'जिला कानूनी सेवा प्राधिकरण (डीएलएसए)'),
            (r'\bNational Legal Services Authority\s*\(\s*NALSA\s*\)', 'राष्ट्रीय कानूनी सेवा प्राधिकरण (एनएएलएसए)'),
            (r'\bChief Medical Officer\s*\(\s*CMO\s*\)', 'मुख्य चिकित्सा अधिकारी (सीएमओ)'),
            (r'\bSuperintendent of Police\s*\(\s*SP\s*\)', 'पुलिस अधीक्षक (एसपी)'),
            (r'\bSenior Superintendent of Police\s*\(\s*SSP\s*\)', 'वरिष्ठ पुलिस अधीक्षक (एसएसपी)'),
            (r'\bDistrict Collector\b', 'जिला कलेक्टर'),
            (r'\bDLSA\b', 'डीएलएसए'),
            (r'\bNALSA\b', 'एनएएलएसए'),
            (r'\bCMO\b', 'सीएमओ'),
            (r'\bSP\b', 'एसपी'),
            (r'\bSSP\b', 'एसएसपी'),
            (r'\bEmergency Response Coordinator\b', 'आपातकालीन प्रतिक्रिया समन्वयक'),
            (r'\bNational Ambulance\b', 'राष्ट्रीय एम्बुलेंस'),
            (r'\bFire Brigade\b', 'दमकल केंद्र'),
            (r'\bPolice\b', 'पुलिस'),
            (r'\bAmbulance\b', 'एम्बुलेंस'),
        ]
        res = val
        for pattern, repl in replacements:
            res = re.sub(pattern, repl, res, flags=re.IGNORECASE)
        return res

    def _post_process_translate(self, obj: any, target_language: str) -> any:
        if target_language != "hindi":
            return obj
        if isinstance(obj, dict):
            return {k: self._post_process_translate(v, target_language) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._post_process_translate(x, target_language) for x in obj]
        elif isinstance(obj, str):
            return self._force_hindi_translation(obj)
        else:
            return obj

    def run(self, coord_result: dict, target_language: str = "hindi") -> dict:
        logger.info("[LanguageAgent] Running translation in separate sub-payloads to prevent truncation and ensure 100%% translation")

        translated_result = {}

        # 1. Overview
        overview_payload = {
            "situation_title": coord_result.get("situation_title", ""),
            "what_is_happening": coord_result.get("what_is_happening", ""),
            "situation_brief": coord_result.get("situation_brief", ""),
            "primary_concern": coord_result.get("primary_concern", ""),
            "nearest_authority_type": coord_result.get("nearest_authority_type", ""),
            "authority_to_contact": coord_result.get("authority_to_contact", ""),
            "golden_window": coord_result.get("golden_window", {}),
            "conflict_resolution": coord_result.get("conflict_resolution", {})
        }
        overview_translated = self._translate_payload(overview_payload, target_language)
        translated_result.update(overview_translated)

        # 2. Basic lists
        lists_payload = {
            "resources_needed": coord_result.get("resources_needed", []),
            "authorities_to_notify": coord_result.get("authorities_to_notify", []),
            "emergency_contacts": coord_result.get("emergency_contacts", [])
        }
        lists_translated = self._translate_payload(lists_payload, target_language)
        translated_result.update(lists_translated)

        # 3. legal_provisions
        if "legal_provisions" in coord_result:
            provs_payload = {"legal_provisions": coord_result["legal_provisions"]}
            provs_translated = self._translate_payload(provs_payload, target_language)
            translated_result.update(provs_translated)

        # 4. legal_timeline
        if "legal_timeline" in coord_result:
            timeline_payload = {"legal_timeline": coord_result["legal_timeline"]}
            timeline_translated = self._translate_payload(timeline_payload, target_language)
            translated_result.update(timeline_translated)

        # 5. immediate_actions
        if "immediate_actions" in coord_result:
            actions_payload = {"immediate_actions": coord_result["immediate_actions"]}
            actions_translated = self._translate_payload(actions_payload, target_language)
            translated_result.update(actions_translated)

        # 6. evidence_to_collect
        if "evidence_to_collect" in coord_result:
            evidence_payload = {"evidence_to_collect": coord_result["evidence_to_collect"]}
            evidence_translated = self._translate_payload(evidence_payload, target_language)
            translated_result.update(evidence_translated)

        # 7. escalation_path
        if "escalation_path" in coord_result:
            escalation_payload = {"escalation_path": coord_result["escalation_path"]}
            escalation_translated = self._translate_payload(escalation_payload, target_language)
            translated_result.update(escalation_translated)

        # General fallbacks for any other keys
        for key, val in coord_result.items():
            if key not in translated_result:
                translated_result[key] = val

        # Apply recursive post-processing to force Hindi translation for legal & time terms
        translated_result = self._post_process_translate(translated_result, target_language)

        return translated_result


class LegalNoticeAgent(BaseAgent):
    """
    Agent for generating legal notice drafts based on incident data and rights assessments.
    """
    prompt_name = "legal_notice"
    max_tokens = 3000

    def run(self, signal, rights_result: dict, target_language: str = "english") -> str:
        logger.info("[LegalNoticeAgent] Running on signal %s with target_language %s", getattr(signal, 'id', 'mock_id'), target_language)
        
        # Format rights result context
        rights_context = ""
        if rights_result:
            rights_context += f"Rights Violated: {', '.join(rights_result.get('rights_violated', []))}\n"
            rights_context += "Legal Provisions:\n"
            for prov in rights_result.get("legal_provisions", []):
                rights_context += f"- Provision: {prov.get('provision')}\n"
                rights_context += f"  Description: {prov.get('description')}\n"
                rights_context += f"  Relevance: {prov.get('relevance')}\n"
            rights_context += f"Recommended Immediate Actions: {', '.join(rights_result.get('immediate_actions', []))}\n"
            rights_context += f"Authority to Contact: {rights_result.get('authority_to_contact')}\n"

        lang_instruction = ""
        if target_language == "hindi":
            lang_instruction = "Generate the complete legal notice in fluent, professional, and authoritative legal HINDI (Devanagari script), translating all sections, facts, demands, and compliance details fully. Maintain a high-quality formal tone."
        else:
            lang_instruction = "Generate the complete legal notice in fluent, professional, and authoritative legal English."

        user_message = (
            f"Signal text: {signal.raw_text}\n\n"
            f"Rights Assessment context:\n{rights_context}\n\n"
            f"{lang_instruction}\n\n"
            f"Please generate the complete legal notice draft based on the above information."
        )

        raw_response = self.call_groq(user_message)
        # We do NOT parse it as JSON, just return the raw string response
        return raw_response.strip()

