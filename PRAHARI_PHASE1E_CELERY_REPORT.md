# Phase 1E: Celery Pipeline Reliability Report

This report documents the implementation details, design decisions, and verification results for **Phase 1E: Celery Pipeline Reliability**.

---

## 1. Executive Summary
The primary objective of Phase 1E was to improve the robustness and correctness of Prahari's asynchronous Celery pipeline. Prior to this phase, transient infrastructure failures could cause tasks to fail silently without updating the associated signal status, leaving signals stuck in the intermediate `"processing"` state forever. Furthermore, no error details or stack traces were stored, making debugging difficult. 

To address these vulnerabilities, we refactored all 5 steps of the pipeline (`ingest_signal`, `classify_domain`, `route_to_agents`, `coordination_agent`, and `push_to_websocket`) to wrap task bodies in robust error-handling blocks, implemented transient/permanent exception classification, integrated exponential backoff retries, captured error tracebacks in the signal metadata, and enabled idempotency checks to bypass redundant LLM calls on retries.

All tests pass cleanly, ensuring a reliable, crash-resilient asynchronous pipeline.

---

## 2. Problems Identified
During the audit and investigation of `pipeline/tasks.py`, we identified the following critical concerns:
1. **Uncaught Exceptions & Stuck States**: Celery task executions were not wrapped in try-except blocks. When an unhandled error occurred, the task crashed, but the signal status was never set to `"failed"`.
2. **Lack of Error Traceability**: There was no logging of exception details or tracebacks back into the database for the user or developers to inspect.
3. **No Retry Strategy**: Tasks were decorated with `max_retries=3`, but did not utilize `self.retry()` to retry transient network/database errors.
4. **No Transient vs. Permanent Distinction**: Permanent programming errors (e.g., `ValueError`, `KeyError`, API input bugs), or Groq authentication failures (invalid API keys) were treated identically to temporary infrastructure errors (e.g., database connection loss, celery broker network disconnect). Retrying permanent errors is redundant and wasteful.
5. **Lack of Idempotency on Retries**: If a task failed in a downstream step (e.g. `coordination_agent` failed after `route_to_agents` succeeded), restarting or retrying would trigger all preceding LLM calls again, leading to duplicate API usage and costs.

---

## 3. Design Decisions & Implementation Details

### A. Transient vs. Permanent Error Classification
We introduced a helper function `is_retryable_exception(exc)` to isolate retryable exceptions:
- **Retryable (Transient)**: `django.db.OperationalError`, socket/network connection issues, broker connection failures.
- **Non-Retryable (Permanent)**: `ValueError`, `KeyError`, `AttributeError`, HTTP 400 Bad Request (API input bugs), or Groq authentication failures (invalid API keys).

### B. Exponential Backoff & Exhaustion Handling
For retryable exceptions, tasks trigger `self.retry` with exponential backoff:
$$\text{countdown} = 5 \times 2^{\text{retries}}$$
If the retry count reaches `max_retries` (3 attempts), or if a non-retryable exception is caught, the task enters the failure handler which updates `Signal.status = 'failed'` and stores the stringified traceback in `Signal.metadata['error']`.

We also solved a crucial edge case where Celery's native `self.retry` raising `MaxRetriesExceededError` could propagate out of the task and bypass the database status update. We resolve this by performing a pre-emptive check:
```python
retries_exhausted = self.request.retries >= self.max_retries
if is_retryable_exception(exc) and not retries_exhausted:
    raise self.retry(...)
else:
    handle_task_failure(signal_id, exc)
    raise exc
```

### C. Task Idempotency Checks
To prevent duplicate LLM calls on retry:
- `route_to_agents` checks if triage/rights agent outputs are already present in `Incident.agent_outputs` before invoking their respective runs.
- `coordination_agent` checks if coordination output is already present in `Incident.agent_outputs`.
- `push_to_websocket` checks if language translations are already present in `Incident.agent_outputs`.

---

## 4. Code Modifications

1. **[`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py)**:
   - Wrapped `ingest_signal`, `classify_domain`, `route_to_agents`, `coordination_agent`, and `push_to_websocket` task logic in try-except blocks.
   - Integrated `is_retryable_exception(exc)` and `retries_exhausted` verification.
   - Configured failure logging to update `Signal.status = 'failed'` and save tracebacks in `Signal.metadata['error']`.
   - Added idempotency checks in the agent dispatches.

2. **[`tests/test_celery.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_celery.py)**:
   - Added `test_is_retryable_exception` to assert exception categorization.
   - Added `test_celery_task_invocation_success` to verify successful processing.
   - Added `test_route_to_agents_retryable_error` to check retry triggers and exponential backoff.
   - Added `test_route_to_agents_non_retryable_error` to assert status set to failed and metadata filled.
   - Added `test_route_to_agents_max_retries_exhausted` to verify failure handling when retries are exhausted.
   - Added `test_pipeline_idempotency_prevents_duplicate_calls` to verify agent runs are skipped on retry.

---

## 5. Verification & Testing Results

We executed the test suite to verify the changes:
```powershell
.\.venv\Scripts\pytest
```

### Output:
```
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-8.3.2, pluggy-1.6.0
django: version: 5.0.6, settings: config.settings.dev (from ini)
rootdir: D:\My Projects\Django\Prahari
configfile: pytest.ini
plugins: anyio-4.13.0, Faker-40.18.0, langsmith-0.3.45, asyncio-0.23.8, django-4.8.0
asyncio: mode=strict
collected 23 items

tests\test_agents.py ........                                            [ 34%]
tests\test_api.py ...                                                    [ 47%]
tests\test_celery.py ......                                              [ 73%]
tests\test_integration.py .                                              [ 78%]
tests\test_agents.py .                                                   [ 82%]
tests\test_rag.py ....                                                   [100%]

============================== warnings summary ===============================
...
======================= 23 passed, 23 warnings in 1.87s =======================
```

All **23 tests passed successfully**, indicating that the test foundation, security features, serializer updates, Groq reliability logic, and Celery pipeline improvements are stable, isolated, and correct.
