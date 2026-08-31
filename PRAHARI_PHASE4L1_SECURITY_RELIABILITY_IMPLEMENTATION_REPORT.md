# Phase 4L.1 — Prahari Production Security & Reliability Hardening Report

## 1. Executive Summary
Phase 4L.1 addresses all critical and high-priority findings identified in the Phase 4L Production Readiness Audit. We hardened production settings, removed thread-blocking Celery synchronous execution, added cache-backed per-report brute-force protection for Return Keys, sanitized public citizen status APIs, hardened session cookies for shared devices, added bound retry decorators to Celery tasks, introduced combined database indexing for citizen profile queries, and built a stale signal cleanup mechanism.

---

## 2. Findings Addressed & Security Controls Added

### 1. Production CSRF & Cookie Hardening
*   **File**: [`config/settings/prod.py`](file:///d:/My%20Projects/Django/Prahari/config/settings/prod.py)
*   **Changes**:
    *   Configured `CSRF_TRUSTED_ORIGINS` dynamically from environment variable `CSRF_TRUSTED_ORIGINS` with whitespace trimming and non-empty filtering.
    *   Set `SESSION_COOKIE_HTTPONLY = True` and `SESSION_COOKIE_SAMESITE = 'Lax'`.
    *   Set `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` so authentication and verification sessions automatically expire when shared/public browser windows close.
    *   Configured `CSRF_COOKIE_SAMESITE = 'Lax'`, `SECURE_HSTS_SECONDS = 31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`, and `SECURE_REFERRER_POLICY = 'same-origin'`.

### 2. Removal of Thread-Blocking Celery Eager Fallback
*   **File**: [`apps/signals/citizen_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/citizen_views.py)
*   **Changes**:
    *   Separated development vs. production Celery enqueue failure handling in `citizen_submit`.
    *   In production (`DEBUG=False`), if `ingest_signal.delay()` fails, the application does **not** mutate global `celery_app.conf` and does **not** run the LLM pipeline synchronously inside the HTTP worker thread.
    *   Instead, it records a clean `failed` status with a safe metadata message (`"Processing service temporarily unavailable. Please retry later."`) and redirects to the tracking page where a safe user failure card is rendered.

### 3. Per-Report Return Key Brute-Force Lockout
*   **File**: [`apps/signals/views.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/views.py)
*   **Changes**:
    *   Added Django cache-backed attempt counter (`verify_failed_attempts_<signal_id>`) in `SignalVerifyCodeView`.
    *   If 5 failed verification attempts occur on a single Report ID, the endpoint locks verification for that specific report for 15 minutes (900 seconds) returning HTTP 429 (`{"valid": false, "locked": true, "message": "..."}`).
    *   Successful verification clears the failure counter immediately.
    *   A lock on Signal A does not affect Signal B.
    *   Preserved IP-based rate limiting as an outer defense layer.

### 4. Status API Sanitization
*   **File**: [`apps/signals/citizen_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/citizen_views.py)
*   **Changes**:
    *   Removed `agent_outputs`, `timing`, `language_outputs`, `data.coordination`, and `data.language` from `citizen_signal_status_api`.
    *   Citizen-facing JSON response contains only sanitized fields required for report rendering (`title_en`, `title_hi`, `what_is_happening_en`, `what_is_happening_hi`, `legal_provisions`, `emergency_contacts`, `authorities_to_notify`, `immediate_actions`, `evidence_to_collect`, etc.).

### 5. Celery Retry Resilience & Structured Logging
*   **File**: [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py)
*   **Changes**:
    *   Converted `classify_domain` and `ingest_signal` to bound Celery tasks (`@shared_task(bind=True, max_retries=3, default_retry_delay=5)`).
    *   Transient exceptions trigger exponential backoff retries (`countdown = 5 * (2 ** retries)`).
    *   Non-retryable / terminal errors update the signal status to `failed` and log with correlation prefix: `[Pipeline: <signal_id>] [<task_name>]`.

### 6. Stale Pipeline Database Cleanup
*   **Files**: [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py), [`apps/signals/management/commands/cleanup_stale_signals.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/management/commands/cleanup_stale_signals.py)
*   **Changes**:
    *   Created `cleanup_stale_signals(timeout_minutes=15)` task that identifies reports stuck in `pending`, `processing`, or `classified` older than 15 minutes without recent updates and marks them as `failed`.
    *   Created a Django management command `python manage.py cleanup_stale_signals --timeout 15` for cron/operator maintenance.

### 7. Database Query Indexing
*   **Files**: [`apps/signals/models.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/models.py), [`apps/signals/migrations/0005_signal_signals_sig_user_id_c6184e_idx.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/migrations/0005_signal_signals_sig_user_id_c6184e_idx.py)
*   **Changes**:
    *   Added combined database index `models.Index(fields=["user", "-created_at"])` to `Signal.Meta.indexes`.
    *   Successfully created and applied migration `0005_signal_signals_sig_user_id_c6184e_idx`.

### 8. Health Check Endpoint & Session Invalidation Fix
*   **Files**: [`apps/signals/citizen_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/citizen_views.py), [`config/urls.py`](file:///d:/My%20Projects/Django/Prahari/config/urls.py), [`templates/report_status.html`](file:///d:/My%20Projects/Django/Prahari/templates/report_status.html)
*   **Changes**:
    *   Added `/health/` and `/api/health/` endpoints returning DB connectivity status for container health checks.
    *   Corrected `closeSessionAndGoHome()` in `report_status.html` to target `/api/signals/${signalId}/close-session/`.

---

## 3. Files Modified & Created

### Modified Files:
*   [`config/settings/prod.py`](file:///d:/My%20Projects/Django/Prahari/config/settings/prod.py)
*   [`config/urls.py`](file:///d:/My%20Projects/Django/Prahari/config/urls.py)
*   [`apps/signals/models.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/models.py)
*   [`apps/signals/views.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/views.py)
*   [`apps/signals/citizen_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/citizen_views.py)
*   [`pipeline/tasks.py`](file:///d:/My%20Projects/Django/Prahari/pipeline/tasks.py)
*   [`templates/report_status.html`](file:///d:/My%20Projects/Django/Prahari/templates/report_status.html)

### Created Files:
*   [`apps/signals/migrations/0005_signal_signals_sig_user_id_c6184e_idx.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/migrations/0005_signal_signals_sig_user_id_c6184e_idx.py)
*   [`apps/signals/management/__init__.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/management/__init__.py)
*   [`apps/signals/management/commands/__init__.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/management/commands/__init__.py)
*   [`apps/signals/management/commands/cleanup_stale_signals.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/management/commands/cleanup_stale_signals.py)
*   [`tests/test_hardening.py`](file:///d:/My%20Projects/Django/Prahari/tests/test_hardening.py)
*   [`PRAHARI_PHASE4L1_SECURITY_RELIABILITY_IMPLEMENTATION_REPORT.md`](file:///d:/My%20Projects/Django/Prahari/PRAHARI_PHASE4L1_SECURITY_RELIABILITY_IMPLEMENTATION_REPORT.md)

---

## 4. Verification & Testing

### Automated Test Suite:
Ran full pytest test suite:
*   **Result**: 73 passed (0 failed).
*   **Tests executed**:
    *   `tests/test_hardening.py` (Health check, per-report Return Key lockout, counter reset, status API sanitization, stale signal cleanup, indexed history query).
    *   `tests/test_identity.py` (Registration, login, logout, ownership isolation, anonymous unowned rules, report linking, coordinator isolation).
    *   `tests/test_api.py` (Ingestion, verify-code, close-session, rate-limiting, permissions).
    *   `tests/test_agents.py` (Sentinel, Triage, Rights, Coordination, Language agents, Groq fallback).
    *   `tests/test_celery.py` (Pipeline task execution and chain behavior).
    *   `tests/test_auditlog.py` (Audit event logging).
    *   `tests/test_rag.py` (Vector retrieval).
    *   `tests/test_integration.py` (End-to-end signal flow).

### Manual QA Scenarios:
1.  **Anonymous Submission**: Report created, tracking ID + Return Key shown once, continuous polling updates progress.
2.  **Return Key Brute Force**: 5 invalid attempts lock the specific report with HTTP 429 for 15 minutes; other reports remain accessible.
3.  **Return Key Success**: Correct Return Key unlocks the report and clears failed counter.
4.  **Status API Payload**: Response verified to contain no `agent_outputs`, `timing`, or internal prompt data.
5.  **Health Check**: `/health/` returns 200 OK with `{"status": "healthy", "database": "connected"}`.
6.  **Close Session**: Clicking Close Report Access successfully posts to `/api/signals/<id>/close-session/` and invalidates only that report's session authorization.

---

## 5. Intentionally Deferred Items
*   **PostGIS Proximity Query Wiring**: PostGIS geospatial calculation logic is deferred until spatial asset databases (hospitals/police/legal aid) are populated.
*   **Transactional Email Service**: SMTP providers and password reset emailers are deferred to cloud infrastructure provisioning.
