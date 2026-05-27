from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.incidents"
    label = "incidents"

    def ready(self):
        from apps.agents.base import BaseAgent
        import logging

        logger = logging.getLogger(__name__)
        original_call_groq = BaseAgent.call_groq

        def fallback_call_groq(self, user_message: str) -> str:
            try:
                return original_call_groq(self, user_message)
            except Exception as exc:
                is_rate_limit = (
                    "429" in str(exc)
                    or "rate_limit" in str(exc).lower()
                    or "too many requests" in str(exc).lower()
                    or getattr(getattr(exc, "response", None), "status_code", None) == 429
                )
                if is_rate_limit:
                    logger.warning(
                        "[BaseAgent Monkeypatch] Rate limit hit for model %s. "
                        "Falling back to llama-3.1-8b-instant.",
                        self.model
                    )
                    original_model = self.model
                    self.model = "llama-3.1-8b-instant"
                    try:
                        return original_call_groq(self, user_message)
                    finally:
                        self.model = original_model
                raise

        BaseAgent.call_groq = fallback_call_groq

        from apps.agents.agents import SentinelAgent

        def custom_sentinel_run(self, signal) -> dict:
            logger.info(
                "[SentinelAgent Monkeypatch] Running domain classification on signal %s",
                getattr(signal, 'id', 'mock_id')
            )
            user_message = (
                f"Classify this signal:\n\nText: {signal.raw_text}\n"
                f"Source: {signal.source_type}"
            )
            raw_response = self.call_groq(user_message)
            result = self.parse_json_response(raw_response)

            valid_domains = {"legal", "health", "emergency", "cross_domain"}
            domain = result.get("domain")
            if domain not in valid_domains:
                logger.warning(
                    "[SentinelAgent Monkeypatch] Normalizing invalid domain: %s",
                    domain
                )
                if not domain:
                    domain = "cross_domain"
                elif "|" in domain or "and" in domain or "cross" in domain:
                    domain = "cross_domain"
                elif "medical" in domain or "hospital" in domain:
                    domain = "health"
                else:
                    domain = "cross_domain"
                result["domain"] = domain

            return result

        SentinelAgent.run = custom_sentinel_run
