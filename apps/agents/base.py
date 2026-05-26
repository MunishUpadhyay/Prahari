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

    def call_gemini(self, user_message: str, api_key: str) -> str:
        """
        Call the Gemini API via HTTP POST request.
        """
        import requests
        system_prompt = self.load_prompt()
        
        # Determine the Gemini model to use based on the Groq model name
        if "70b" in self.model.lower():
            gemini_model = "gemini-1.5-pro"
        else:
            gemini_model = "gemini-1.5-flash"
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": user_message}
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [
                    {"text": system_prompt}
                ]
            },
            "generationConfig": {
                "temperature": 0.1,
            }
        }
        
        # Force JSON formatting if requested
        if "json" in system_prompt.lower() or "json" in user_message.lower():
            payload["generationConfig"]["responseMimeType"] = "application/json"
            
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError(f"Gemini API returned no candidates. Response: {data}")
            
        candidate = candidates[0]
        if candidate.get("finishReason") == "SAFETY":
            raise ValueError("Gemini API call was blocked by safety settings.")
            
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise ValueError(f"Gemini API returned empty content parts. Response: {data}")
            
        return parts[0].get("text", "")

    def call_groq(self, user_message: str) -> str:
        """
        Send system + user messages to LLM.
        If settings.GEMINI_API_KEY is configured, routes to Gemini API.
        Otherwise, rotates across available Groq API keys on rate-limit (429) errors.

        Keys tried in order:
            1. settings.GEMINI_API_KEY (if configured)
            2. settings.GROQ_API_KEY
            3. settings.GROQ_API_KEY_2 (if configured)

        Raises:
            ValueError: if no API keys are configured.
            groq.RateLimitError / httpx.HTTPStatusError: if all keys are exhausted.
        """
        gemini_key = getattr(settings, "GEMINI_API_KEY", "")
        if gemini_key:
            try:
                logger.info("[BaseAgent] Routing to Gemini API.")
                return self.call_gemini(user_message, gemini_key)
            except Exception as exc:
                logger.warning("[BaseAgent] Gemini call failed: %s. Falling back to Groq rotation.", exc)

        # Build ordered list of non-empty keys
        api_keys = [
            k for k in [
                getattr(settings, "GROQ_API_KEY", ""),
                getattr(settings, "GROQ_API_KEY_2", ""),
            ]
            if k
        ]
        if not api_keys:
            raise ValueError("No GROQ_API_KEY or GEMINI_API_KEY is configured in Django settings.")

        system_prompt = self.load_prompt()
        last_exc = None

        for idx, api_key in enumerate(api_keys, start=1):
            try:
                client = Groq(api_key=api_key)
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_message},
                    ],
                    temperature=0.1,
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content

            except Exception as exc:
                # Detect rate-limit errors from groq SDK or httpx
                is_rate_limit = (
                    "429" in str(exc)
                    or "rate_limit" in str(exc).lower()
                    or "too many requests" in str(exc).lower()
                    or getattr(getattr(exc, "response", None), "status_code", None) == 429
                )
                if is_rate_limit and idx < len(api_keys):
                    logger.warning(
                        "[BaseAgent] Key %d hit rate limit (429) — switching to key %d.",
                        idx, idx + 1
                    )
                    last_exc = exc
                    continue
                raise  # non-429 error or last key exhausted

        raise last_exc  # all keys rate-limited

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
