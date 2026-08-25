# Phase 1H-B: GPT-OSS Triage Response Truncation Fix Report

This report documents the implementation and verification results for the immediate fix applied to resolve response truncation in the `TriageAgent`.

---

## 1. Problem

During the initial real-world smoke test of `openai/gpt-oss-120b`, the API successfully returned `200 OK`, but the pipeline failed with:
`ValueError: Failed to parse JSON response from LLM.`
The raw text was cut off mid-string:
`"consequence_of_delay": "Delayed psychological care increases risk of chronic PTSD, severe anxiety, depression, and possible self`

The cause was identified as response truncation because the agent's output exceeded the default `max_tokens=1024` limit of the `BaseAgent`.

---

## 2. Fix

We overrode the `max_tokens` configuration inside the `TriageAgent` class:
`max_tokens = 2000`

This matches the style used by `CoordinationAgent`, giving `TriageAgent` enough output headroom to complete its detailed structured JSON responses.

---

## 3. Why This Is Targeted

The global default inside `BaseAgent` (`max_tokens = 1024`) was **not changed**.
- **Efficiency**: Simpler agents (such as `SentinelAgent` or `LanguageAgent`) do not require detailed descriptive responses. Keeping their token limits low conserves API tokens and controls resource usage.
- **Isolation**: Increasing the limit only where needed (`TriageAgent` and `CoordinationAgent`) limits the surface area of potential changes and isolates the fix.

---

## 4. Tests

We updated `tests/test_agents.py` to add:
- `test_triage_agent_max_tokens_limit`: Verifies that `TriageAgent` has `max_tokens == 2000` and `prompt_name == "triage"`.

No existing tests were weakened.

---

## 5. Test Results

We ran the complete test suite:
- **Total**: 32
- **Passed**: 32
- **Failed**: 0
- **Errors**: 0
- **Skipped**: 0
- **Warnings**: 32 (All are known databases override warnings from test configuration)
- **Duration**: 4.19 seconds

---

## 6. Files Modified

1. **[`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py)**: Added `max_tokens = 2000` to `TriageAgent`.
2. **[`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py)**: Added `finish_reason` logging inside `BaseAgent.call_groq()`.
3. **[`tests/test_agents.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_agents.py)**: Added `test_triage_agent_max_tokens_limit` test case.
4. **[`PRAHARI_PHASE1H_GPTOSS_DIAGNOSTIC.md`](file:///d:/My%20Projects/Django/Prahari/PRAHARI_PHASE1H_GPTOSS_DIAGNOSTIC.md)**: Updated with the immediate fix section.

---

## 7. Real Smoke Test

"Not performed during this implementation phase." (Automated tests were executed in mock mode to prevent credentials exposure).

---

## 8. Remaining Reliability Improvement

Currently, Prahari relies on plain text system prompts requesting JSON formatting (Option C) followed by manual Python JSON decoding. To enforce correct JSON structure at the API gateway level, a subsequent phase should introduce Groq's native **Structured Outputs** (JSON mode or JSON Schema parameter) inside `BaseAgent.call_groq()`.
