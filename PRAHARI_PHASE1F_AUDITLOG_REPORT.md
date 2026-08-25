# Phase 1F: AuditLog Activation Report

This report documents the design, implementation, and verification results for **Phase 1F: AuditLog Activation**.

---

## 1. Existing AuditLog Design

### Fields:
- `id` (UUIDField, Primary Key)
- `incident` (ForeignKey to `Incident`, related_name="audit_logs")
- `action` (CharField, e.g. `'incident_created'`, `'pipeline_completed'`, `'incident_resolved'`)
- `performed_by` (CharField, representing actor username, agent, or system component name)
- `payload` (JSONField, storing extra non-sensitive structured metadata)
- `hash` (CharField, storing SHA-256 digest of key fields)
- `timestamp` (DateTimeField, auto-default to timezone.now)

### Hash Mechanism:
The tamper-evident integrity design hashes the key fields separated by a pipe (`|`) character before database save:
```python
raw = f"{self.incident_id}|{self.action}|{self.performed_by}|{self.timestamp.isoformat()}"
self.hash = hashlib.sha256(raw.encode()).hexdigest()
```

### Integrity Design & Tamper-Evidence:
- The SHA-256 hash is computed and stored automatically during the model's `save()` operation.
- Any subsequent modifications to the key fields will cause the output of `compute_hash()` to differ from the stored `hash` value, immediately exposing tampering.

### Current Limitations:
- The hash computes a signature only over the fields of the individual record. It is not chained to the previous audit log entries (i.e. not a Merkle tree/blockchain chain).
- There is no automated database trigger or background job to periodically verify all hashes; validation is done on-demand or during tests.

---

## 2. Audit Events Activated

We activated three core events using the existing design:

| Event Name | Source Function/Task | When It Is Written | performed_by Behavior |
| :--- | :--- | :--- | :--- |
| **`incident_created`** | `route_to_agents` in [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py) | When a new `Incident` object is successfully created (`if created:` is True). | `"system/pipeline"` |
| **`pipeline_completed`** | `push_to_websocket` in [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py) | After signal status is successfully marked as `"processed"`, indicating all AI agents and translations completed. | `"system/pipeline"` |
| **`incident_resolved`** | 1. `IncidentDetailView.perform_update` in [`apps/incidents/views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/views.py)<br>2. `resolve_incident` in [`apps/incidents/coordinator_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/coordinator_views.py) | When the coordinator status transitions/is set to `'resolved'`. | Authenticated coordinator's username (e.g. `request.user.username`), falling back to `"unknown"` if unauthenticated. |

---

## 3. Failure Isolation

To prevent AuditLog failures from blocking critical operational flows (e.g. a failed audit write should not fail an otherwise successful pipeline or API call), we introduced `AuditLog.log_event` inside `apps/audit/models.py`. 

If `log_event` encounters an error (e.g., database connection loss, validation constraint error):
1. The exception is caught in a `try-except` block.
2. The error details are written to the Django logs using `logger.error()`.
3. The helper returns `None` safely.
4. The main pipeline or request continues executing successfully.

---

## 4. Transaction Behavior

To protect successful pipeline commits from rollback when an audit log write fails:
- The database write inside `AuditLog.log_event` is wrapped in `with transaction.atomic():`.
- This creates a **database savepoint**. If the audit save fails, PostgreSQL only rolls back to the savepoint, leaving the outer transaction unaffected.
- This guarantees that an AuditLog database failure will never roll back or abort the core pipeline transaction.

---

## 5. Idempotency

We prevented duplicate audit entries from Celery retries using the following logic:
- **`incident_created`**: Written only when `created` is True from `Incident.objects.update_or_create`. If retried, `created` is False, and the log is skipped.
- **`pipeline_completed`**: We perform a check `if not AuditLog.objects.filter(incident=incident, action='pipeline_completed').exists():` before creating the log. This prevents multiple completion events from being recorded for the same incident during retries.
- **`incident_resolved`**: Since resolution is a manual action, subsequent POST/PATCH requests will only generate logs if the action is explicitly retried by the user.

---

## 6. Tests

We created a dedicated test file [`tests/test_auditlog.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_auditlog.py) with 8 test cases:
1. `test_audit_log_creation_and_hash_generation`: Validates creation, hash presence, and determinism.
2. `test_audit_log_event_helper`: Validates the `log_event` helper.
3. `test_non_blocking_audit_failure`: Verifies that audit failures do not crash the caller.
4. `test_pipeline_incident_created_audit`: Verifies that `route_to_agents` creates the `incident_created` log.
5. `test_pipeline_completed_audit`: Verifies that `push_to_websocket` creates the `pipeline_completed` log.
6. `test_pipeline_completed_idempotency`: Verifies that retries do not log duplicate completion events.
7. `test_incident_resolved_api_audit`: Verifies REST PATCH resolution logs `incident_resolved` with simple-jwt user credentials.
8. `test_incident_resolved_dashboard_audit`: Verifies dashboard HTML POST resolution logs `incident_resolved` with coordinator credentials.

---

## 7. Test Results

We ran the complete test suite:
- **Total**: 31
- **Passed**: 31
- **Failed**: 0
- **Skipped**: 0
- **Errors**: 0
- **Warnings**: 31 (All are harmless `UserWarning: Overriding setting DATABASES` from `conftest.py`)
- **Duration**: ~3.33 seconds

---

## 8. Security

We verified that:
- No API keys are stored in `payload` or metadata.
- No JWTs or Authorization headers are recorded.
- No passwords, secrets, or large raw LLM prompt texts are written to the database.

---

## 9. Files Changed

1. **[`apps/audit/models.py`](file:///d:/My%20Projects/Django/Prahari/apps/audit/models.py)**: Added `AuditLog.log_event` classmethod.
2. **[`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py)**: Added `incident_created` and `pipeline_completed` audit logs.
3. **[`apps/incidents/views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/views.py)**: Added `incident_resolved` audit logs for API PATCH requests.
4. **[`apps/incidents/coordinator_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/coordinator_views.py)**: Added `incident_resolved` audit logs for coordinator resolve POST requests.
5. **[`tests/test_auditlog.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_auditlog.py)**: New test file with 8 test cases.

---

## 10. Remaining Limitations

- **Chaining**: Chaining hashes to the previous rows (blockchain style) is not implemented.
- **Verification Cron**: Periodically running a job to verify all audit hashes against their computed hashes is left for a future observability phase.
