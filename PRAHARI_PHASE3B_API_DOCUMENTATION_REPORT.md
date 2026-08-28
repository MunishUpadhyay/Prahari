# Phase 3B — API Contract, Postman & Developer Documentation Report

## 1. Complete Endpoint Inventory

A thorough audit of Prahari's routing configurations has discovered the following **11 authoritative HTTP API endpoints**:

1. **POST** `/api/signals/`
   - Ingests raw text signals with optional location and metadata.
2. **POST** `/api/signals/<signal_id>/verify-code/`
   - Validates 6-character citizen access codes.
3. **GET** `/report/<signal_id>/status/`
   - Returns structured processing status for citizens.
4. **POST** `/api/auth/token/`
   - Obtains access and refresh JWT pair.
5. **POST** `/api/auth/token/refresh/`
   - Refreshes expired access tokens.
6. **GET** `/api/incidents/`
   - Lists incidents filtered by the coordinator's authorized tenant.
7. **GET** `/api/incidents/<id>/`
   - Retrieves detail details for an incident.
8. **PATCH** `/api/incidents/<id>/`
   - Updates status or notes for an incident.
9. **GET** `/api/incidents/<id>/similar/`
   - Retrieves semantically similar historical incidents.
10. **GET** `/api/incidents/<id>/legal-notice/`
    - Renders statutory notice letters using BNS references.
11. **POST** `/api/webhooks/register/`
    - Configures active webhooks for tenants (SHA-256 API key required).

---

## 2. Authentication Model

Prahari uses two forms of API authentication:
- **Simple JWT Bearer Token**: Enforced on coordinator APIs.
  - Header: `Authorization: Bearer <access_token>`
  - Path: `/api/auth/token/` returns tokens valid for 1 hour (access) and 7 days (refresh, supports rotation/blacklisting).
- **Session Authentication**: Enforced on citizen status page AJAX polling. Sets session flag `verified_{signal_id} = True` on successful verify-code validation.

---

## 3. Authorization Model

- **Citizen Level**: Session verification is strictly bound to the specific Signal UUID. If session validates Code A, calls to retrieve Signal B will fail with a `403 Forbidden`.
- **Coordinator Level**: Query-scoped entirely via the `get_authorized_tenant(request)` helper. Coordinator requests filter `Incident.objects.filter(signal__tenant=tenant)`. Attempts to query another tenant's incident UUID will return `404 Not Found` to prevent information leakage.

---

## 4. Citizen API Flow

- **Submission**: `POST /api/signals/` -> Returns `signal_id` and tracks progress in background Celery queues.
- **Verification**: `POST /api/signals/<signal_id>/verify-code/` -> Authenticates session to the target signal.
- **Polling**: `GET /report/<signal_id>/status/` -> Polls structured steps until state changes to `processed`.

---

## 5. Coordinator API Flow

- **Access Token**: `POST /api/auth/token/` -> Obtains JWT.
- **Dashboard**: `GET /api/incidents/` -> Loads authorized list.
- **Detail View**: `GET /api/incidents/<id>/` -> Renders incident specifics.
- **RAG & Analysis**: `GET /api/incidents/<id>/similar/` and `/api/incidents/<id>/legal-notice/` generate recommendations and statutory notices.
- **Update**: `PATCH /api/incidents/<id>/` -> Resolves the incident.

---

## 6. Request/Response Contracts

All schemas are fully detailed in [`docs/API_DOCUMENTATION.md`](file:///d:/My%20Projects/Django/Prahari/docs/API_DOCUMENTATION.md).

---

## 7. Error Catalog

| Status Code | Description | Sensitive Info Leaked? | Response Example |
|---|---|---|---|
| **400 Bad Request** | Body validation error | [NO] | `{"detail": "Error description"}` |
| **401 Unauthorized** | Missing/Invalid JWT | [NO] | `{"detail": "Authentication credentials were not provided."}` |
| **403 Forbidden** | Session unverified | [NO] | `{"status": "unauthorized", "message": "Anonymous access code verification required."}` |
| **404 Not Found** | Record not found / Tenant mismatch | [NO] | `{"detail": "Not found."}` |
| **429 Too Many Requests** | Sliding IP Rate Limit hit | [NO] | `{"error": "Rate limit exceeded..."}` |

---

## 8. Rate Limits

- **Ingestion**: 10 requests / hour / IP. [OBSERVED]
- **Verify Code**: 5 requests / minute / IP. [OBSERVED]
- **Token pair**: 5 requests / minute / IP. [OBSERVED]
- **Token refresh**: 10 requests / minute / IP. [OBSERVED]

---

## 9. Frontend API Dependencies

Fully audited and mapped inside `API_DOCUMENTATION.md`. Matches all AJAX calls inside `report_status.html` and `coordinator_detail.html`. [OBSERVED]

---

## 10. Postman Collection

- **Location**: [`docs/postman/Prahari.postman_collection.json`](file:///d:/My%20Projects/Django/Prahari/docs/postman/Prahari.postman_collection.json) [IMPLEMENTED]

---

## 11. Postman Environment

- **Location**: [`docs/postman/Prahari.postman_environment.json`](file:///d:/My%20Projects/Django/Prahari/docs/postman/Prahari.postman_environment.json) [IMPLEMENTED]

---

## 12. Documentation Files

- **API Documentation**: [`docs/API_DOCUMENTATION.md`](file:///d:/My%20Projects/Django/Prahari/docs/API_DOCUMENTATION.md) [IMPLEMENTED]

---

## 13. Validation Results

- Both Postman JSON files are validated and syntactically correct. [VERIFIED]

---

## 14. Test Results

- Total tests: 52 automated tests.
- Status: **SUCCESS** (52 passed, 0 failures). [VERIFIED]

---

## 15. Discovered Inconsistencies

- **None**. The API contracts correspond 1-to-1 with actual view behaviors.

---

## 16. Remaining API Improvements

- None. Endpoints are robustly hardened and secure.

---

## 17. Recommended Next Phase

- **Phase 4A — Frontend Modernization & UI/UX Styling pass**.
