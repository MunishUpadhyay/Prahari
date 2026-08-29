# Phase 4D — Citizen Journey & Report UX Audit Report

This report documents the detailed findings of the citizen reporting product lifecycle, user experience design system, security constraints, and recommended flow enhancements.

---

## 1. Executive Summary

- **Objective**: Audit and reconcile the citizen user journey from initial submission to status tracking, ensuring Prahari operates with safe and intuitive user interactions for emergency public-safety scenarios.
- **Key Finding**: The current visual progress stepper displays a misleading 3-step sequence ("Submit Report" → "Get Code" → "Verify & Poll") that is both logically and behaviorally inaccurate. In reality, the browser session is automatically authenticated right after submission, meaning no manual verification is needed for the current user session.
- **Recommendation**: Adopt **Option B** (frictionless automatic authentication for active sessions, with the access code presented solely as a return/recovery credential).
- **Compliance**: This phase is an **Audit Only**. No files or database schemas were modified, and all 52 unit/integration tests remain passing.

---

## 2. Actual Current Citizen Flow

Through direct source code inspection, the actual execution sequence for a citizen is tracked as:

1. **Visit Home Page**:
   - The user loads the dashboard [`templates/home.html`](file:///d:/My%20Projects/Django/Prahari/templates/home.html).
   - Serves options to "Report an Incident" or input a Prahari ID (tracking number) to track an existing case. `[OBSERVED]`
2. **Submit Incident Form**:
   - Renders [`templates/submit.html`](file:///d:/My%20Projects/Django/Prahari/templates/submit.html) via `GET /submit/`.
   - Offers fields for raw text description, location details, contact number, language, and an **Anonymous** toggle. `[OBSERVED]`
3. **Submission POST Request**:
   - Triggers `citizen_submit` in [`apps/signals/citizen_views.py`](file:///d:/My%20Projects/Django/Prahari/apps/signals/citizen_views.py).
   - Generates a new `Signal` in the database. `[OBSERVED]`
4. **Access Credentials Setup**:
   - **For Anonymous Reports**: A 6-character alphanumeric access code is generated via `secrets.token_urlsafe(4)[:6].upper()`. Its SHA-256 hash is saved to `signal.metadata['anonymous_code']`, the plain-text code is set in `request.session[f"anon_code_{signal.id}"]`, and the active session is automatically marked verified: `request.session[f"verified_{signal.id}"] = True`. `[OBSERVED]`
   - **For Regular Reports**: No code is generated, and no session verification parameters are modified. `[OBSERVED]`
5. **Background Pipeline Execution**:
   - The Celery task `ingest_signal.delay(signal.id)` is enqueued. `[OBSERVED]`
6. **Submission Redirect**:
   - Redirects to `/report/PRAH-YYYYMMDD-XXXX/` based on date and first 4 characters of the Signal UUID. `[OBSERVED]`
7. **Report Status Page Load**:
   - Triggers `citizen_report_status` view.
   - Pops the raw access code from the session to pass to the template context once: `raw_code = request.session.pop(session_key, None)`. `[OBSERVED]`
   - Renders [`templates/report_status.html`](file:///d:/My%20Projects/Django/Prahari/templates/report_status.html).
8. **Pipeline Polling**:
   - AJAX calls poll the status endpoint `/report/<signal_id>/status/` every 6 seconds until classification/analysis finishes. `[OBSERVED]`

---

## 3. Submission Lifecycle

The citizen lifecycle is executed as:

```
[Citizen Input] ➔ Form POST ➔ Signal Created ➔ [Anonymous Check]
                                                      |
                                                      +-- (Yes) ➔ Generate Code ➔ Hash & Save ➔ Set Session verified_UUID=True
                                                      |
                                                      +-- (No)  ➔ Proceed directly
                                                      |
                                                    Celery delay() Enqueued
                                                      |
                                           Redirect: /report/PRAH-YYYYMMDD-XXXX/
```

- **Verification Stance**: The submitting browser is **automatically verified** for anonymous reports during the post request (setting the session variable `verified_{signal.id} = True`). The citizen is **never** explicitly asked to enter the access code immediately after redirecting. `[VERIFIED]`

---

## 4. Access Code Lifecycle

- **Generation**: Created during anonymous POST submissions only. `[OBSERVED]`
- **Storage**: The SHA-256 hash is saved permanently in `Signal.metadata`. The raw text code is set in the Django session, then deleted immediately upon rendering the redirect page: `request.session.pop(f"anon_code_{signal.id}")`. `[OBSERVED]`
- **Display Status**: Shown **only once** to the citizen as a success banner on the first status page load. Refreshing or navigating away clears it permanently. `[VERIFIED]`
- **Requirements**: Not required immediately after submitting (session is active). It is required only when returning later in a fresh browser session. `[VERIFIED]`
- **Recovery**: If lost, it cannot be recovered as the plain-text value is not retained anywhere in the backend database. `[OBSERVED]`

---

## 5. Session Verification Lifecycle

- **Verification Points**:
  - Automatically configured inside `citizen_submit` POST: `request.session[f"verified_{signal.id}"] = True`. `[OBSERVED]`
  - Manually configured after validating raw code inside `SignalVerifyCodeView`: `request.session[f"verified_{signal.id}"] = True`. `[OBSERVED]`
- **Invalidation**: The "Done — Close Session" button deletes the browser's local `sessionStorage` key. However, **no backend invalidation is performed**, meaning `request.session[f"verified_{signal.id}"]` remains `True` in the Django session. `[OBSERVED]`

---

## 6. Status Page Authorization

- **HTML Page (`GET /report/<signal_id>/`)**: Has **no backend authorization checks** and serves the status page skeleton to any client. `[OBSERVED]`
- **AJAX Status API (`GET /report/<signal_id>/status/`)**: **Strictly authorized** for anonymous reports. It checks `request.session.get(f"verified_{signal.id}")` and returns `403 Forbidden` if missing or false. `[OBSERVED]`

### API Response States `[VERIFIED]`
- **Unverified**: Returns `403 Forbidden` with `{"status": "unauthorized", "message": "Anonymous access code verification required."}`.
- **Verified & Processing**: Returns `200 OK` with `{"status": "processing", "steps": {...}, "result": null}`.
- **Verified & Processed**: Returns `200 OK` with `{"status": "processed", "steps": {...}, "result": {...}}`.
- **Verified & Failed**: Returns `200 OK` with `{"status": "failed", "steps": {...}}`.
- **Nonexistent**: Returns `404 Not Found`.

---

## 7. Returning Citizen Flow

1. **Input tracking key**: Users enter a Prahari ID or UUID on the home page.
2. **Navigate**: Form triggers `navigateToReport()`, redirecting the browser to `/report/<ID>/`. `[OBSERVED]`
3. **Verification Check**:
   - `report_status.html` reads `is_anonymous = true`.
   - Checks client-side `sessionStorage` for `prahari_verified_{signal.id}`.
   - If empty, hides report layout and displays a secure 6-character code input wrapper. `[OBSERVED]`
4. **Code Validation**:
   - User inputs code, sending `POST /api/signals/<signal_id>/verify-code/`.
   - On success, sets Django session variable `verified_{signal.id} = True`, updates client `sessionStorage` to `true`, reveals report layout, and starts status polling. `[VERIFIED]`

---

## 8. Current Stepper Accuracy

- **Verdict**: **INACCURATE / MISLEADING** `[RECOMMENDATION]`
- **Why**:
  - The stepper implies the user must complete "Get Code" and "Verify & Poll" sequentially after submitting. In practice, they are verified immediately and go straight to polling.
  - For non-anonymous users, "Get Code" and "Verify" are completely irrelevant, yet they are shown statically, causing severe confusion.

---

## 9. UX Problems

1. **Immediate Code Verification Misconception**: Users think they must enter their code immediately to start analysis, when in fact they are already authorized. `[RECOMMENDATION]`
2. **One-Time Visibility Loss**: Displaying the code only once on the status page without a prior warning means stressed users might miss copying it. `[RECOMMENDATION]`
3. **Tracking ID vs Access Code Confusion**: "Report ID" and "Access Code" are presented similarly. Stressed users struggle to identify which one is public and which is private. `[RECOMMENDATION]`
4. **Static Stepper for Different Flows**: Regular (non-anonymous) users see empty steps about codes they never received. `[RECOMMENDATION]`
5. **No Backend Session Invalidation on Logout**: Leaving the browser verified on the backend after the user clicks "Done" is a potential security vulnerability. `[RECOMMENDATION]`

---

## 10. Security Constraints

- **Access Token Expose Protection**: Plain-text codes are never stored in databases or cookies; verification relies solely on SHA-256 hashes. `[OBSERVED]`
- **Brute-Force Rate Limiting**: The `verify-code` API and Signal status views enforce IP-based rate limiting to prevent code enumeration. `[OBSERVED]`

---

## 11. Option A vs Option B

- **Option A (Forced manual code entry immediately after submit)**: Creates a high-friction barrier. Under stress, forcing users to type a code to view their urgent report status is poor UX. `[RECOMMENDATION]`
- **Option B (Frictionless automatic verification, showing code as recovery key)**: Much better. It matches the current backend architecture where the browser is authorized immediately, and only requires code entry if returning later. `[RECOMMENDATION]`

---

## 12. Recommended Citizen Journey

Adopt **Option B** with these UX enhancements:

1. **Incident Submit**:
   - The user fills out the form.
   - If "Anonymous" is toggled, a warning appears *before submission*: *"Keep your access code safe! It is only shown once."*
2. **Submission Redirect**:
   - The current session is automatically verified.
   - The status page loads directly, displaying the **Report ID** (for public references) and the **Access Code** (specifically highlighted as a *Return Password/Recovery Key*).
3. **Status Polling**:
   - Clear progressive steps showing agent pipeline status.
4. **Done / Close Session**:
   - Clicking "Done" calls a backend endpoint to clear `request.session[f"verified_{signal.id}"]` and redirect to Home.

---

## 13. Proposed Screen-by-Screen UX

### Screen 1: Submit Page
- A simple progressive form.
- Stepper is replaced with a simple visual indicator showing: `1. Submit Report ➔ 2. Live Response`.
- If "Anonymous" check is toggled:
  - Displays a warning banner: `🔒 Anonymous Mode active. We will provide a 6-character access key on the next page. Write it down to track this case later.` `[RECOMMENDATION]`

### Screen 2: Live Status & Recovery (First Load)
- Banners split into two columns:
  - **Left**: `📋 Public Case ID: PRAH-YYYYMMDD-XXXX` (Use this for referencing).
  - **Right (Highlighted Card)**: `🔑 Private Return Key: XK7P2M` (Write this down! It will not be shown again). `[RECOMMENDATION]`
- If regular (non-anonymous):
  - Hides the "Private Return Key" card entirely. `[RECOMMENDATION]`

### Screen 3: Returning Citizen Track
- Home page tracking panel redirects to status.
- If anonymous & unverified:
  - Displays a clean lock screen requesting the 6-character Key.
  - Submitting it verification redirects to the report. `[RECOMMENDATION]`

---

## 14. Required Backend Changes

- **Logout / Session Clear Route**: Create `POST /api/signals/<signal_id>/close-session/` (or similar) to pop `verified_{signal.id}` from the backend session. `[RECOMMENDATION]`

---

## 15. Required Frontend Changes

- **Update Stepper logic**: Conditionally render steps based on whether the report is anonymous or regular. `[RECOMMENDATION]`
- **Warning on Submit Page**: Warn about one-time key display when anonymous mode is checked. `[RECOMMENDATION]`
- **Session termination action**: Update the "Done" click handler to post to the session-close endpoint before redirecting. `[RECOMMENDATION]`

---

## 16. Test Cases Required `[RECOMMENDATION]`

1. Verify that regular (non-anonymous) signals do not generate access codes and poll `/status/` immediately.
2. Verify that clicking the "Done" button makes a request to close the session, and subsequent status checks fail (returning 403) until the code is re-entered.

---

## 17. Risks

- **Stressed User Actions**: Stressed users may close the window before saving their key, losing access. Clear copy-to-clipboard actions and alerts must be implemented. `[RECOMMENDATION]`

---

## 18. Phase 4D Implementation Plan

### Step 1: Backend Session Invalidation
- Create a backend view/action to invalidate the session verification flag upon session closure.

### Step 2: Submit Page Stepper & Alert Upgrades
- Hide/show steps conditionally based on the "Anonymous" toggle.
- Add pre-submission warnings for anonymous reporting.

### Step 3: Status Page Layout Reconstruction
- Implement the split layout separating public Report ID and private Return Key.
- Update "Done" button logic to trigger backend session invalidation.
