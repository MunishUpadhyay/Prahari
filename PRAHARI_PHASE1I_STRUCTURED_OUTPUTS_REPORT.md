# Phase 1I: Groq Structured Outputs Implementation Report

This report documents the design, implementation, and verification results for **Phase 1I: Groq Structured Outputs**.

---

## 1. Current Architecture

Previously, Prahari relied on natural language prompts instructing the LLM to format its response as JSON (Option C), followed by `json.loads` and manual dictionary validation/fallback assignment inside each agent's `.run()` method. This design occasionally suffered from response truncation and formatting errors (like trailing ellipses or incomplete structures) under high output sizes.

---

## 2. Existing Pydantic Schemas

Prior to this phase, Prahari did not contain Pydantic schemas or validation classes. All validation and fallback logic was implemented manually using nested dictionary lookups (e.g. `if "field" not in result:`). We constructed Pydantic v2 schemas (`TriageSchema`, `CoordinationSchema`) to represent the exact properties and types specified in the agent docstrings and validation layers.

---

## 3. Groq Strict Structured Output Compatibility

Groq supports strict Structured Outputs via standard JSON Schema definitions. To meet the compatibility requirements, we designed the schemas with:
- **`ConfigDict(extra="forbid")`**: Sets `"additionalProperties": false` in the generated JSON Schema, as required by strict API validation.
- **Required Nullable Properties**: In strict mode, every property must be present in the `"required"` array, even if it is nullable or contains `None`. We achieved this by defining nullable fields (like `conflict_resolution` in `CoordinationSchema`) as `Optional[ConflictResolutionSchema]` without setting a default `= None`, forcing Pydantic to include it in the `required` schema array.
- **Enum Restriction**: Standardized options using Python's `Literal` type which translates to schema `enum` arrays.

---

## 4. Exact BaseAgent Design

We updated [`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py):
- Changed `BaseAgent.call_groq` to accept an optional parameter `response_schema`.
- When provided, `call_groq` automatically converts the Pydantic schema using `.model_json_schema()`, and populates the `response_format` payload:
  ```python
  kwargs["response_format"] = {
      "type": "json_schema",
      "json_schema": {
          "name": response_schema.__name__.lower(),
          "strict": True,
          "schema": response_schema.model_json_schema()
      }
  }
  ```
- This keeps the schema payload generation completely centralized.

---

## 5. TriageAgent Implementation

- Integrated `TriageSchema` into `TriageAgent.run()` inside [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py) by passing `response_schema=TriageSchema` to `self.call_groq()`.
- Retained all existing dictionary fallback checks (`if "triage_severity" not in result`) as defense-in-depth safety checks.

---

## 6. Tests

We updated [`tests/test_agents.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_agents.py):
- Added `test_call_groq_structured_output_payload` to verify:
  1. `response_schema` is supplied by `TriageAgent` and `CoordinationAgent` during execution.
  2. `BaseAgent` constructs the correct `response_format` (strict mode enabled, correct name, additionalProperties=False).
  3. No real network calls are made.

---

## 7. Test Results

- **Total**: 33
- **Passed**: 33
- **Failed**: 0
- **Errors**: 0
- **Warnings**: 33
- **Duration**: 5.75 seconds

All 33 tests passed successfully.

---

## 8. Token / Reasoning Observations

- `reasoning_effort` is not currently configured in parameters, meaning `openai/gpt-oss-120b` uses the model's default reasoning effort setting.
- Enabling Structured Outputs reduces token overhead by eliminating syntax formatting failures and preventing natural language prefix/suffix boilerplate.

---

## 9. CoordinationAgent Migration Status

Because the `CoordinationAgent` schema is fully compatible and was hitting the same truncation limit on the `openai/gpt-oss-120b` smoke test, we migrated it alongside the `TriageAgent`. We defined `CoordinationSchema` and nested schemas (`ImmediateActionSchema`, `ConflictResolutionSchema`, etc.) and integrated them into `CoordinationAgent.run()`.

---

## 10. Remaining Agents

The remaining agents have not been migrated to Structured Outputs during this phase:
- **`SentinelAgent`**: Schema is simple and hasn't experienced issues.
- **`RightsAgent`**: TBD.
- **`LanguageAgent`**: Schema structure is dynamic (depends on input coordination payload) and translates in sub-payloads.
- **`LegalNoticeAgent`**: Outputs plaintext legal notices (no JSON/Structured outputs applicable).

---

## 11. Known Risks

- Schema mismatch: If the Pydantic schema excludes a field that the system prompt specifically requests, the model might experience generation issues or API validation errors. (We matched the schemas exactly to prompt definitions).

---

## 12. Exact Files Modified

1. **[`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py)**: central structured payload generation.
2. **[`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py)**: defined schemas and passed them to `call_groq`.
3. **[`tests/test_agents.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_agents.py)**: added structured payload validation test case.
