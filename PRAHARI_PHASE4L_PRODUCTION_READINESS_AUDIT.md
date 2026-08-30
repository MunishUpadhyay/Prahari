# Prahari Phase 4L — Production Readiness Audit

## Executive Summary
This audit provides a comprehensive, read-only evaluation of Prahari's current architecture, security controls, and infrastructure to determine its readiness for public deployment. While the core functional flow and bilingual frontends are stable and cover all standard path operations, there are critical production configuration gaps, security risks on shared terminals, database query inefficiencies, and Celery worker failover vulnerabilities that must be resolved prior to launch.

---

## Current Architecture

### Django Setup
*   **Settings Layering**: Uses `base.py` for common variables, `dev.py` for local sqlite3 configuration, and `prod.py` for environment-driven PostgreSQL, WhiteNoise static files, and security cookies.
*   **Routing**: Clean citizen-coordinator isolation via path structures and staff privileges.

### Processing Pipeline
*   **Celery Chaining**: Processing is structured as a five-stage serial pipeline (`ingest_signal` -> `classify_domain` -> `route_to_agents` -> `coordination_agent` -> `push_to_websocket`), backed by SQLite in dev and PostgreSQL/Redis in production.

---

## Production Readiness Scorecard

| Area | Status | Severity | Notes |
|---|---|---|---|
| **Authentication** | NEEDS CHANGE | 🟠 HIGH | Dynamic citizen auth works, but cookies lack browser-close expiration which creates session leakage risk on public computers. |
| **Authorization** | NEEDS CHANGE | 🟠 HIGH | Citizen and coordinator views are separated, but raw agent JSON outputs are exposed in the unauthenticated status API. |
| **Anonymous Reports** | NEEDS CHANGE | 🟠 HIGH | Uses SHA256 hashes for Return Keys. However, Return Key verification lacks rate-limiting per Report ID. |
| **Database** | NEEDS CHANGE | 🟠 HIGH | Lacks database indexes on `user` and `created_at` fields, which will cause sequential scans as data size increases. |
| **PostGIS** | DEFERRED | 🔵 LOW | PostGIS is configured, but the spatial proximity queries are scaffolded and return a `501 Not Implemented` response. |
| **Redis** | NEEDS CHANGE | 🔴 CRITICAL | Local connection detection is safe in dev, but fallback synchronous blocking in the view layer is a thread-blocking risk. |
| **Celery** | NEEDS CHANGE | 🟠 HIGH | Early stages (`classify_domain`) lack bound retry decorators, making the pipeline vulnerable to transient API failures. |
| **AI Pipeline** | NEEDS CHANGE | 🟠 HIGH | Handles model fallback and key rotation, but raw LLM parse failures can cause reports to become stuck in processing status. |
| **Frontend** | GOOD | 🟢 GOOD | responsive layouts, live progress indicators, and bilingual controls are consistent and accessible. |
| **Email** | DEFERRED | 🔵 LOW | Email is used as the login identifier; transactional mail, registration verification, and password resets are deferred. |
| **Security** | NEEDS CHANGE | 🔴 CRITICAL | `CSRF_TRUSTED_ORIGINS` is missing from `prod.py`, causing form submissions to fail on HTTPS. |
| **Observability** | NEEDS CHANGE | 🟡 MEDIUM | Standard Django logger is used. Correlation IDs and health check endpoints are missing. |
| **Deployment** | NEEDS CHANGE | 🟡 MEDIUM | Docker Compose is local-focused. Render free-tier deployment requires configuring external persistent storage. |
| **Testing** | NEEDS CHANGE | 🟠 HIGH | Happy-path tests pass, but concurrent requests, API failover, and boundary checks are missing. |
| **Privacy** | NEEDS CHANGE | 🟡 MEDIUM | Personal contact information is saved in metadata without an automated cleanup or data retention policy. |

---

## Critical Findings

### 1. Missing CSRF Trusted Origins Configuration (`prod.py`)
*   **Severity**: 🔴 CRITICAL
*   **Status**: NEEDS CHANGE
*   **Detail**: Since `SECURE_SSL_REDIRECT = True` is configured, all requests under production will run over HTTPS. Django checks incoming referrers against `CSRF_TRUSTED_ORIGINS` on HTTPS POST/PATCH requests. Because this setting is missing in `prod.py`, all citizen submissions, logins, and linking forms will fail with a `403 Forbidden` CSRF verification error.
*   **Recommendation**: Add `CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")` to `config/settings/prod.py`.

### 2. Thread-Blocking Synchronous Eager Fallback in Ingestion Views
*   **Severity**: 🔴 CRITICAL
*   **Status**: NEEDS CHANGE
*   **Detail**: In `apps/signals/citizen_views.py`, if `ingest_signal.delay` fails (e.g., due to Redis connection loss), the catch block sets `celery_app.conf.task_always_eager = True` globally and runs the task synchronously. In a production ASGI environment (Daphne), this blocks the active web thread for up to 60 seconds during LLM API execution, resulting in immediate service unavailability for concurrent users.
*   **Recommendation**: Fail fast when Celery or Redis is down. Show the citizen a user-safe connection error card instead of executing heavy asynchronous pipelines synchronously on HTTP thread context.

### 3. Missing Report ID Rate Limiting for Return Key Verification
*   **Severity**: 🔴 CRITICAL
*   **Status**: NEEDS CHANGE
*   **Detail**: The `verify-code` API endpoint only implements IP-based rate limiting (`limit=5, period=60`). If an attacker uses multiple IPs (a distributed botnet) or rotating proxies, they can brute-force the 6-character Return Key for a targeted Report ID because there is no limit on verification attempts for a specific Report ID.
*   **Recommendation**: Implement a cache-backed rate-limiter that counts failed verification attempts per `signal_id`. Lock verification for that specific report for 15 minutes after 5 failed attempts.

---

## High-Priority Findings

### 1. Leakage of Raw LLM Output to Frontend Status API
*   **Severity**: 🟠 HIGH
*   **Status**: NEEDS CHANGE
*   **Detail**: The `citizen_signal_status_api` view returns the entire `agent_outputs` dictionary directly in the JSON response payload. This exposes raw system prompts, internal reasoning paths, confidence scores, and API call logs to anyone viewing browser developer tools, which violates the principal of information containment.
*   **Recommendation**: Sanitize the JSON response in the API view to output only citizen-facing summaries, bilingual steps, and checklist values.

### 2. Missing Indexes on ForeignKey and Audit Fields
*   **Severity**: 🟠 HIGH
*   **Status**: NEEDS CHANGE
*   **Detail**: With Phase 4K introducing citizen profiles, the query `Signal.objects.filter(user=request.user).order_by("-created_at")` is run every time the citizen opens their profile page. The `user` foreign key and `created_at` columns do not have indexes, which will result in expensive sequential scans as the database size increases.
*   **Recommendation**: Add a combined database index on `user` and `created_at` in the `Signal` model's Meta options.

### 3. Early Pipeline Stages Lack Retry Decorators
*   **Severity**: 🟠 HIGH
*   **Status**: NEEDS CHANGE
*   **Detail**: The `classify_domain` task does not have retries configured (`max_retries` is only specified on steps 3, 4, and 5). If the Groq/OpenAI API hits a transient rate limit or network timeout during step 2, the pipeline fails immediately and marks the signal as failed, with no retry attempts.
*   **Recommendation**: Configure `@shared_task(bind=True, max_retries=3, default_retry_delay=5)` on `classify_domain` to align retry logic across the pipeline.

### 4. Session Lifetime Cookie Vulnerability on Public Shared Devices
*   **Severity**: 🟠 HIGH
*   **Status**: NEEDS CHANGE
*   **Detail**: By default, Django sessions persist for 2 weeks in cookie storage. Since citizens often submit reports from shared community computers or cyber cafes, leaving sessions open indefinitely allows subsequent users of the device to view sensitive report history.
*   **Recommendation**: Set `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` in `prod.py` to ensure authentication credentials and verification cookies are purged when the browser is closed.

---

## Medium-Priority Findings

### 1. Stuck Pipeline States Lack Automatic Database Invalidation
*   **Severity**: 🟡 MEDIUM
*   **Status**: NEEDS CHANGE
*   **Detail**: If a worker crashes or is forcefully terminated mid-pipeline, the `Signal` status remains stuck as `processing` or `classified` in the database. While the status API returns a pipeline timeout error to the client, the backend never cleans up or updates the database record.
*   **Recommendation**: Implement a Celery beat heartbeat or cron job that queries for active reports older than 15 minutes and updates their status to `failed`.

### 2. Lack of Centralized Application Observability
*   **Severity**: 🟡 MEDIUM
*   **Status**: NEEDS CHANGE
*   **Detail**: Standard logs do not include a unified correlation ID linking HTTP requests to Celery background execution. If a citizen reports a stuck submission, tracing the failure through log files is difficult.
*   **Recommendation**: Pass the `signal_id` as a correlation tag across all logs and print structured JSON logs in production.

---

## Low-Priority Findings

### 1. Inactive PostGIS Configuration
*   **Severity**: 🔵 LOW
*   **Status**: DEFERRED
*   **Detail**: PostGIS is loaded in Django settings but is completely unused. The location text is saved as a plain string inside the `metadata` dictionary, and geographic queries to `/api/resources/nearby/` return a `501 Not Implemented` mock response.
*   **Recommendation**: Map the string address to a geospatial point using a geocoder and store it in the PointField `location` database field to enable proximity logic.

### 2. Missing Email Notifications and Password Recovery
*   **Severity**: 🔵 LOW
*   **Status**: DEFERRED
*   **Detail**: Citizens log in using their email, but email verification and password reset flows are completely missing.
*   **Recommendation**: Add standard SMTP django-mailer setups for transactional recovery workflows.

---

## What Is Already Strong
*   **Robust LLM Fallback and Key Rotation**: The `BaseAgent` class includes an exceptional multi-model and multi-key fallback loop, making LLM execution resilient to rate limits (429s) and invalid credentials.
*   **Bilingual Translation Layer**: The bilingual system is deeply integrated across both templates and dynamic API responses.
*   **Clean Separation of Concerns**: Clear, robust separation of Citizen endpoints and Coordinator actions based on `is_staff` privileges.

---

## What Must Be Fixed Before Deployment
1.  Configure `CSRF_TRUSTED_ORIGINS` in `config/settings/prod.py`.
2.  Remove thread-blocking synchronous Celery execution in `apps/signals/citizen_views.py`.
3.  Implement Report ID-based rate limiting on the `/verify-code/` endpoint.
4.  Sanitize `agent_outputs` to exclude raw JSON from the frontend status API.
5.  Enable `SESSION_EXPIRE_AT_BROWSER_CLOSE` to protect shared computers.

---

## What Can Wait
1.  PostGIS implementation (proximity query wiring can wait until geographical data collection expands).
2.  Email verification, password reset mailers, and notifications.
3.  Centralized Observability logging systems.

---

## PostGIS Opportunities
*   **Nearest Responder Routing**: Resolve the nearest hospital or legal aid office relative to the incident's geo-coordinates.
*   **Incident Hotspot Clustering**: Group coordinates to identify high-density warning zones on coordinator maps.

---

## Email Opportunities
*   **Report Status Alerts**: Email notifications when an anonymous report is processed or updated by a coordinator.
*   **Secure Password Reset**: Secure token generation for password recovery.

---

## Render Deployment Risks
*   **Database Disk Space**: The free tier of managed PostgreSQL has strict storage limits. Binary attachments (like images uploaded with signals) should be saved to an external object store (e.g., AWS S3) rather than local disk.
*   **Service Sleeping**: Render free-tier services spin down after 15 minutes of inactivity. This will cause the Daphne server and Celery workers to experience severe latency on first access.
*   **Celery Redis Broker**: A managed Redis instance is required since Render container filesystems are ephemeral and cannot support a reliable local Redis broker.

---

## Recommended Phase 4L.1 Implementation Order
1.  **Security settings**: Add `CSRF_TRUSTED_ORIGINS` and set `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`.
2.  **Verify-Code Rate Limiting**: Limit failed code validation attempts per `signal_id`.
3.  **Sanitize Status API**: Remove raw `agent_outputs` from the citizen status endpoint response.
4.  **Celery Ingestion Stability**: Remove synchronous eager fallback execution in submission views.
5.  **Celery Pipeline Resilience**: Add retry decorators to the `classify_domain` Celery task.
6.  **Database Optimization**: Add indexes on `Signal` `user` and `created_at` fields.

---

## Production Readiness Conclusion
**NOT READY**

Prahari is functionally advanced, but cannot be deployed to production until CSRF configurations are fixed, blocking backend execution flows are removed, and sensitive agent data leakages are resolved.
