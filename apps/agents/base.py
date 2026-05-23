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
        """
        Initializes Groq client and sends system + user messages to the model.
        """
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured in Django settings.")

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.load_prompt()},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,  # low temperature for consistent classification
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content

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
