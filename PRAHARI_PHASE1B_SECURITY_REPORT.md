# Prahari — Phase 1B Security Report

This document reports the implementation details and verification results for Phase 1B: Security API Endpoint Protection.

---

## 1. Changes Made

* **File Modified:** [`apps/incidents/views.py`](file:///d:/My%20Projects/Django/Prahari/apps/incidents/views.py)
* **Classes Modified:**
  * `SimilarIncidentsView` (Line 89)
  * `LegalNoticeView` (Line 193)
* **Modifications:** Changed `permission_classes = [AllowAny]` to `permission_classes = [IsAuthenticated]` for both classes.

---

## 2. Previous Behavior

Before the modifications, both `SimilarIncidentsView` and `LegalNoticeView` were publicly accessible (`AllowAny` permission). Any anonymous request from the internet could query:
* `/api/incidents/<id>/similar/` to retrieve a list of similar past incidents, their domain, severity labels, and brief details.
* `/api/incidents/<id>/legal-notice/` to trigger legal notice drafts containing Indian law citations and incident details.

---

## 3. New Behavior

Both endpoints now require active authentication. Requests are handled as follows:
* **Anonymous Request (No Auth):** Blocked, returns `HTTP 401 Unauthorized`.
* **Invalid/Expired JWT Token:** Blocked, returns `HTTP 401 Unauthorized`.
* **Valid JWT Token:** Extracted via Django REST Framework's simplejwt middleware. The request proceeds to the view's business logic, returning `HTTP 200 OK`.

---

## 4. Tests

We updated `tests/test_api.py` to assert the new permissions. The updated test files cover:
* `test_similar_incidents_view_authentication`:
  * Anonymous client gets `HTTP 401 Unauthorized`.
  * Client with invalid JWT token (`Bearer invalid_token`) gets `HTTP 401 Unauthorized`.
  * Client with a valid, dynamically generated JWT token gets `HTTP 200 OK`.
* `test_legal_notice_view_authentication`:
  * Anonymous client gets `HTTP 401 Unauthorized`.
  * Client with invalid JWT token gets `HTTP 401 Unauthorized`.
  * Client with a valid, dynamically generated JWT token gets `HTTP 200 OK` and reads notice content.

---

## 5. Test Results

* **Total Tests Run:** 12
* **Passed:** 12
* **Failed:** 0
* **Skipped:** 0
* **Errors:** 0

All security tests pass successfully.

---

## 6. Internal Usage & Design Conflict

During Step 5's inspection, we searched for references to these endpoints in the codebase and identified a design conflict:
* **Citizen Status Page:** [`templates/report_status.html`](file:///d:/My%20Projects/Django/Prahari/templates/report_status.html) calls `/api/incidents/${incidentId}/similar/` (line 1103) and `/api/incidents/${incidentId}/legal-notice/` (line 2144) using client-side JavaScript.
* **Impact:** Since the citizen tracking portal is a public, unauthenticated portal, the citizen browser does not possess a JWT token. Consequently, anonymous citizens checking their report status will now be blocked from seeing similar cases and generating legal notice drafts (the endpoints will return `HTTP 401 Unauthorized`).
* **Mitigation / Next Step:** This design conflict is flagged for Phase 2. We should resolve it either by relocating legal notice generation to the coordinator-only dashboard or by introducing secure, single-use tracking tokens for citizens to authenticate their specific report status views.

---

## 7. Security Notes

* **Authentication vs. Authorization:** Phase 1B enforces **Authentication** (ensuring the caller has a valid, active Django account/JWT token). It does **not** implement tenant-level multi-tenant database row scoping (Authorization boundaries).
* **Scope:** All authenticated users can query these views. Fine-grained per-tenant boundary authorization checks will be implemented in Phase 2.

---

## 8. Files Changed

* `apps/incidents/views.py` (Modified)
* `tests/test_api.py` (Modified)

---

## 9. Production Safety

* **No secrets or credentials** are exposed.
* **No real Groq client calls** were executed.
* **No Supabase PostgreSQL production database connection** was made.
* **No Render configuration** was modified.
