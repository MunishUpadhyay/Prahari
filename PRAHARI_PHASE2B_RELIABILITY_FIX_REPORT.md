# Phase 2B — RAG Reliability, Safety & Hallucination Fixes Report

This report outlines the technical changes, designs, and test verification results for Phase 2B.

---

## 1. Problems Addressed

We successfully implemented the following highest-priority reliability and safety fixes:
1. **Critical Evidence Checklist Bug**: Decoupled the eviction checklist from `"DLSA"` and `"Magistrate Court"`. It is now matched solely on context keywords.
2. **RAG Relevance Thresholds**: Introduced L2 distance thresholds for legal and medical collections, returning empty results instead of irrelevant documents.
3. **Authority Contact Hallucination Protection**: Created a static verified directory architecture and deterministic sanitizers that convert any unverified phone numbers or placeholders to `"Verified contact unavailable"`.
4. **Self-Harm Triage Safeguards**: Tuned the triage agent prompts to distinguish between general distress/anxiety and explicit self-harm intent/ideation.
5. **RAG Grounding**: Tuned agent prompts to treat retrieved text as reference material rather than facts about the citizen.
6. **Deterministic Emergency Priority**: Added a code-based reordering helper to prevent life-saving actions from being displaced by follow-ups.
7. **Coordination Data Integrity**: Enforced severity-preservation rules to prevent the LLM from silently downgrading critical severity scores.
8. **ChromaDB Telemetry Warning**: Disabled anonymized telemetry, resolving log warning noise.
9. **Phase 1 Report Cleanup**: Deleted 15 temporary phase report files.

---

## 2. Evidence Checklist Fix

- **Location**: `bringChecklist` Javascript function in [`templates/report_status.html`](file:///d:/My%20Projects/Django/Prahari/templates/report_status.html)
- **Change**: Replaced `isTenantDispute || auth === 'DLSA' || auth === 'Magistrate Court'` check with `isTenantDispute` only.
- **Result**: Eviction checklists are now strictly limited to actual landlord/tenant/rent/lease dispute reports. Emergency reports (such as mass shootings or medical injuries) will default to the general checklist rather than recommending rent agreements.

---

## 3. RAG Threshold Design

- **Location**: [`config/settings/base.py`](file:///d:/My%20Projects/Django/Prahari/config/settings/base.py) and [`rag/retriever.py`](file:///d:/My%20Projects/Django/Prahari/rag/retriever.py)
- **Threshold Selection**:
  - `RAG_LEGAL_DISTANCE_THRESHOLD = 1.1`
  - `RAG_MEDICAL_DISTANCE_THRESHOLD = 1.1`
- **Rationale**: ChromaDB uses squared L2 distance. Distances `< 0.8` signify high relevance, while `0.8 - 1.2` signify weak/moderate relevance. Setting the threshold at `1.1` allows relevant and marginally relevant documents to pass while discarding highly distant, unrelated noise (such as eviction laws matching shooting incidents, which typically score `> 1.3`).
- **Empty Retrieval Behavior**: If no results pass the threshold, the retriever returns `[]`. The agents format this explicitly as: *"No sufficiently relevant knowledge-base material was retrieved."*, preventing the LLM from fabricating context.

---

## 4. Domain Isolation

- **Isolation Status**: Already fully enforced at the vector database level. `retrieve_legal_provisions()` only queries the `legal_provisions` collection, and `retrieve_medical_protocols()` only queries the `medical_protocols` collection, guaranteeing that no legal provisions leak into medical queries.

---

## 5. Authority Contact Safety

- **Location**: [`apps/agents/directory.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/directory.py) and [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py)
- **Design**:
  - Maintained an empty `VERIFIED_DIRECTORY` structure representing verified contacts.
  - Implemented `sanitize_contact_number(number)` to filter out placeholder patterns (like `01234` or `1800-HOME-SEC`).
  - Allowed only known official helpline numbers (like `108`, `100`, `112`) to pass.
  - Overrode all other LLM-generated contacts to `"Verified contact unavailable"`.

---

## 6. Self-Harm Classification Safety

- **Location**: [`prompts/triage.txt`](file:///d:/My%20Projects/Django/Prahari/prompts/triage.txt)
- **Change**: Added explicit triage rules instructing the model to distinguish general anxiety, fear, crying, or shock from active self-harm intent/ideation. The model is forbidden from classifying self-harm risk solely based on general anxiety signals.

---

## 7. RAG Grounding Changes

- **Location**: [`prompts/triage.txt`](file:///d:/My%20Projects/Django/Prahari/prompts/triage.txt) and [`prompts/coordination.txt`](file:///d:/My%20Projects/Django/Prahari/prompts/coordination.txt)
- **Change**: Instructed the LLM that retrieved documents are reference material and may be irrelevant. The model must not assume that the generic protocol text applies to the user unless facts directly match.

---

## 8. Emergency Priority Protection

- **Location**: [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py#L363-L400)
- **Design**: Implemented `reorder_actions_by_safety()` in python. If the incident contains emergency keywords, the code scans the actions and shifts life-saving interventions (ambulance, hospital, CPR) to priorities 1 & 2, ensuring they are not displaced by administrative or legal actions.

---

## 9. Coordination Data Integrity

- **Location**: [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py#L529-L541)
- **Design**: Added checks to prevent CoordinationAgent from downgrading Sentinel's severity score. If the sentinel reports high severity (e.g. 0.9), the coordination synthesized score is protected and aligned with its corresponding label (e.g., "critical").

---

## 10. ChromaDB Telemetry Status

- **Status**: **Telemetry Disabled**.
- **Fix**: Initialized `PersistentClient` with `Settings(anonymized_telemetry=False)` in [`rag/retriever.py`](file:///d:/My%20Projects/Django/Prahari/rag/retriever.py) and [`rag/ingest.py`](file:///d:/My%20Projects/Django/Prahari/rag/ingest.py).
- **Result**: ChromaDB telemetry calls are bypassed, eliminating log warnings from our pipeline output completely.

---

## 11. Tests Added

We added 6 comprehensive test suites in [`tests/test_agents.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_agents.py):
1. `test_rag_threshold_filtering`: Confirms relevant results pass settings thresholds and irrelevant ones are rejected.
2. `test_rag_empty_retrieval_behavior`: Verifies empty context is explicitly passed to agents as a notification string.
3. `test_authority_contact_sanitization`: Validates sanitization of hallucinated numbers to `"Verified contact unavailable"` while preserving standard emergency lines.
4. `test_evidence_checklist_cases`: Verifies correct checklist selection for mass shooting (general) and tenant dispute (eviction).
5. `test_coordination_agent_emergency_priority`: Validates priority reordering logic for life-saving interventions.
6. `test_coordination_agent_severity_protection`: Confirms sentinel severity scores cannot be downgraded.

---

## 12. Full Test Results

- **Total Tests**: 39
- **Passed**: 39
- **Failed**: 0
- **Errors**: 0
- **Warnings**: 39 (Standard `DATABASES` settings override warnings)
- **Duration**: 11.15 seconds

---

## 13. Real Smoke Test Status

- **Status**: **Not performed during implementation.** (All validations were performed through automated mocked unit tests; no live Groq API calls were made).

---

## 14. Remaining Risks

- **Prompt Over-constraint**: Excessively strict self-harm instructions in prompts could cause the model to miss subtle or indirect expressions of self-harm intent if not worded clearly.
- **Dynamic Database Growth**: As `incident_history` grows, queries could return slightly higher base distances. This should be monitored as historical datasets scale.

---

## 15. Files Modified

1. [`config/settings/base.py`](file:///d:/My%20Projects/Django/Prahari/config/settings/base.py)
2. [`rag/retriever.py`](file:///d:/My%20Projects/Django/Prahari/rag/retriever.py)
3. [`rag/ingest.py`](file:///d:/My%20Projects/Django/Prahari/rag/ingest.py)
4. [`apps/agents/directory.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/directory.py) [NEW]
5. [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py)
6. [`prompts/triage.txt`](file:///d:/My%20Projects/Django/Prahari/prompts/triage.txt)
7. [`prompts/coordination.txt`](file:///d:/My%20Projects/Django/Prahari/prompts/coordination.txt)
8. [`templates/report_status.html`](file:///d:/My%20Projects/Django/Prahari/templates/report_status.html)
9. [`tests/test_agents.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_agents.py)
