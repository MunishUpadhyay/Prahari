# Phase 1E: Celery Pipeline Reliability Verification Report

This report documents the verification of the Celery pipeline retry semantics, existing test structures, warnings analysis, Groq/Celery interactions, and task idempotency.

---

## 1. Retry Semantics

We inspected the Celery task configuration and exception handling implementation in [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py). The task decorator defines:
`@shared_task(bind=True, max_retries=3, default_retry_delay=5, name="...")`

### Execution Flow:
- **Initial Execution**: The task is triggered for the first time. The value of `self.request.retries` is `0`.
- **Retry #1**: On a transient error, the task calls `self.retry()`. On execution, `self.request.retries` is `1`.
- **Retry #2**: On failure, task retries. On execution, `self.request.retries` is `2`.
- **Retry #3**: On failure, task retries. On execution, `self.request.retries` is `3`.
- **Exhaustion**: On execution #4 (where `self.request.retries` is `3`), the condition `self.request.retries >= self.max_retries` (`3 >= 3`) evaluates to `True`. The task enters the failure handler, marks the signal as `"failed"`, writes the stack trace, and propagates the error without rescheduling.

### Verification Metrics:
- **Initial execution** = 1
- **Maximum retry operations** = 3
- **Maximum total executions** = 4 (1 initial + 3 retries)

> [!NOTE]
> The existing report's wording of "3 attempts" is technically ambiguous; it could be misinterpreted as 3 total executions. The correct description is **3 maximum retry operations** resulting in up to **4 total task executions** before exhaustion.

---

## 2. Max Retry Test

We inspected `test_route_to_agents_max_retries_exhausted` in [`tests/test_celery.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_celery.py):

- **Retry Count Verification**: Yes, the test verifies exhaustion by mocking the request retries context to `3` and verifying that `self.retry` is not called again.
- **Number of Task Executions**: Eager Celery mode does not automatically cycle retries recursively in a loop by default when using `.run(...)`. The mock setup correctly isolates and verifies the boundary behavior of execution at limit.
- **Final Failure & Signal Status**: Yes, the test asserts that `OperationalError` propagates to the caller, `signal.status` changes to `"failed"`, and the exception description is saved in `signal.metadata["error"]`.

The existing test suite is fully robust. It checks the retry triggers on first execution (under `test_route_to_agents_retryable_error`) and checks the failure handling on final execution (under `test_route_to_agents_max_retries_exhausted`), testing all branches of the retry/exhaustion logic.

---

## 3. Warning Analysis

We ran the test suite:
```powershell
.\.venv\Scripts\pytest
```

### Warning Categories:
All 23 warnings produced belong to a single category:
`UserWarning: Overriding setting DATABASES can lead to unexpected behavior.`
This warning is raised at `tests/conftest.py:20` when we override `settings.DATABASES` to configure an in-memory SQLite database.

### Classification:
- **Category**: **C. Test configuration issue** / **A. Harmless framework warning**
- **Explanation**: This warning is harmless. Overriding the settings at test runtime is necessary in this repository to prevent test runs from polluting or querying the production/development PostgreSQL database.
- **Recommended Action**: Leave the code unchanged. To clean up the test output, we can add a filter to `pytest.ini` in a later task:
  ```ini
  filterwarnings =
      ignore:Overriding setting DATABASES:UserWarning
  ```

---

## 4. Groq/Celery Interaction

We analyzed the model key rotation from Phase 1D and the task retrying from Phase 1E together:
- **Groq Fallback Loop (Bounded)**: Inside `BaseAgent.call_groq()`, the key and model rotation loops synchronously over the array of API keys and fallback models. This loop is fully synchronous and is contained within a single execution of the Celery task.
- **Task Retry Isolation**: Only when all Groq keys/models are exhausted and a final exception is raised does the control return to the Celery task. The task then decides whether to retry the entire stage.
- **Conclusion**: There is **no accidental recursion or retry explosion**. Bounded model/key rotation completes synchronously within one task execution, and Celery retries only when the entire run fails with a retryable exception.

---

## 5. Idempotency Verification

We verified the idempotency checks inside [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py):

### Protected (Idempotent):
- **Triage Agent & Rights Agent**: `route_to_agents` checks `Incident.agent_outputs` for `"triage"` and `"rights"` keys, reusing them if they exist.
- **Coordination Agent**: `coordination_agent` checks `Incident.agent_outputs` for the `"coordination"` key, reusing it if it exists.
- **Language Agent**: `push_to_websocket` checks `Incident.agent_outputs` for the `"language"` key, reusing translations.
- **RAG Ingestion**: `ingest_incident_to_history` uses ChromaDB's `collection.upsert()` with `ids=[str(incident_id)]`, ensuring duplicate ingestion updates the existing vector rather than creating duplicates.

### Unprotected (Non-Idempotent Limitations):
- **WebSocket Broadcast**: Every retry of `push_to_websocket` broadcasts the event over Django Channels. This is harmless but repeated.
- **SMS Notifications**: If `push_to_websocket` is retried, it dispatches the `send_notification` task again without checking if a notification was already sent. This could lead to duplicate SMS messages to the user.

> [!TIP]
> In a subsequent phase, we should add a `notification_sent` flag to `Signal` or check if a `Notification` record already exists for the signal in `send_notification` before sending.

---

## 6. Test Results

The test suite results are:
- **Total**: 23
- **Passed**: 23
- **Failed**: 0
- **Skipped**: 0
- **Errors**: 0
- **Warnings**: 23

---

## 7. Required Changes

"No implementation changes required."

*Note: In the beginning of this session, a minor test mock adjustment was performed in `tests/test_celery.py` to resolve an `AttributeError` caused by accessing task attributes on the Celery proxy object. We solved it by resolving the proxy with `_get_current_object()` before monkeypatching.*
