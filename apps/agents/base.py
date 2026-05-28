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
    model: str = "llama-3.3-70b-versatile"
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

    def call_groq(self, user_message: str) -> str:
        system_prompt = self.load_prompt()
        
        # Model fallback order
        models_to_try = [
            self.model,  # llama-3.3-70b-versatile
            "llama-3.1-70b-versatile",  # fallback 1
            "llama-3.1-8b-instant",     # fallback 2
        ]
        
        # Key fallback order
        api_keys = [k for k in [
            getattr(settings, "GROQ_API_KEY", ""),
            getattr(settings, "GROQ_API_KEY_2", ""),
        ] if k]
        
        if not api_keys:
            raise ValueError("No GROQ_API_KEY configured")
        
        last_exc = None
        
        # Try each key, then fall back to smaller model
        for model in models_to_try:
            for idx, api_key in enumerate(api_keys, 1):
                try:
                    client = Groq(api_key=api_key, max_retries=0)
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system",
                             "content": system_prompt},
                            {"role": "user",
                             "content": user_message},
                        ],
                        temperature=0.1,
                        max_tokens=self.max_tokens,
                    )
                    if model != self.model:
                        logger.warning(
                            "[BaseAgent] Using fallback"
                            " model: %s", model)
                    return response.choices[0].message.content
                except Exception as exc:
                    is_rate_limit = (
                        "429" in str(exc) or
                        "rate_limit" in str(exc).lower() or
                        "400" in str(exc) or
                        "decommissioned" in str(exc).lower()
                    )
                    if is_rate_limit:
                        logger.warning(
                            "[BaseAgent] Key %d rate"
                            " limited or decommissioned on model %s",
                            idx, model)
                        last_exc = exc
                        continue
                    raise
        
        raise last_exc or ValueError(
            "All Groq keys and models exhausted")

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
