# Prahari — Phase 1D Groq / LLM Reliability Report

This document reports the implementation details and verification results for Phase 1D: Groq / LLM Reliability.

---

## 1. Previous Architecture

The old architecture suffered from triple-nested retry/fallback layers:
1. **Layer 1 (Native `BaseAgent.call_groq`):** Had a model fallback loop (`models_to_try`) and key rotation loop (`api_keys`). Exception handling classified HTTP 400 Bad Requests as rate limits (`"400" in str(exc)`), causing useless retries.
2. **Layer 2 (Monkeypatch `fallback_call_groq` in `apps/incidents/apps.py`):** Intercepted failures, mutated the model state (`self.model = "openai/gpt-oss-120b"`), and ran `original_call_groq` again, repeating Layer 1 attempts.
3. **Layer 3 (Hidden `sitecustomize.py` in local `.venv`):** Intercepted all `BaseAgent.call_groq` calls, executed 10 attempts, slept for 7 seconds on 429 rate limit exceptions, causing further duplicates and test leaks.

Additionally, `LanguageAgent`'s chunked translation logic was monkeypatched in `apps/signals/apps.py` on startup (`patched_language_agent_run`).

---

## 2. Problems Found

* **Duplicate Retries:** Under rate-limiting, the agent could make up to 60 retries (`10 * 3 models * 2 keys`), wasting time and hiding real provider issues.
* **400 Bad Request Handling:** Handled as a rate limit, triggering model rotation when the parameters or prompt structure was simply wrong.
* **Hidden Local File (`sitecustomize.py`):** Contaminated the testing runtime by intercepting calls globally, causing mock exhaustion tests to fail.
* **Thread Safety Issues:** Mutating `self.model` inside fallback loops could leak state between concurrent requests.

---

## 3. New Architecture

We removed all duplicate wraps and nested retry loops, establishing a single, unified, thread-safe, and testable LLM fallback path:
* **authoritative Abstraction:** Refactored `BaseAgent.call_groq` inside [`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py) as the single fallback executor.
* **No State Mutation:** Configured model fallback to run over local variables without mutating `self.model`.
* **Cleaned Up Monkeypatches:** Deleted `fallback_call_groq` from [`apps/incidents/apps.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/apps.py) and removed the hidden [`sitecustomize.py`](file:///D:/My%20Projects/Django/Prahari/.venv/lib/site-packages/sitecustomize.py) from the local environment.

---

## 4. Error Policy

| Error Category | Example Exception | Behavior |
|---|---|---|
| **Rate Limit** | HTTP 429 | Rotate keys, then models. Maximum 6 attempts. |
| **Model Unavailable** | HTTP 404, "unknown model" | Immediately skip to next model (skip key rotation for this model). |
| **Bad Request** | HTTP 400 | Fail immediately. Do **not** rotate keys or models. |
| **Authentication** | HTTP 401, 403 | Rotate to next key. If both keys fail, raise exception immediately. |
| **Server/Network** | HTTP 5xx, timeouts | Treat as retryable (rotate keys and models). |
| **Programming Error** | ValueError, json decode error | Fail immediately. Do **not** retry. |

---

## 5. Model / Key Strategy

* **Model Order:** `[self.model (llama-3.3-70b-versatile), "openai/gpt-oss-120b", "openai/gpt-oss-20b"]`
* **Key Scopes:** `[settings.GROQ_API_KEY, settings.GROQ_API_KEY_2]`
* **Maximum Attempts:** 6 total attempts (3 models * 2 keys).

---

## 6. LanguageAgent Changes

We relocated the chunked translation and regex post-processing directly into `LanguageAgent` in [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py) as clean private helper methods:
* `_translate_payload(payload, target_language)`: Translates JSON blocks.
* `_force_hindi_translation(val)`: Regex-maps English terms to Hindi.
* `_post_process_translate(obj, target_language)`: Recursively walks JSON values.
We removed `patched_language_agent_run` and its startup hook from [`apps/signals/apps.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/apps.py).

---

## 7. Tests

We updated and added extensive test cases inside [`tests/test_agents.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_agents.py):
1. `test_call_groq_success`: Succeeds on primary model.
2. `test_call_groq_rate_limit_key_rotation`: Key 1 rate limit (429) triggers Key 2.
3. `test_call_groq_model_decommissioned_skips_keys`: Model unavailable (404) skips Key 2 and switches to next model.
4. `test_call_groq_400_bad_request_aborts`: 400 Bad Request aborts immediately without fallback.
5. `test_call_groq_auth_failure_key_rotation`: Key 1 auth failure (401) rotates to Key 2.
6. `test_call_groq_all_exhausted_raises`: 6 consecutive rate limits exhaust attempts and raise exception.
7. `test_language_agent_translation_logic`: Verifies chunking payload translations and Hindi term overrides.

---

## 8. Test Results

* **Total Tests Run:** 19
* **Passed:** 19
* **Failed:** 0
* **Skipped:** 0
* **Errors:** 0
* **Duration:** 4.34 seconds

All tests pass successfully.

---

## 9. Security

* **No keys exposed:** Logging masks API keys (`api_key[:6] + "..."`).
* **No real Groq API calls** executed during tests (fully mocked clients).
* **No production databases** accessed.

---

## 10. Files Changed

* `apps/agents/base.py` (Modified)
* `apps/agents/agents.py` (Modified)
* `apps/incidents/apps.py` (Modified)
* `apps/signals/apps.py` (Modified)
* `tests/test_agents.py` (Modified)
* `D:\My Projects\Django\Prahari\.venv\lib\site-packages\sitecustomize.py` (DELETED)

---

## 11. Remaining Concerns

None. The LLM integration is now clean, isolated, and robust.
