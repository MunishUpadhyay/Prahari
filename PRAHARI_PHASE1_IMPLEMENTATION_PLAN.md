# Prahari — Phase 1: Reliability, Correctness, and Security Implementation Plan

This document outlines the detailed technical implementation plan for Phase 1 of the Prahari upgrade roadmap. All modifications will utilize the existing infrastructure (Django 5, PostgreSQL/SQLite, Celery, Redis, and Groq API) and follow strict open-source practices.

---

## 1. Plan Overview & Objectives

* **Objective:** Elevate the reliability, correctness, and security of the Prahari platform.
* **Scope:** 
  1. Fix critical security leaks (endpoints with `AllowAny` permission).
  2. Implement a robust, unified Groq fallback architecture and remove all startup monkeypatches.
  3. Wire up Celery error handling (auto-fail signal status) and task retries.
  4. Activate the tamper-evident `AuditLog` on key incident state changes.
  5. Establish an automated test suite using pytest.
* **Constraints:** Must use existing infrastructure; no paid/third-party services. Do not modify any code files yet (this document is the blueprint).

---

## 2. Component Modifications

### A. Security: API Endpoint Protection
* **Target File:** [`apps/incidents/views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/views.py)
* **Function/Class:** `SimilarIncidentsView` and `LegalNoticeView`
* **Current Behavior:**
  * Both views specify `permission_classes = [AllowAny]`.
  * Anyone can access sensitive incident details (situation briefs, rights violations, metadata) without authenticating.
* **Desired Behavior:**
  * Update `permission_classes` to `[IsAuthenticated]`.
  * Restrict access to authenticated users presenting a valid JWT token.
* **Dependencies:** `rest_framework.permissions.IsAuthenticated`
* **Test Cases:**
  * `test_similar_incidents_unauthorized`: Verify GET requests without a JWT token receive an HTTP 401 Unauthorized response.
  * `test_legal_notice_unauthorized`: Verify GET requests without a JWT token receive an HTTP 401 Unauthorized response.
  * `test_authorized_access`: Verify GET requests with a valid JWT token receive an HTTP 200 OK response.
* **Risks:** The frontend coordinator dashboard must pass the JWT token in the Authorization header. (Verified: `coordinator_dashboard()` already generates and passes the JWT token as `jwt_token` context to `coordinator_dashboard.html`).

---

### B. AI/LLM: Unified Groq Fallback & Clean Architecture
* **Target File 1:** [`apps/agents/base.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/base.py)
  * **Function:** `BaseAgent.call_groq()`
  * **Current Behavior:**
    * Catches rate-limits using substring checks.
    * Bug: `"400" in str(exc)` is included in rate-limiting checks, causing HTTP 400 Bad Request to trigger fallbacks, which masks prompt engineering errors.
    * Lacks complete rate-limiting checks like `"too many requests"` and status code `429`.
  * **Desired Behavior:**
    * Remove `"400" in str(exc)` from the fallback trigger criteria.
    * Add `"too many requests"` and `getattr(getattr(exc, "response", None), "status_code", None) == 429` to target all rate-limiting error structures.
* **Target File 2:** [`apps/incidents/apps.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/apps.py)
  * **Function:** `IncidentsConfig.ready()`
  * **Current Behavior:** Replaces `BaseAgent.call_groq` at startup with a custom wrapper `fallback_call_groq` to run another rate limit check and retry loop.
  * **Desired Behavior:** Delete the `fallback_call_groq` definition and monkeypatch completely.
* **Target File 3:** [`apps/signals/apps.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/apps.py)
  * **Function:** `SignalsConfig.ready()`
  * **Current Behavior:** Monkeypatches `LanguageAgent.run` with a chunked translation implementation (`patched_language_agent_run`).
  * **Desired Behavior:** Delete the monkeypatch override completely.
* **Target File 4:** [`apps/agents/agents.py`](file:///d:/My%20Projects/Django/Prahari/apps/agents/agents.py)
  * **Function/Class:** `SentinelAgent.run()`
    * **Current Behavior:** Throws a `ValueError` if the LLM output is not `"legal"`, `"health"`, `"emergency"`, or `"cross_domain"`.
    * **Desired Behavior:** Inline the domain normalization logic directly (e.g., normalize "medical" or "hospital" to "health", default missing or complex matches to "cross_domain").
  * **Function/Class:** `LanguageAgent.run()`
    * **Current Behavior:** Executes a single translation call (which fails/truncates for large briefs).
    * **Desired Behavior:** Inline the 173-line chunked translation logic, regex replacements, and post-processing from `patched_language_agent_run` directly here.
* **Dependencies:** Groq SDK, standard Python `re` module.
* **Test Cases:**
  * `test_http_400_raises`: Verify an HTTP 400 Bad Request exception is raised immediately instead of triggering a model fallback.
  * `test_429_triggers_model_fallback`: Mock a 429 response on `llama-3.3-70b-versatile` and verify it transitions to `openai/gpt-oss-120b`.
  * `test_domain_normalization`: Verify `SentinelAgent` successfully normalizes "medical-aid" to "health" and empty values to "cross_domain".
* **Risks:** Deleting monkeypatches changes start-up behavior. We must ensure model imports are correct in `BaseAgent` and individual agents do not raise circular dependencies.

---

### C. Observability: Tamper-Evident AuditLog Wiring
* **Target File 1:** [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py)
  * **Functions:** `route_to_agents()` and `push_to_websocket()`
  * **Current Behavior:** No audit entries are generated during pipeline execution.
  * **Desired Behavior:**
    * In `route_to_agents()`, write an `AuditLog` entry with action `'incident_created'` when a new `Incident` object is generated.
    * In `push_to_websocket()`, write an `AuditLog` entry with action `'pipeline_completed'` when the processing pipeline finishes successfully.
* **Target File 2:** [`apps/incidents/coordinator_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/coordinator_views.py)
  * **Function:** `coordinator_resolve_incident()`
  * **Current Behavior:** Saves the incident model state as resolved without creating a corresponding audit record.
  * **Desired Behavior:** Write an `AuditLog` entry with action `'incident_resolved'`, listing the resolving user (from `request.user.username`) under `performed_by`.
* **Dependencies:** [`apps/audit/models.py`](file:///d:/My%20Projects/Django/Prahari/apps/audit/models.py)
* **Test Cases:**
  * `test_audit_log_creation`: Verify processing a signal successfully records both `'incident_created'` and `'pipeline_completed'` audit records.
  * `test_tamper_evident_hash`: Save an `AuditLog` entry, modify a field, and verify that the recomputed hash does not match the stored hash.
* **Risks:** `AuditLog` is a blocking write in Celery tasks and HTTP views. If the database save fails, the transaction will roll back. We must ensure the `AuditLog` write is safe.

---

### D. Distributed Systems: Celery Error Handling & Retries
* **Target File:** [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py)
* **Tasks:** `ingest_signal`, `classify_domain`, `route_to_agents`, `coordination_agent`, `push_to_websocket`
* **Current Behavior:**
  * If a task raises an exception, the task fails, but `Signal.status` remains stuck in `'processing'` or `'classified'` indefinitely.
  * `route_to_agents` and `coordination_agent` have retry configurations but do not execute them because `self.retry()` is never called in their exception blocks.
* **Desired Behavior:**
  * Add a custom Celery Task class (`PipelineTask`) overriding `on_failure`:
    ```python
    from celery import Task
    class PipelineTask(Task):
        def on_failure(self, exc, task_id, args, kwargs, einfo):
            # Extract signal_id or incident_id from args
            # Scope the database lookup, set signal.status = 'failed'
    ```
  * In tasks with retries, wrap the execution block in `try-except Exception as exc` and call `raise self.retry(exc=exc)`.
* **Dependencies:** Celery `shared_task` parameter routing.
* **Test Cases:**
  * `test_celery_task_failure_updates_status`: Mock a failure in `classify_domain` and verify the `Signal.status` transitions to `'failed'`.
  * `test_celery_retry_trigger`: Mock a rate-limit exception in `route_to_agents` and verify `self.retry` is invoked up to 3 times before raising `MaxRetriesExceededError`.
* **Risks:** `self.retry` raises a Celery `Retry` exception to schedule the next execution. We must ensure the task logic lets this exception propagate instead of intercepting it.

---

### E. Code Quality: Static Serializers
* **Target File 1:** [`apps/incidents/coordinator_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/coordinator_views.py)
  * **Lines to Remove:** Lines 11-13 where `IncidentListSerializer.Meta.fields` is dynamically altered.
* **Target File 2:** [`apps/incidents/serializers.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/serializers.py)
  * **Class:** `IncidentListSerializer`
  * **Desired Behavior:** Statically add `"agent_outputs"` to the `fields` array within `Meta`.
* **Test Cases:** Verify `/api/incidents/` includes `agent_outputs` in list payloads without mutating classes at runtime.

---

## 3. Implementation Order & Checklist

1. `[ ]` **Phase 1A: Security Endpoint Protection**
   * Update `SimilarIncidentsView` and `LegalNoticeView` permissions.
2. `[ ]` **Phase 1B: Clean Serializers & Remove Dynamic Patching**
   * Edit `serializers.py` and delete dynamic code mutations in `coordinator_views.py`.
3. `[ ]` **Phase 1C: Refactor Groq Client and Agents**
   * Update `base.py` error checks (remove HTTP 400 trigger).
   * Migrate chunked translation logic to `LanguageAgent` in `agents.py`.
   * Migrate domain normalization logic to `SentinelAgent` in `agents.py`.
   * Remove startup overrides in signals and incidents `apps.py`.
4. `[ ]` **Phase 1D: Wire Celery Task Retries & Failure Hooks**
   * Create `PipelineTask` class with `on_failure`.
   * Bind tasks and call `self.retry()` inside task exception blocks.
5. `[ ]` **Phase 1E: Wire AuditLog Writes**
   * Add log entries for incident creation, resolve actions, and pipeline completion.
6. `[ ]` **Phase 1F: Write Automated Test Suite**
   * Create unit and integration test suite under `tests/` directory.
