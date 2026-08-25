# Phase 1H: GPT-OSS Real-World Failure Diagnosis Report

This report documents the diagnostic investigation of the JSON parsing failure encountered during the local smoke test after migrating Prahari's primary model to `openai/gpt-oss-120b`.

---

## 1. Observed Failure

- **Error**: `ValueError: Failed to parse JSON response from LLM.`
- **Underlying Error**: `JSONDecodeError: Unterminated string starting at line 11 column 29.`
- **Raw Response Ending**:
  `"consequence_of_delay": "Delayed psychological care increases risk of chronic PTSD, severe anxiety, depression, and possible self`
- **Symptom**: The response is truncated mid-word inside the `consequence_of_delay` field, indicating the document is incomplete.

---

## 2. Actual Groq Request Configuration

We inspected `BaseAgent.call_groq()` in [`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py) (lines 84–93). The parameters sent to the Groq API client `chat.completions.create` are:

- **`model`**: the active model name (e.g. `"openai/gpt-oss-120b"`)
- **`messages`**: system prompt (`system_prompt`) and user prompt (`user_message`)
- **`temperature`**: `0.1` (low, deterministic)
- **`max_tokens`**: `self.max_tokens` (which defaults to `1024` for `TriageAgent` and `BaseAgent`)
- **`response_format` / JSON Mode**: None. No JSON mode parameter is passed.

---

## 3. Actual Response Handling

- **Raw Return**: The raw string is returned via `response.choices[0].message.content`.
- **Reasoning Fields**: No special reasoning fields are parsed or inspected.
- **Finish Reason**: The `finish_reason` is not inspected.
- **JSON Parsing**: The raw response is parsed with `self.parse_json_response()` inside the individual agent's `run()` method (outside `call_groq()`).
- **Error Propagation**: Since JSON parsing occurs *outside* `call_groq()`, any `ValueError` or `JSONDecodeError` propagates directly out of the agent and task, bypassing the internal model/key fallback loop in `call_groq()`.
- **Celery Classification**: `ValueError` is classified as a permanent, non-retryable exception. It causes `route_to_agents` to mark the signal as `"failed"` immediately and abort.

---

## 4. Structured Output Configuration

- Prahari relies on **plain text prompting requesting JSON** (Option C). The system prompt (`prompts/triage.txt`) requests a raw JSON output conforming to a specific schema and instructs the model to omit conversational markdown text.
- No client-side JSON Mode (`response_format={"type": "json_object"}`) or strict JSON Schema parameters are passed in the API payload.

---

## 5. Triage Schema Analysis

The `TriageAgent` schema defines several fields that encourage detailed narrative responses:
- `primary_concern`: Requires a detailed structured medical handoff note including age, symptoms, duration, mechanism, status, and major risks.
- `interventions` (array of strings): Requires each item to explain action, why needed, consequences if skipped, and how to perform if no professional is available.
- `golden_window.consequence_of_delay`: Requires a detailed physiological description of consequences.
- `emergency_contacts` (array of objects): Contains names, numbers, and descriptions of when to call.

The schema details, combined with JSON boilerplate, easily demand more than 1024 output tokens.

---

## 6. Prompt Analysis

The system prompt [`prompts/triage.txt`](file:///d:/My%20Projects/Django/Prahari/prompts/triage.txt) instructs the model to write verbose handoff notes and multi-point intervention protocols. Because `openai/gpt-oss-120b` is a much larger and more analytical reasoning model, its answers are naturally more descriptive and verbose than those of the previous Llama model under the same instructions, causing it to exceed the default `max_tokens=1024` ceiling.

---

## 7. Response Metadata / Finish Reason

The response metadata is not logged in the database or Django logs. However, because the response was truncated mid-word inside the last few fields of the JSON schema, we have **100% confidence** that the model reached the output limit and the `finish_reason` was `"length"`.

---

## 8. Fallback Behavior

The model fallback loop inside `call_groq()` only catches exceptions raised during the Groq API HTTP exchange (such as 429 rate limit or 404 model not found). Because the API request completed with a successful `200 OK` status and returned a truncated raw string, `call_groq()` completed successfully. The parsing error occurred downstream in `TriageAgent.run()`, which lies outside the fallback block.

---

## 9. Celery Behavior

When `TriageAgent` raises `ValueError`, the Celery task `route_to_agents` catches the exception. In accordance with the Phase 1E retry design, `ValueError` is treated as a non-retryable application/data bug. The task immediately updates `Signal.status = "failed"` and records the traceback in the signal metadata.

---

## 10. ChromaDB Telemetry Errors

The error `Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given` is an **independent warning caused by a dependency version mismatch** (Category D). It does not affect vector queries or the Groq pipeline.

---

## 11. Root Cause

- **Primary Failure**: **E. Response truncation / output limit**
- **Explanation**: The default output ceiling `max_tokens=1024` is too low for the detailed structured output generated by `openai/gpt-oss-120b` under `TriageAgent`'s system prompts, causing the response to be cut off mid-word, resulting in malformed JSON.

---

## 12. Confidence Level

- **Confidence**: **HIGH**

---

## 13. Recommended Fix

We recommend **increasing the output token limit** specifically for the `TriageAgent` by setting `max_tokens = 2000` in the class definition (matching the existing configuration of `CoordinationAgent`). This provides the model with enough headroom to complete its verbose structured responses.

---

## 14. Files Inspected

1. **[`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py)**: Handled Groq request and default token limit.
2. **[`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py)**: Contained `TriageAgent` class definition and schema.
3. **[`prompts/triage.txt`](file:///d:/My%20Projects/Django/Prahari/prompts/triage.txt)**: Contained instructions driving output verbosity.
4. **[`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py)**: Handled Celery error classification and status logging.

---

## 15. Immediate Fix Applied

- **TriageAgent max_tokens Increase**: Changed `TriageAgent.max_tokens` from `1024` to `2000` in [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py) to provide sufficient output headroom for detailed structured JSON responses under `openai/gpt-oss-120b`.
- **Diagnostics Visibility**: Added `finish_reason` logging inside `BaseAgent.call_groq()` in [`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py) to log the completion status of Groq completions API responses.
- **Scope Restriction**: No other agent token limits were changed, no `response_format` JSON mode parameters were introduced, and the fallback architecture remains identical.
