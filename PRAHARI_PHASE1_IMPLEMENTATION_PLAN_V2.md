# Prahari — Phase 1: Reliability, Correctness, and Security Implementation Plan (Revised V2)

This document presents a revised plan for Phase 1 focusing on establishing a test suite first, cleaning up architecture monkeypatches, securing API views, fixing Groq rate-limiting fallbacks, and handling Celery/AuditLog failure paths gracefully.

---

## 1. Core Constraints & Preservation of Strengths

### Core Constraints
* **₹0 / Free Solutions Only:** All implementations rely on existing open-source libraries, local CPU models (`all-MiniLM-L6-v2`), and developer-gated APIs.
* **No Database Migrations:** Do not migrate PostgreSQL away from the current Supabase-hosted setup.
* **No PostGIS in Phase 1:** Keep the fallback settings that remove `"django.contrib.gis"` from `INSTALLED_APPS` active during local development and native Render test runs.
* **No New Frameworks:** Avoid introducing LangChain, LangGraph, MCP, or Kubernetes. Focus on Django, Celery, Redis, and ChromaDB.
* **Preserve Working Code:** Do not refactor functional layouts without a documented reliability, correctness, or security reason.

### Preservation of Existing Strengths
* **BaseAgent Architecture:** Keep the abstract base class and prompting framework intact. Avoid wrapper classes.
* **Celery + Redis Structure:** Retain the solo concurrency model and broker setups.
* **Externalized Prompts:** Keep prompts inside `.txt` files rather than inlining them.
* **Structured Output Validation:** Preserve per-agent JSON field check loops.

---

## 2. Implementation Sequence

The implementation is structured sequentially, moving from safety net creation to view security, code cleanup, LLM fallbacks, distributed system reliability, audit logging, and final validation.

```text
Step 1: Phase 1A (Test Foundation)
         ↓
Step 2: Phase 1B (Security Views)
         ↓
Step 3: Phase 1C (Serializer Cleanup)
         ↓
Step 4: Phase 1D (Groq & LLM Reliability)
         ↓
Step 5: Phase 1E (Celery Task Reliability)
         ↓
Step 6: Phase 1F (AuditLog Activation)
         ↓
Step 7: Phase 1G (Regression & Smoke Verification)
```

---

## 3. Phase Details

### Phase 1A: Test Foundation

#### Objective
Establish a baseline test suite containing unit, API, Celery, RAG, and E2E integration tests to act as a safety net before any modification of production code.

#### Current Behavior
Testing dependencies (`pytest`, `pytest-django`, `pytest-asyncio`, `factory-boy`, `coverage`) are listed in `requirements.txt`, but there are no automated test files in the project.

#### Desired Behavior
An active test suite running on a local SQLite database that validates core agent behaviors, API views, task retry/failure paths, RAG retrieves, and E2E processing chains without executing real paid API calls.

#### Files Affected
* `d:\My Projects\Django\Prahari\pytest.ini` (NEW)
* `d:\My Projects\Django\Prahari	ests/` (NEW directory)
* `d:\My Projects\Django\Prahari	ests/conftest.py` (NEW)
* `d:\My Projects\Django\Prahari	ests/test_agents.py` (NEW)
* `d:\My Projects\Django\Prahari	ests/test_api.py` (NEW)
* `d:\My Projects\Django\Prahari	ests/test_celery.py` (NEW)
* `d:\My Projects\Django\Prahari	ests/test_rag.py` (NEW)
* `d:\My Projects\Django\Prahari	ests/test_integration.py` (NEW)

#### Functions/Classes Affected
N/A (New test infrastructure setup only).

#### Implementation Approach
1. **pytest configuration:** Create `pytest.ini` setting `DJANGO_SETTINGS_MODULE = config.settings.dev`.
2. **pytest-django behavior:** Utilize `@pytest.mark.django_db` for database queries. Use local SQLite memory DB configured dynamically to bypass GDAL checks.
3. **Mocking structure:** Configure mock objects for the `groq.Groq` client response in `conftest.py` to yield deterministic mock outputs without hitting the internet.
4. **End-to-End mock pipeline:** Write a single high-value E2E test that mocks LLM responses and maps the flow: Ingest Signal → classify domain → dispatch agents → create Incident → create AuditLog → set status.

#### Tests to Create
* `test_base_agent_json_parsing`: Verify markdown stripping and control char handling in `BaseAgent.parse_json_response`.
* `test_api_auth_views`: Test endpoint responses for unauthenticated vs. authenticated requests (mocking simplejwt validation).
* `test_rag_retriever`: Mock ChromaDB client queries to return empty or mock provisions and test context building.
* `test_celery_pipeline_e2e`: Test Celery pipeline run using `celery_app` test workers with mocked model returns.

#### Risks
If test configurations require GDAL to validate migrations, pytest will fail. (Mitigation: Use `dev_nogis.py` settings module which excludes `"django.contrib.gis"` from `INSTALLED_APPS` and runs safely on standard SQLite databases).

#### Rollback Strategy
Delete the `tests/` directory and `pytest.ini` configuration.

#### Verification
Execute `pytest` in terminal; expect green baseline runs.

#### Cost
₹0 (Uses local SQLite database and mock client objects).

---

### Phase 1B: Security

#### Objective
Prevent sensitive incident data and legal notices from being publicly exposed by enforcing authentication on API views.

#### Current Behavior
`SimilarIncidentsView` and `LegalNoticeView` in [apps/incidents/views.py](file:///d:/My%20Projects/Django/Prahari/apps/incidents/views.py#L92) declare `permission_classes = [AllowAny]`, allowing unauthenticated requests to read situation briefs and rights details.

#### Desired Behavior
Both views enforce `permission_classes = [IsAuthenticated]`. Anonymous requests receive `HTTP 401 Unauthorized`. Valid JWT access tokens allow full responses. (Authorization limits scoped to tenant boundaries will be handled separately in Phase 2).

#### Files Affected
* `d:\My Projects\Django\Praharipps\incidentsiews.py`

#### Functions/Classes Affected
* `SimilarIncidentsView`
* `LegalNoticeView`

#### Implementation Approach
Import `IsAuthenticated` from `rest_framework.permissions` and assign `permission_classes = [IsAuthenticated]` to both view declarations.

#### Tests
* `test_anonymous_denied_similar`: GET `/api/incidents/<id>/similar/` returns 401.
* `test_anonymous_denied_notice`: GET `/api/incidents/<id>/legal-notice/` returns 401.
* `test_authenticated_allowed_similar`: GET with valid token returns 200.

#### Risks
The coordinator frontend HTML page may crash when querying these views if the JWT token is not passed in the request header. (Mitigation: Dashboard template context already handles access token generation; verify dashboard JavaScript attaches the header).

#### Rollback Strategy
Revert permission settings to `[AllowAny]`.

#### Verification
Execute pytest against security test cases.

#### Cost
₹0.

---

### Phase 1C: Serializer / Runtime Mutation Cleanup

#### Objective
Clean up the dynamic class modification in coordinator views to adhere to standard static serializer definitions.

#### Current Behavior
[apps/incidents/coordinator_views.py](file:///d:/My%20Projects/Django/Prahari/apps/incidents/coordinator_views.py#L11-L13) mutates the `IncidentListSerializer.Meta.fields` variable at startup. This runtime class mutation is fragile and can impact test isolation.

#### Desired Behavior
Statically define `"agent_outputs"` inside the serializer's `Meta` fields in [serializers.py](file:///d:/My%20Projects/Django/Prahari/apps/incidents/serializers.py#L11) and remove the startup patch.

#### Files Affected
* `d:\My Projects\Django\Praharipps\incidents\serializers.py`
* `d:\My Projects\Django\Praharipps\incidents\coordinator_views.py`

#### Functions/Classes Affected
* `IncidentListSerializer`

#### Implementation Approach
1. Add `"agent_outputs"` to `IncidentListSerializer.Meta.fields` array.
2. Delete lines 11-13 in `coordinator_views.py` that perform the startup modification.

#### Tests
* `test_serializer_fields`: Verify `IncidentListSerializer(instance).data` contains `agent_outputs` without running any runtime patches.

#### Risks
Very low risk.

#### Rollback Strategy
Restore original files from git.

#### Verification
Ensure the dashboard continues to display agent details correctly during manual review.

#### Cost
₹0.

---

### Phase 1D: Groq / LLM Reliability

#### Objective
Eliminate redundant startup monkeypatches, fix the HTTP 400 fallback bug, and organize fallback/translation behaviors cleanly.

#### Current Behavior
* `BaseAgent.call_groq()` includes `"400" in str(exc)` under rate limits, causing Bad Requests to trigger retries.
* `incidents/apps.py` wraps `BaseAgent` with a second fallback method `fallback_call_groq`, causing duplicate retry attempts.
* `signals/apps.py` replaces `LanguageAgent.run` at startup, leaving dead code in `agents.py`.

#### Desired Behavior
Provide one clean, unified fallback loop inside `BaseAgent.call_groq()` and remove startup monkeypatches. Structure agents with clear internal helper methods.

#### Files Affected
* `d:\My Projects\Django\Praharippsgentsase.py`
* `d:\My Projects\Django\Praharippsgentsgents.py`
* `d:\My Projects\Django\Praharipps\incidentspps.py`
* `d:\My Projects\Django\Praharipps\signalspps.py`

#### Functions/Classes Affected
* `BaseAgent.call_groq()`
* `SentinelAgent.run()`
* `LanguageAgent.run()`
* `IncidentsConfig.ready()`
* `SignalsConfig.ready()`

#### Implementation Approach
1. **Unify Fallback (`base.py`):**
   * Remove `"400" in str(exc)` from `is_rate_limit`.
   * Add specific checks: `429` status code, `"too many requests"`.
   * Define model escalation: `self.model` → `openai/gpt-oss-120b` → `openai/gpt-oss-20b`.
   * Sequential key rotation: Attempt key 1, then key 2 for each model.
2. **De-monkeypatch app configs:**
   * Delete custom ready patches in `incidents/apps.py` and `signals/apps.py`.
3. **Structured Agent Refactoring (`agents.py`):**
   * Move domain normalization to `SentinelAgent._normalize_domain(domain)`.
   * Cleanly structure `LanguageAgent.run()` by decomposing chunked translation into helper methods:
     * `_translate_payload()`
     * `_force_hindi_translation()`
     * `_post_process_translate()`

#### Tests
* `test_http_400_raises_immediately`: Mock a 400 Bad Request error and verify it raises without retrying.
* `test_model_key_fallback_escalation`: Mock 429 errors on primary keys/models and verify the loop progresses from `llama-3.3-70b-versatile` keys to `openai/gpt-oss-120b` keys.
* `test_sentinel_domain_normalization`: Verify malformed domain strings are mapped to valid domains.

#### Risks
Deprecated models like `llama-3.3-70b-versatile` could be disabled. (Mitigation: The fallback chain is robust enough to transition to active `openai/gpt-oss` models automatically if a decommissioning error is intercepted).

#### Rollback Strategy
Restore `base.py`, `agents.py`, and `apps.py` files to their previous states.

#### Verification
Execute targeted LLM fallback tests.

#### Cost
₹0.

---

### Phase 1E: Celery Task Reliability

#### Objective
Ensure Celery worker failures or rate-limiting exceptions do not leave signals stuck in intermediate statuses, and properly invoke task retries.

#### Current Behavior
* Unhandled pipeline task errors leave signals in `'processing'` or `'classified'` status forever.
* Tasks have `@shared_task(max_retries=3)` but never call `self.retry()`, failing silently on the first exception.

#### Desired Behavior
* Implement a custom base task class (`PipelineTask`) whose `on_failure` callback catches unhandled task failures and updates the related `Signal.status` to `'failed'`.
* Wrap retryable operations in try-except blocks and invoke `raise self.retry(exc=exc)`.

#### Files Affected
* `d:\My Projects\Django\Prahari\pipeline	asks.py`

#### Functions/Classes Affected
* `PipelineTask` (NEW Task subclass)
* `ingest_signal`, `classify_domain`, `route_to_agents`, `coordination_agent`, `push_to_websocket`

#### Implementation Approach
1. **Define PipelineTask:**
   Create a Celery Task class override:
   ```python
   from celery import Task
   class PipelineTask(Task):
       def on_failure(self, exc, task_id, args, kwargs, einfo):
           # Extract signal_id or incident_id from args[0]
           # Fetch Signal and update status = 'failed'
   ```
2. **Apply Task Base:** Decorate tasks using `@shared_task(bind=True, base=PipelineTask, max_retries=3, default_retry_delay=5)`.
3. **Differentiate Retry Scenarios:**
   * **Retryable:** Temporary rate limits, API timeouts, Redis connection issues.
   * **Non-Retryable:** Bad request errors (400), invalid serializer fields, programming bugs. Wrap task logic in try-except blocks and call `self.retry(exc=exc)` only on retryable errors.

#### Tests
* `test_task_failure_hook`: Raise an error inside a task and verify the related `Signal.status` is set to `'failed'` in the database.
* `test_task_retry_progression`: Verify that retryable exceptions trigger up to 3 retries before failing.

#### Risks
Infinite loop retries if exceptions are incorrectly categorized. (Mitigation: Let non-retryable exceptions like `MaxRetriesExceededError` propagate to prevent loops).

#### Rollback Strategy
Revert `@shared_task` decorators to standard Celery class configurations.

#### Verification
Run celery tests using `pytest`.

#### Cost
₹0.

---

### Phase 1F: AuditLog Activation

#### Objective
Activate the tamper-evident `AuditLog` database writes on key incident changes while ensuring logging errors do not crash the primary pipeline execution.

#### Current Behavior
The `AuditLog` model is defined in `apps/audit/models.py`, but no views or tasks write to it.

#### Desired Behavior
* Write `'incident_created'` entries when incidents are created.
* Write `'pipeline_completed'` entries on final WebSocket push.
* Write `'incident_resolved'` entries when coordinators manually resolve incidents.
* Wrap all audit database saves in try-except blocks. An `AuditLog` writing failure should NOT block the successful execution of the core AI pipeline.

#### Files Affected
* `d:\My Projects\Django\Prahari\pipeline	asks.py`
* `d:\My Projects\Django\Praharipps\incidents\coordinator_views.py`

#### Functions/Classes Affected
* `route_to_agents()`
* `push_to_websocket()`
* `coordinator_resolve_incident()`

#### Implementation Approach
1. Import `AuditLog` inside targeted tasks and views.
2. Call `AuditLog.objects.create(...)` in the appropriate logic steps.
3. Wrap each create statement in:
   ```python
   try:
       AuditLog.objects.create(...)
   except Exception as exc:
       logger.warning("AuditLog write failed (non-blocking): %s", exc)
   ```

#### Tests
* `test_audit_creation_success`: Verify audit entries are generated on successful pipeline execution.
* `test_non_blocking_audit_failure`: Mock `AuditLog.save` to raise a database exception and verify the pipeline still completes successfully.
* `test_tamper_evident_hashing`: Verify altering a log entry changes its calculated hash.

#### Risks
High database write frequencies on single logs could cause write lock contentions. (Mitigation: Scoping handles single entries; try-except blocks prevent blocks).

#### Rollback Strategy
Revert audit write calls.

#### Verification
Execute test suite and manually check database entries.

#### Cost
₹0.

---

### Phase 1G: Regression Testing & Verification

#### Objective
Execute regression testing to verify system components work together without issue.

#### Current Behavior
No automated pipeline verification process is defined.

#### Desired Behavior
Verify database constraints, local services, model outputs, and run a safe production deployment test.

#### Files Affected
N/A (Verification phase only).

#### Implementation Approach
1. Run local container checks for Redis and PostgreSQL.
2. Execute the entire test suite.
3. Trigger a controlled production smoke test (submit one test signal with a mock text payload and verify Daphne and Celery process the flow).

#### Verification
* Ensure `pytest` yields a green report with zero failures.
* Monitor logging outputs during the production test run.

#### Cost
₹0.

---

## 4. Final Implementation Checklist

### Before Implementation
* [ ] Verify local Docker container services (`redis` and `postgis` / PostgreSQL) are running.
* [ ] Initialize the test directory structure (`tests/`).
* [ ] Verify environment variables (`GROQ_API_KEY`, `DJANGO_SETTINGS_MODULE`) are configured.
* [ ] Create a git branch checkpoint.

### After Each Phase
* [ ] Run `pytest` and verify the baseline tests pass.
* [ ] Perform manual developer checks on the Django admin dashboard.
* [ ] Check local logs for unexpected warning flags.
* [ ] Commit files to git.

### Before Deployment
* [ ] Verify full test suite passes with coverage.
* [ ] Verify all mock integration runs return expected values.
* [ ] Confirm API security tests return HTTP 401 for anonymous access.
* [ ] Verify Celery failure and retry states operate as expected.
* [ ] Verify `AuditLog` fails gracefully without blocking the pipeline.

### Production Deployment
* [ ] Daphne startup succeeds.
* [ ] Celery background workers are active.
* [ ] Validate database connectivity.
* [ ] Execute a single controlled test signal.
* [ ] Ensure all secrets remain unexposed in environment logs.

---

## 5. Summary Analysis & Sequence

### Recommended Implementation Sequence
1. **Create Test Suite:** Initialize `pytest.ini` and write baseline mock tests (Phase 1A).
2. **Endpoint Protection:** Restrict views to `[IsAuthenticated]` (Phase 1B).
3. **Clean Serializer:** Remove dynamic Meta field mutation (Phase 1C).
4. **LLM Error Tuning:** Adjust `base.py` rate limit criteria and remove monkeypatches (Phase 1D).
5. **Worker Retries:** Add `PipelineTask` and task-level error checks (Phase 1E).
6. **Audit Logs:** Add non-blocking `AuditLog.objects.create` calls (Phase 1F).
7. **Final Check:** Run regression checks and deploy (Phase 1G).

### Highest Risk Changes
* **Celery task retry propagation:** If `self.retry` is not raised correctly, it can lead to infinite loops or unexpected state changes.
* **Removing monkeypatches:** If imported namespaces mismatch, startup circular dependency errors could occur in Django apps.

### Lowest Risk Changes
* **Serializer Field Cleanup:** Statically declaring fields inside the Meta class is a safe configuration task.
* **View Permission Updates:** Swapping `AllowAny` for `IsAuthenticated` is a low-risk change.

### Developer Approval Points
1. **Approval Point 1:** Confirm the test suite executes successfully locally.
2. **Approval Point 2:** Confirm the monkeypatch cleanup allows Django to start up without errors.
3. **Approval Point 3:** Verify the API endpoint restrictions deny unauthorized requests.
