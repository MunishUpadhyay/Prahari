"""
Base agent interface for Prahari.

All domain agents inherit from BaseAgent and must implement .run().
The base class handles:
    - Loading the system prompt from prompts/<prompt_name>.txt
    - Providing a hook for the Groq API call
    - Parsing and validating JSON responses
"""

import abc
import json
import logging
from pathlib import Path
from django.conf import settings
from typing import Optional, Any
from groq import Groq

logger = logging.getLogger(__name__)

# Absolute path to the prompts/ directory at project root
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


class BaseAgent(abc.ABC):
    """
    Abstract base class for all Prahari AI agents.

    Subclasses MUST set:
        prompt_name (str): Filename stem for the prompt in prompts/<name>.txt

    Subclasses MUST implement:
        run(signal) -> dict
    """

    prompt_name: str = ""
    model: str = "openai/gpt-oss-120b"
    max_tokens: int = 1024

    def load_prompt(self) -> str:
        """
        Load and return the system prompt from prompts/<prompt_name>.txt.
        Raises FileNotFoundError if the file does not exist.
        """
        if not self.prompt_name:
            raise ValueError(f"{self.__class__.__name__} must set `prompt_name`.")

        prompt_path = PROMPTS_DIR / f"{self.prompt_name}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file for agent '{self.prompt_name}' not found at: {prompt_path}"
            )

        return prompt_path.read_text(encoding="utf-8").strip()

    def call_groq(self, user_message: str, response_schema: Optional[Any] = None) -> str:
        system_prompt = self.load_prompt()
        
        # Model fallback candidates
        models_to_try = [
            self.model,             # openai/gpt-oss-120b
            "openai/gpt-oss-20b",   # fallback 1
        ]
        
        # Key fallback candidates
        api_keys = [k for k in [
            getattr(settings, "GROQ_API_KEY", ""),
            getattr(settings, "GROQ_API_KEY_2", ""),
        ] if k]
        
        if not api_keys:
            raise ValueError("No GROQ_API_KEY configured")
        
        last_exc = None
        
        for model in models_to_try:
            logger.info("[BaseAgent] Attempting LLM call with model=%s", model)
            
            for idx, api_key in enumerate(api_keys, 1):
                masked_key = api_key[:6] + "..." if len(api_key) > 6 else "..."
                logger.info("[BaseAgent] Using API key index %d (%s)", idx, masked_key)
                
                try:
                    client = Groq(api_key=api_key, max_retries=0)
                    kwargs = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        "temperature": 0.1,
                        "max_tokens": self.max_tokens,
                    }
                    if response_schema is not None:
                        schema_name = response_schema.__name__.lower()
                        schema_dict = response_schema.model_json_schema()
                        kwargs["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": schema_name,
                                "strict": True,
                                "schema": schema_dict
                            }
                        }
                    response = client.chat.completions.create(**kwargs)
                    choice = response.choices[0]
                    finish_reason = getattr(choice, "finish_reason", None)
                    logger.info(
                        "[BaseAgent] Groq response received for model %s. finish_reason: %s",
                        model, finish_reason
                    )
                    if model != self.model:
                        logger.warning(
                            "[BaseAgent] Fallback model %s succeeded on key index %d",
                            model, idx
                        )
                    return choice.message.content
                except Exception as exc:
                    last_exc = exc
                    status_code = getattr(exc, "status_code", None)
                    exc_str = str(exc).lower()
                    
                    # 1. Authentication / Authorization Failure (401/403)
                    is_auth_error = (
                        status_code in (401, 403)
                        or "401" in str(exc)
                        or "403" in str(exc)
                        or "unauthorized" in exc_str
                        or "forbidden" in exc_str
                        or "api key" in exc_str
                    )
                    if is_auth_error:
                        logger.error(
                            "[BaseAgent] Authentication failure on API Key index %d for model %s: %s",
                            idx, model, exc
                        )
                        # Try next key
                        continue
                    
                    # 2. Model decommissioned / unavailable
                    is_model_unavailable = (
                        status_code == 404
                        or "decommissioned" in exc_str
                        or "not found" in exc_str
                        or "unknown model" in exc_str
                    )
                    if is_model_unavailable:
                        logger.warning(
                            "[BaseAgent] Model %s is unavailable/decommissioned. Skipping to next model.",
                            model
                        )
                        # Skip this model immediately: break key loop to proceed to next model
                        break
                    
                    # 3. Rate Limit (429) or Server/Network errors (5xx/timeouts)
                    is_retryable = (
                        status_code == 429
                        or status_code >= 500
                        or "429" in str(exc)
                        or "rate_limit" in exc_str
                        or "too many requests" in exc_str
                        or "timeout" in exc_str
                        or "connection" in exc_str
                        or "500" in str(exc)
                        or "502" in str(exc)
                        or "503" in str(exc)
                        or "504" in str(exc)
                    )
                    if is_retryable:
                        logger.warning(
                            "[BaseAgent] Retryable failure (status=%s) with Key %d on model %s: %s",
                            status_code, idx, model, exc
                        )
                        # Try next key
                        continue
                    
                    # 4. Standard 400 Bad Request or Programming/Application Error
                    logger.error(
                        "[BaseAgent] Non-retryable error (status=%s) for model %s: %s. Aborting fallback.",
                        status_code, model, exc
                    )
                    raise exc
        
        raise last_exc or ValueError("All Groq keys and models exhausted")

    def parse_json_response(self, raw: str) -> dict:
        """
        Strips markdown code fences and parses JSON safely.
        Raises ValueError with clear message if parsing fails.
        """
        if not raw:
            raise ValueError("Empty response received from LLM.")

        cleaned = raw.strip()
        # Strip markdown json code fences (e.g. ```json ... ``` or ``` ... ```)
        if cleaned.startswith("```"):
            # Check for ```json or ```
            if cleaned.lower().startswith("```json"):
                cleaned = cleaned[7:]
            else:
                cleaned = cleaned[3:]
            
            # Strip ending ```
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()

        # Pre-process cleaned text to escape raw control characters inside string literals
        cleaned_for_json = []
        in_string = False
        escaped = False
        for char in cleaned:
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
        cleaned = "".join(cleaned_for_json)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse JSON response from LLM. Error: {e}. Raw content: {raw}"
            )

    @abc.abstractmethod
    def run(self, signal) -> dict:
        """
        Execute the agent against a Signal instance.

        Args:
            signal: apps.signals.models.Signal instance

        Returns:
            dict: Structured agent output.
        """
        raise NotImplementedError
