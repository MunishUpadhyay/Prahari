# Phase 3A — Production Access Control & Security

## 1. Executive Summary

- **Objective**: Harden Prahari's production access control and security properties, ensuring that citizens only access their own signals/incidents and coordinators can only retrieve/mutate incidents belonging to their authorized tenant.
- **Key Actions Completed**:
  - Centralized tenant resolution under a unified helper `get_authorized_tenant(request)` in [`apps/tenants/utils.py`](file:///d:/My%20Projects/Django/Prahari/apps/tenants/utils.py). [IMPLEMENTED, VERIFIED]
  - Scoped all coordinator-facing API viewsets and HTML detail views, resolution updates, statistics counters, and notice generation queries to the active authorized tenant. [IMPLEMENTED, VERIFIED]
  - Generalized sliding-window client IP rate-limiter and applied it to `verify-code` (5 reqs/min) and simple JWT obtain/refresh views (5 and 10 reqs/min respectively). [IMPLEMENTED, VERIFIED]
  - Wrote 12 automated security regression integration tests. [IMPLEMENTED, VERIFIED]
  - Configured Locate Memory Cache (`LocMemCache`) for local test environments to mock Redis cache dependency. [IMPLEMENTED, VERIFIED]

---

## 2. Current Authentication Architecture

Prahari uses two distinct forms of authentication:
1. **Simple JWT Token Auth**: Coordinator APIs are protected by DRF's `JWTAuthentication` class configured in `settings.py`. [VERIFIED]
2. **Session Authentication**: Coordinator HTML templates use Django's standard session-based cookie authentication (`AuthenticationMiddleware`). [VERIFIED]
3. **Anonymous Session Validation**: Citizen tracking uses Django sessions to map signal verification access flags. [VERIFIED]

---

## 3. Current Authorization Architecture

Authorization is mapped per-role:
1. **Authenticated Coordinators**: Can access coordinator endpoints scoped to their tenant. [VERIFIED]
2. **Anonymous Citizens**: Can submit signals and track their own incidents. [VERIFIED]
3. **Webhooks Ingestion**: Secured by API keys hashed under SHA-256 (`verify_api_key`). [VERIFIED]

---

## 4. Citizen Tracking Security

- **Code Generation**: Cryptographically secure 6-character uppercase alphanumeric access codes are generated on signal creation. [VERIFIED]
- **Verification binding**: Successful code check validates a signal-specific session flag (`verified_{signal.id} = True`), preventing verified session A from accessing signal B. [VERIFIED]

---

## 5. Coordinator Authentication

- **Django Auth**: Leverages built-in Django user model. [VERIFIED]
- **HTML Dashboard Protection**: Handled via `@login_required(login_url="/login/")` decorator. [VERIFIED]
- **Token Invalidation**: Refresh token rotation is enabled (`ROTATE_REFRESH_TOKENS = True`), with blacklisting configuration. [VERIFIED]

---

## 6. Object-Level Authorization

- **Hardened Scoping**: Detail queries and update mutations verify that the incident belongs to the authorized tenant:
  `Incident.objects.filter(signal__tenant=tenant)`
- Any attempt to query another tenant's incident UUID will return `404 Not Found` to prevent information leakage. [IMPLEMENTED, VERIFIED]

---

## 7. API Permission Audit

Coordinator detail views, outcome stats, and legal notice generation endpoints are protected by `permission_classes = [IsAuthenticated]`. Non-coordinator endpoints (such as verify-code and signal ingestion) are public, but protected by rate limits. [VERIFIED]

---

## 8. Incident Enumeration

Incident primary keys are random `UUIDField` objects. Attempts to query nonexistent or random UUIDs return `404 Not Found`. [VERIFIED]

---

## 9. Information Disclosure

No sensitive details (such as tracebacks, raw texts, phone numbers, or metadata) are disclosed to unauthorized clients. Authorization check failures return standard clean `403 Forbidden` or `404 Not Found` messages. [VERIFIED]

---

## 10. Session Security

- Session cookies use `SESSION_COOKIE_SECURE = True` in production. [VERIFIED]
- CSRF middleware validates POST requests. [VERIFIED]
- Session ID rotation is triggered automatically on coordinator login (`login(request, user)`). [VERIFIED]

---

## 11. Rate Limiting

- **Signal Ingest API**: Sliding-window rate limiter limits IP to 10 requests per hour. [VERIFIED]
- **Access Code Verification**: Limits attempts to 5 requests per minute (`key_prefix="verify"`). [IMPLEMENTED, VERIFIED]
- **Token API**: Limits `token_obtain_pair` to 5 requests per minute (`key_prefix="token"`) and `token_refresh` to 10 requests per minute (`key_prefix="token_refresh"`). [IMPLEMENTED, VERIFIED]

---

## 12. Database Ownership

Ownership relationships are clean:
`Tenant` (1) ◄── (N) `Signal` (1) ◄── (1) `Incident`

---

## 13. Multi-Tenant Decision

- **Limitation**: Currently, Prahari is single-tenant at the Coordinator layer because there is no relationship mapping a Django `User` object to a `Tenant`.
- **Mitigation**: Scoping all coordinator views through `get_authorized_tenant(request)` acts as a query-scope hardening boundary, ensuring all actions map to the default active tenant. If multi-tenancy is wired in the future, updating only this helper will secure the entire project. [VERIFIED]

---

## 14. Frontend Security

AJAX calls inside `report_status.html` and `coordinator_detail.html` bind only to authorized views. Data extraction is fully blocked at the backend controller level. [VERIFIED]

---

## 15. Security Fixes Implemented

1. Scoped `IncidentDetailView`, `SimilarIncidentsView`, and `LegalNoticeView` in [`apps/incidents/views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/views.py) through `get_authorized_tenant`.
2. Scoped `coordinator_dashboard`, `coordinator_incident_detail`, and `coordinator_resolve_incident` in [`apps/incidents/coordinator_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/coordinator_views.py) through `get_authorized_tenant`.
3. Extended `rate_limit_ip` in [`apps/signals/utils.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/utils.py) to support isolated prefixes.
4. Added rate limiting to `SignalVerifyCodeView`, `TokenObtainPairView`, and `TokenRefreshView`.
5. Configured `LocMemCache` for tests in [`tests/conftest.py`](file:///d:/My%20Projects/Django/Prahari/tests/conftest.py).

---

## 16. Security Regression Tests

Added 12 integration tests in `tests/test_api.py` under `test_security_regression(client)`:
1. Citizen A accesses Citizen A status -> Allowed.
2. Citizen A accesses Citizen B unverified anonymous status -> Forbidden (403).
3. Anonymous user accesses unverified anonymous status -> Forbidden (403).
4. Verified Citizen A accesses Citizen B anonymous status -> Forbidden (403).
5. Valid verification code for A + querying UUID of B -> Forbidden (403).
6. Coordinator accesses tenant-authorized incident A -> Allowed.
7. Coordinator tries to retrieve Tenant B's incident B -> Not Found (404).
8. Coordinator tries to mutate/resolve Tenant B's incident B -> Not Found (404).
9. Unauthenticated coordinator dashboard access -> Redirects (302).
10. Invalid JWT on incident details -> Unauthorized (401).
11. Nonexistent incident UUID -> Not Found (404).
12. Repeated verify-code attempts -> Rate Limited (429).

---

## 17. Full Test Results

All 52 automated tests passed successfully:
```powershell
52 passed, 52 warnings in 24.86s
```

---

## 18. Manual Smoke Test

Executed custom python script [`scratch/manual_smoke_test.py`](file:///C:/Users/munis/.gemini/antigravity-ide/brain/c9aad996-ccb1-46a7-a90e-2d9406a0d568/scratch/manual_smoke_test.py) on dev settings:
- Status: **SUCCESS** (All assertions passed successfully).

---

## 19. API Contract Inventory

- **Citizen Endpoints**:
  - POST `/api/signals/` (Optional JWT) -> Ingests raw text/metadata.
  - POST `/api/signals/<signal_id>/verify-code/` (Anonymous, Rate-limited) -> Validates tracking codes.
  - GET `/report/<signal_id>/status/` (Anonymous, Session-protected) -> AJAX status polling.
- **Coordinator Endpoints**:
  - POST `/api/auth/token/` (Anonymous, Rate-limited) -> Obtains JWT.
  - GET `/api/incidents/` (JWT protected) -> Lists tenant-authorized incidents.
  - GET/PATCH `/api/incidents/<id>/` (JWT protected) -> Detail/mutation.
  - GET `/api/incidents/<id>/similar/` (JWT protected) -> Similarity lookup.
  - GET `/api/incidents/<id>/legal-notice/` (JWT protected) -> Statutorynotice generator.

---

## 20. Remaining Risks

- Hugging Face model download timeouts during the Render build phase. Monitor build logs.

---

## 21. Recommended Next Phase

- **Phase 3B**: Postman API Contract documentation.
