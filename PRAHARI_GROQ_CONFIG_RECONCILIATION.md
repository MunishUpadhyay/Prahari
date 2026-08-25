# Prahari — Groq Configuration Reconciliation Report

This report reconciles the differences between the model fallback descriptions in the Phase 1D and Phase 1G reports, based on the current state of the source code.

---

## 1. Exact Runtime Model List

The runtime model list in [`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py) (lines 59–63) defines:
```python
models_to_try = [
    self.model,             # Primary Agent Model (defaults to "llama-3.3-70b-versatile")
    "openai/gpt-oss-120b",  # Fallback 1
    "openai/gpt-oss-20b",   # Fallback 2
]
```

At runtime, `BaseAgent.call_groq()` tries the following models in this exact order:
1. **`llama-3.3-70b-versatile`** (Primary)
2. **`openai/gpt-oss-120b`** (Secondary)
3. **`openai/gpt-oss-20b`** (Tertiary)

---

## 2. Fallback Key & Model Rotation Order

The fallback loop utilizes both model escalation and key rotation:
1. **Model 1: `llama-3.3-70b-versatile`** is tried:
   - First with `api_keys[0]` (`GROQ_API_KEY`)
   - Next with `api_keys[1]` (`GROQ_API_KEY_2`)
2. **Model 2: `openai/gpt-oss-120b`** is tried (if Model 1 fails on all keys):
   - First with `api_keys[0]` (`GROQ_API_KEY`)
   - Next with `api_keys[1]` (`GROQ_API_KEY_2`)
3. **Model 3: `openai/gpt-oss-20b`** is tried (if Model 2 fails on all keys):
   - First with `api_keys[0]` (`GROQ_API_KEY`)
   - Next with `api_keys[1]` (`GROQ_API_KEY_2`)

---

## 3. Agent Overrides

An exhaustive scan of `apps/agents/agents.py` confirms that **no agent overrides the `model` attribute**. 
All agents (`SentinelAgent`, `TriageAgent`, `RightsAgent`, `CoordinationAgent`, and `LanguageAgent`) inherit `model = "llama-3.3-70b-versatile"` directly from `BaseAgent`.

---

## 4. All Groq Models Found in the Repository

| Model String | Location(s) | Role / Status |
| :--- | :--- | :--- |
| **`llama-3.3-70b-versatile`** | `apps/agents/base.py`, `tests/test_agents.py`, `README.md` | **Active** — Primary LLM model for all agents. |
| **`openai/gpt-oss-120b`** | `apps/agents/base.py`, `tests/test_agents.py`, `README.md` | **Active** — Secondary fallback model. |
| **`openai/gpt-oss-20b`** | `apps/agents/base.py`, `README.md` | **Active** — Tertiary fallback model. |
| **`llama-3.1-8b-instant`** | `README.md` | **Decommissioned** — Explicitly removed from the code fallback list (still referenced in documentation). |
| **`llama-3.1-70b-versatile`** | `PRAHARI_PHASE1G_FINAL_READINESS_REPORT.md` | **Not in code** — Erroneously referenced in Phase 1G report. |
| **`gemma2-9b-it`** | `PRAHARI_PHASE1G_FINAL_READINESS_REPORT.md` | **Not in code** — Erroneously referenced in Phase 1G report. |

---

## 5. Status of `llama-3.1-8b-instant`

- **Code Status**: Completely absent. There are no configuration parameters or python files referencing this model string.
- **Documentation Status**: Mentioned only in `README.md` and historical reports to explain why it was removed when decommissioned.

---

## 6. Discrepancy Reconciliation

- **The Phase 1G report was incorrect/stale** on line 109. The source code did NOT change.
- The model array in the Phase 1G report (`gemma2-9b-it`, `llama-3.1-70b-versatile`, `llama-3.1-8b-instant`) was mistakenly reported and does not exist in python source configuration files or tests. 
- The Phase 1D report correctly matches the runtime code: `llama-3.3-70b-versatile`, `openai/gpt-oss-120b`, and `openai/gpt-oss-20b`.

---

## 7. Decommissioning Status

Based on `README.md` and repository configuration:
- **`llama-3.1-8b-instant`** has been decommissioned by Groq and is removed from the active loop.
- **`llama-3.3-70b-versatile`** is currently active and is the primary model used by the application.
