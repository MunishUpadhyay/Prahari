"""
Signals app configuration.
"""
from django.apps import AppConfig


def patched_language_agent_run(self, coord_result: dict, target_language: str = "hindi") -> dict:
    import json
    import logging
    import re
    logger = logging.getLogger(__name__)
    logger.info("[Patched LanguageAgent] Running translation in separate lists to prevent truncation and ensure 100% translation")

    translated_result = {}
    
    # Helper to call LLM for a specific sub-dict/field
    def translate_payload(payload):
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
            logger.error("[Patched LanguageAgent] Sub-translation failed: %s", exc)
            return payload

    # Helper for post-processing translation of remaining English terms to Hindi
    def force_hindi_translation(val):
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

    # Recursive function to apply force translation to string values in a dict/list
    def post_process_translate(obj):
        if isinstance(obj, dict):
            return {k: post_process_translate(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [post_process_translate(x) for x in obj]
        elif isinstance(obj, str):
            return force_hindi_translation(obj)
        else:
            return obj

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
    overview_translated = translate_payload(overview_payload)
    translated_result.update(overview_translated)

    # 2. Basic lists
    lists_payload = {
        "resources_needed": coord_result.get("resources_needed", []),
        "authorities_to_notify": coord_result.get("authorities_to_notify", []),
        "emergency_contacts": coord_result.get("emergency_contacts", [])
    }
    lists_translated = translate_payload(lists_payload)
    translated_result.update(lists_translated)

    # 3. legal_provisions
    if "legal_provisions" in coord_result:
        provs_payload = {"legal_provisions": coord_result["legal_provisions"]}
        provs_translated = translate_payload(provs_payload)
        translated_result.update(provs_translated)

    # 4. legal_timeline
    if "legal_timeline" in coord_result:
        timeline_payload = {"legal_timeline": coord_result["legal_timeline"]}
        timeline_translated = translate_payload(timeline_payload)
        translated_result.update(timeline_translated)

    # 5. immediate_actions
    if "immediate_actions" in coord_result:
        actions_payload = {"immediate_actions": coord_result["immediate_actions"]}
        actions_translated = translate_payload(actions_payload)
        translated_result.update(actions_translated)

    # 6. evidence_to_collect
    if "evidence_to_collect" in coord_result:
        evidence_payload = {"evidence_to_collect": coord_result["evidence_to_collect"]}
        evidence_translated = translate_payload(evidence_payload)
        translated_result.update(evidence_translated)

    # 7. escalation_path
    if "escalation_path" in coord_result:
        escalation_payload = {"escalation_path": coord_result["escalation_path"]}
        escalation_translated = translate_payload(escalation_payload)
        translated_result.update(escalation_translated)

    # General fallbacks for any other keys
    for key, val in coord_result.items():
        if key not in translated_result:
            translated_result[key] = val

    # Apply recursive post-processing to force Hindi translation for legal & time terms
    if target_language == "hindi":
        translated_result = post_process_translate(translated_result)

    return translated_result


class SignalsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.signals"
    label = "signals"

    def ready(self):
        from apps.agents.agents import LanguageAgent
        LanguageAgent.run = patched_language_agent_run
