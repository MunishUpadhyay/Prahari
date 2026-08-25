# Prahari — Deployment & Integration Investigation

## 1. Render Architecture

The production application deployment is configured across separate service components on Render. The process architecture and orchestration are structured as follows:

```text
Render
├── Web Service (prahari-web)
│   └── Daphne (ASGI server)
├── Worker Service (prahari-celery)
│   └── Celery worker (pool=solo, concurrency=1)
├── PostgreSQL (prahari-db)
│   └── Render Managed PostgreSQL (Free tier)
└── Redis (External Host)
    └── Redis Connection (Broker + Channels + Cache)
```

### Web Service
* **Start Command:** `daphne -b 0.0.0.0 -p $PORT config.asgi:application` (defined in render.yaml).
* **Server Type:** Daphne (ASGI application server).
* **Port:** Injected dynamically by Render via the `$PORT` environment variable.
* **Environment settings:** `config.settings.prod` (configured via `DJANGO_SETTINGS_MODULE` env var).

### Worker Service
* **Start Command:** `celery -A config worker --loglevel=info --pool=solo --concurrency=1` (defined in render.yaml).
* **Pool/Concurrency:** Single-threaded execution (`--pool=solo --concurrency=1`).
* **Broker:** Redis (resolved using the `REDIS_URL` environment variable).
* **Isolation:** Configured as a completely separate Render Background Worker service named `prahari-celery`.

### Database
* **Database URL:** Provided dynamically via the `DATABASE_URL` environment variable.
* **Hosting Details:** The production database is a Render Managed PostgreSQL instance (`prahari-db`) on the free plan, which dynamically injects its connection string into both the Web and Worker services.
* **Supabase Code:** No source code or configuration files reference Supabase endpoints.

### Redis
* **Source:** Configured via the `REDIS_URL` environment variable.
* **Hosting Details:** The `render.yaml` specification defines `REDIS_URL` as a manual entry (`sync: false`), meaning the developer must provide an external Redis connection string (e.g. from Upstash, Aiven, or a manually created Redis service on Render).
* **Requirement:** Required by both the Web service (for ASGI channel layers and cache-based rate limiting) and the Celery worker (for the task broker and result backend).

---

## 2. PostGIS Production Configuration

An inspection of the database settings and migration files reveals the following configuration:

* **Engine:** Dynamically resolved at runtime in settings/prod.py:
  Since Render's native Python runtime does not include the system-level GDAL, GEOS, or PROJ library dependencies, the import will fail, forcing Django to run on the standard `django.db.backends.postgresql` engine and remove `django.contrib.gis` from `INSTALLED_APPS`.
* **Database URL:** Configured via `DATABASE_URL` using `dj-database_url`.
* **PostgreSQL Backend:** Defaults to standard PostgreSQL when GDAL is missing.
* **Database Extensions:** No script or hook forces database-level extension enablement (`CREATE EXTENSION postgis`).
* **Migrations:** The migration history in `apps/signals/migrations/0002_...` and `apps/resources/migrations/0002_...` alters `location` fields directly to `models.JSONField`. Therefore, the database tables created by migrations contain standard JSONB/Text fields, NOT PostGIS spatial Geometry columns.
* **Geospatial Dependencies:** Since Django dynamically falls back to the standard PostgreSQL backend and changes fields to JSONField, GDAL is not required for production startup or standard operation.

> "Production PostGIS availability cannot be verified from source code."

### How to Verify PostGIS on Production
To safely check if PostGIS is enabled on the active database, the developer should connect to their Render database using the external database connection string via `psql` or a database viewer (DBeaver, pgAdmin) and run the following queries:

1. **Check active extensions:**
   ```sql
   SELECT extname, extversion FROM pg_extension WHERE extname = 'postgis';
   ```
2. **Retrieve version summary:**
   ```sql
   SELECT postgis_full_version();
   ```
   If either query returns a valid version, the PostGIS extension is installed and ready. If not, the extension is missing from the database.

---

## 3. Supabase Investigation

A thorough check of the repository was conducted to trace any references to Supabase.

> "No Supabase integration exists in the repository."

### External Configuration Context
While the codebase contains zero direct SDK or helper code for Supabase, the following external endpoints are supported via standard environment configurations:
* **Database:** The database URL parses any standard PostgreSQL connection link via `dj-database-url`. If the developer has a Supabase project, they can point the `DATABASE_URL` environment variable directly to their Supabase PostgreSQL connection pool/string.
* **Authentication:** No external auth integrations exist. All sessions and JWT tokens are managed locally.
* **Storage:** No external blob storage is configured. Media files are handled locally.

---

## 4. Groq Fallback Architecture

Groq client connections and failover loops are implemented across two redundant layers in the codebase:

```
Request Cycle
    ↓
[Layer 2] incidents/apps.py: fallback_call_groq() [Outer Monkeypatch Wrapper]
    ↓
[Layer 1] agents/base.py: BaseAgent.call_groq() [Inner Core Model/Key Loop]
    ↓
Groq Client API
```

### Layer 1: BaseAgent.call_groq()
The inner core implementation iterates through a model list (`models_to_try = [self.model, "openai/gpt-oss-120b", "openai/gpt-oss-20b"]`) and rotates across available keys (`[GROQ_API_KEY, GROQ_API_KEY_2]`).
If an exception is raised, it checks if it fits the rate limit/deprecation criteria:
If True, it logs a warning and tries the next key or model. If False (e.g. 401/403/500), it raises the exception immediately.

### Layer 2: incidents/apps.py fallback_call_groq()
This outer wrapper intercepts exceptions raised by `original_call_groq`. If the exception indicates a rate limit:
It logs a warning, temporarily sets `self.model = "openai/gpt-oss-120b"`, and runs `original_call_groq` a second time before restoring the original model string.

---

### Architectural Clarifications
* **Active Method at Runtime:** `fallback_call_groq` (defined in apps/incidents/apps.py) is invoked first, wrapping the original `BaseAgent.call_groq`.
* **Redundancy:** The fallback logic is duplicated. The monkeypatch was likely created to add rate-limiting safety without realizing that the underlying `BaseAgent.call_groq` already featured an internal model fallback and key rotation loop.
* **Attempt Order & Model Escalation:**
  If the agent runs under default settings (starting with model `llama-3.3-70b-versatile`):
  1. `llama-3.3-70b-versatile` using API Key 1
  2. `llama-3.3-70b-versatile` using API Key 2
  3. `openai/gpt-oss-120b` using API Key 1
  4. `openai/gpt-oss-120b` using API Key 2
  5. `openai/gpt-oss-20b` using API Key 1
  6. `openai/gpt-oss-20b` using API Key 2
  If all 6 options raise rate limit exceptions, `original_call_groq` raises an exception, which is caught by the outer monkeypatch. The monkeypatch sets `self.model = "openai/gpt-oss-120b"` and triggers `original_call_groq` again, which repeats the attempts:
  7. `openai/gpt-oss-120b` using API Key 1
  8. `openai/gpt-oss-120b` using API Key 2
  9. `openai/gpt-oss-120b` using API Key 1 (duplicate)
  10. `openai/gpt-oss-120b` using API Key 2 (duplicate)
  11. `openai/gpt-oss-20b` using API Key 1
  12. `openai/gpt-oss-20b` using API Key 2
* **Key Rotation:** Up to 2 API keys (`GROQ_API_KEY` and `GROQ_API_KEY_2`) are loaded from settings. The inner loop tests each key sequentially for the active model before moving to the next model.
* **Error Handling Specifics:**
  * **429 (Rate Limit):** Caught by both layers. Logs warning, rotates key, or shifts model.
  * **400 (Bad Request):** Caught as rate limit inside Layer 1 (due to `"400" in str(exc)`), which incorrectly triggers model rotation. Not caught as rate limit in Layer 2.
  * **401 (Unauthorized) / 403 (Forbidden) / 500 (Server Error) / Timeout:** Halts execution and immediately raises the exception.
  * **Model Decommissioning:** Caught as rate limit in Layer 1 (due to `"decommissioned"` check), triggering fallback.

---

## 5. Groq Model Verification

| Model ID | Location | Purpose | Fallback Order | Source Code Status | Current Groq Availability |
|---|---|---|---|---|---|
| `llama-3.3-70b-versatile` | `base.py:36` | Primary Agent LLM | 1st | Active Primary | Active (announced for deprecation in late August 2026) |
| `openai/gpt-oss-120b` | `base.py:61`, `incidents/apps.py:33` | Secondary Fallback | 2nd | Active Fallback | Active (OpenAI open-weights MoE supported on Groq) |
| `openai/gpt-oss-20b` | `base.py:62` | Tertiary Fallback | 3rd | Active Fallback | Active (OpenAI open-weights MoE supported on Groq) |
| `llama-3.1-8b-instant` | README.md | Removed reference | N/A | Decommissioned | Deprecated / Removed from Groq platform |

---

## 6. Developer Actions Required

To fully resolve the deployment and database configurations, the developer must perform the following actions inside their external dashboards and accounts:

1. **Verify PostGIS Extension status:**
   Connect to the production database (`prahari-db`) on Render and run:
   ```sql
   SELECT extname, extversion FROM pg_extension WHERE extname = 'postgis';
   ```
2. **Provision External Redis:**
   Since managed Redis is not configured in `render.yaml`, provision a Redis instance (e.g., via Upstash or a separate Render Redis service) and add the `REDIS_URL` variable to both Web and Celery worker settings on Render.
3. **Verify Groq API Key Tiers:**
   Access the GroqCloud Dashboard to check whether their API keys have access permission for the high-reasoning `openai/gpt-oss-120b` and `openai/gpt-oss-20b` models.
4. **Automate Vector Store Ingestion:**
   Since ChromaDB is stored on Render's ephemeral disk, add the knowledge-base ingestion command to the build script in Render to ensure data is parsed on deployment:
   ```bash
   python manage.py collectstatic --noinput && python manage.py migrate && python rag/ingest.py
   ```
