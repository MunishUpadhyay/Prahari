# Prahari API Documentation

This document describes the authoritative API contract, schemas, authentication, and access control models for Prahari.

---

## 1. Architecture Overview

Prahari is an incident response and decision support platform operating across **legal**, **medical**, and **emergency** domains. Its API is built using Django and Django REST Framework (DRF), and integrates with a Celery background task processing pipeline, Redis broker, and ChromaDB vector store for semantic retrieval (RAG).

```
   [Citizen API]               [Coordinator API]
        │                             │
        ▼                             ▼
   Rate Limited /               JWT Authenticated
   Public Ingest                       │
        │                             ▼
        ▼                      Tenant Isolated Queries
  Celery Pipeline ───────► (Incident / Signal DB States)
```

---

## 2. Base URL

In development, the API is available locally at:
```http
http://127.0.0.1:8000
```
In production, the base URL is dynamically configured in environment variables (`SITE_URL`). All endpoints use absolute paths.

---

## 3. Authentication

### A. Coordinator JWT Token Authentication
Coordinator endpoints require a valid JSON Web Token (JWT) passed in the `Authorization` header:
```http
Authorization: Bearer <access_token>
```

#### 1. Obtain Token Pair
- **Endpoint**: `POST /api/auth/token/`
- **Rate Limit**: 5 requests per minute per IP.
- **Request Body**:
  ```json
  {
    "username": "coordinator_username",
    "password": "coordinator_password"
  }
  ```
- **Success Response (200 OK)**:
  ```json
  {
    "refresh": "eyJhbGciOi...",
    "access": "eyJhbGciOi..."
  }
  ```
- **Access Token Lifetime**: 1 Hour.
- **Refresh Token Lifetime**: 7 Days (supports token rotation & blacklisting).

#### 2. Refresh Token
- **Endpoint**: `POST /api/auth/token/refresh/`
- **Rate Limit**: 10 requests per minute per IP.
- **Request Body**:
  ```json
  {
    "refresh": "refresh_token_jwt"
  }
  ```
- **Success Response (200 OK)**:
  ```json
  {
    "access": "new_access_token_jwt",
    "refresh": "rotated_refresh_token_jwt"
  }
  ```

### B. Citizen Session Authentication
Citizen report status and polling endpoints are session-bound to the client browser via standard Django cookies. Anonymous signals require verifying an access code once per session to view reports.

---

## 4. Citizen API Flow

A citizen reports an incident anonymously or publicly:

```
[Citizen] ──(POST /submit/ or /api/signals/)──► [Signal Ingested]
                                                      │
                                                      ▼
[Poll /status/ (200 OK)] ◄──(POST /verify-code/) ◄── [Received Code] (6-char)
```

1. **Submit Signal**: Citizen submits form (Raw text, optional location/contact).
2. **Retrieve Signal ID & Access Code**: The API creates the Signal and returns a UUID and a cryptographically secure 6-character uppercase access code.
3. **Verify Tracking Code**: If anonymous, the client POSTs the 6-character code to `/api/signals/<signal_id>/verify-code/`. On success, the backend sets the session verification flag `request.session[f"verified_{signal.id}"] = True`.
4. **Poll Status**: The client polls `GET /report/<signal_id>/status/` using AJAX. The backend checks the session flag for anonymous signals and returns the structured pipeline status.

---

## 5. Coordinator API Flow

1. **Login & JWT**: The coordinator requests tokens at `/api/auth/token/`.
2. **List Incidents**: Requests `GET /api/incidents/` (returns incidents belonging to the authorized tenant).
3. **Get Incident**: Requests `GET /api/incidents/<id>/`.
4. **Similar Incidents**: Requests `GET /api/incidents/<id>/similar/` (queries ChromaDB for semantic similarities and historical resolution rates).
5. **Generate Legal Notice**: Requests `GET /api/incidents/<id>/legal-notice/` (drafts notice letters using BNS/BNSS citations).
6. **Resolve/Update**: PATCHes `coordinator_status` or `coordinator_notes` at `/api/incidents/<id>/`.

---

## 6. Authorization Model

- **Citizen Domain Isolation**: Verification is key-scoped to the specific Signal UUID in the session. Validating Code A grants access **ONLY** to Signal A. Querying Signal B status remains blocked (returns `403 Forbidden`).
- **Coordinator Tenant Isolation**: Scoped globally via `get_authorized_tenant(request)`. All statistics, incident lists, detail view retrievals, outcomes, and legal notice generation filter by:
  `Incident.objects.filter(signal__tenant=tenant)`
- Any coordinator attempting to fetch or mutate an incident belonging to another tenant is blocked with a clean `404 Not Found` response.

---

## 7. Rate Limiting

Rate limiting is enforced at the IP level using a sliding-window cache:
- **Signal Ingest API**: 10 requests per hour.
- **Access Code Verification**: 5 requests per minute.
- **JWT Token Obtain**: 5 requests per minute.
- **JWT Token Refresh**: 10 requests per minute.

---

## 8. Error Handling & Catalog

Prahari uses standard HTTP status codes. Error payloads return formatted JSON without exposing database tracebacks or internal metadata.

| Status Code | Description | Trigger Example | Response Body |
|---|---|---|---|
| **400 Bad Request** | Schema/Validation Error | Invalid request payload fields | `{"detail": "Error description"}` |
| **401 Unauthorized** | Missing/Invalid JWT | Call protected API without token | `{"detail": "Authentication credentials were not provided."}` |
| **403 Forbidden** | Anonymous Access Denied | Polling status without verify-code | `{"status": "unauthorized", "message": "Anonymous access code verification required."}` |
| **404 Not Found** | Record not found/Tenant mismatch | Requesting invalid UUID or another tenant's incident | `{"detail": "Not found."}` |
| **429 Too Many Requests** | Rate Limit Exceeded | Exceeding 5 verify-code attempts in a minute | `{"error": "Rate limit exceeded. Maximum 10 requests per hour."}` |
| **500 Internal Error** | Server Exception | Database down or server error | Standard server error page (DEBUG=False hides stack traces) |

---

## 9. Frontend API Usage Map

| Template | API Endpoint | Method | Trigger/Purpose | Expected Fields |
|---|---|---|---|---|
| `report_status.html` | `/report/${signalId}/status/` | GET | Polling status of pipeline processing | `status`, `steps`, `result` |
| `report_status.html` | `/api/signals/${signalId}/verify-code/` | POST | Verifies tracking code for anonymous view | `valid` |
| `report_status.html` | `/api/incidents/${incidentId}/similar/` | GET | Shows similar statistics inside progress portal | `similar_incidents`, `outcome_stats` |
| `report_status.html` | `/api/incidents/${incidentId}/legal-notice/` | GET | Renders notice draft for download | `notice` |
| `coordinator_detail.html`| `/coordinator/incident/${id}/resolve/` | POST | Marks incident resolved in HTML portal | `status`, `incident_id`, `is_resolved` |
| `coordinator_detail.html`| `/api/incidents/${incidentId}/similar/` | GET | Renders historical stats in coordinator portal| `similar_incidents`, `outcome_stats` |
| `coordinator_dashboard.html`| `/api/incidents/${id}/` | PATCH | Updates coordinator notes and status | Full deserialized Incident object |

---

## 10. Complete Endpoint Reference

### A. POST /api/signals/
- **Purpose**: Citizen signal submission endpoint.
- **Auth**: Optional JWT.
- **Request Body**:
  ```json
  {
    "raw_text": "Describe the emergency incident...",
    "source_type": "text",
    "location": "Latitude/Longitude or address string",
    "metadata": {
      "contact_number": "optional contact number"
    }
  }
  ```
- **Success (201 Created)**:
  ```json
  {
    "id": "e4ee9b91-ba48-458e-8b89-2d824fa53d44",
    "raw_text": "Describe the emergency incident...",
    "source_type": "text",
    "location": "Latitude/Longitude or address string",
    "status": "pending",
    "domain": "cross",
    "metadata": {
      "contact_number": "optional contact number"
    },
    "created_at": "2026-08-28T15:00:00Z"
  }
  ```

### B. POST /api/signals/<signal_id>/verify-code/
- **Purpose**: Verifies the 6-character anonymous tracking code.
- **Request Body**:
  ```json
  {
    "code": "CODEAA"
  }
  ```
- **Success (200 OK)**:
  ```json
  {
    "valid": true
  }
  ```

### C. GET /report/<signal_id>/status/
- **Purpose**: Polling status endpoint for progress screens.
- **Success (200 OK)**:
  ```json
  {
    "signal_id": "e4ee9b91-ba48-458e-8b89-2d824fa53d44",
    "status": "processed",
    "steps": {
      "received": true,
      "classified": true,
      "analyzed": true,
      "coordinated": true,
      "translated": true
    },
    "result": {
      "incident_id": "b8913443-6d11-40ca-a915-71e9c8736008",
      "severity_label": "high",
      "severity_score": 0.7,
      "domain": "legal",
      "brief_en": "Human-readable legal summary...",
      "legal_provisions": [
        {
          "code": "BNS",
          "section": "115",
          "title": "Voluntary hurt...",
          "legacy_code": "IPC",
          "legacy_section": "323"
        }
      ]
    }
  }
  ```

### D. GET /api/incidents/
- **Purpose**: Retrieves a paginated list of incidents for the authorized tenant.
- **Auth**: JWT Bearer.
- **Success (200 OK)**:
  ```json
  {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "b8913443-6d11-40ca-a915-71e9c8736008",
        "signal": "e4ee9b91-ba48-458e-8b89-2d824fa53d44",
        "severity_score": 0.7,
        "severity_label": "high",
        "domain": "legal",
        "is_resolved": false,
        "coordinator_status": "pending",
        "created_at": "2026-08-28T15:00:00Z"
      }
    ]
  }
  ```

### E. GET/PATCH /api/incidents/<id>/
- **Purpose**: Get detail or update coordinator status/notes.
- **Auth**: JWT Bearer.
- **Success (200 OK)**:
  ```json
  {
    "id": "b8913443-6d11-40ca-a915-71e9c8736008",
    "signal": "e4ee9b91-ba48-458e-8b89-2d824fa53d44",
    "severity_score": 0.7,
    "severity_label": "high",
    "domain": "legal",
    "agent_outputs": {},
    "situation_brief": "Brief situation text...",
    "is_resolved": false,
    "coordinator_status": "under_review",
    "coordinator_notes": "Reviewed by coordinator.",
    "status_updated_at": "2026-08-28T15:05:00Z"
  }
  ```
