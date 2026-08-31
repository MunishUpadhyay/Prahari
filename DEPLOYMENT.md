# Prahari — Production Deployment & Operations Guide

**System:** Prahari (Real-Time Civic Intelligence & Incident Response Platform)  
**Version:** 1.0.0 (Phase 4M.1 Production Release)  
**Target Infrastructure:** Render.com / Linux Container Environments  

---

## 1. Required Architecture & Services

Production deployment of Prahari requires four distinct runtime services:

1. **Django Web Service (ASGI):** High-concurrency ASGI web application powered by **Daphne** to handle HTTP traffic and real-time WebSocket Channels connections.
2. **Celery Worker Process:** Asynchronous background worker (`celery -A config worker --pool=solo --concurrency=1`) executing the 5-stage AI processing pipeline and RAG retrieval tasks.
3. **PostgreSQL Database:** Relational database storing tenants, signals, incidents, user accounts, audit logs, and notification records.
4. **Redis Data Store & Message Broker:** In-memory data store functioning as the Celery task broker, Celery result backend, Django cache store, and Channels layer backend.

---

## 2. Production Environment Variables Reference

Configure the following environment variables in your deployment dashboard or `.env` environment configuration.

### Mandatory Environment Variables

| Variable | Description | Example / Placeholder |
|:--- |:--- |:--- |
| `DJANGO_SETTINGS_MODULE` | Active Django settings module | `config.settings.prod` |
| `SECRET_KEY` | Strong cryptographic secret key | `django-insecure-prod-key-xyz123...` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed domains | `prahari.onrender.com,api.prahari.org` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated list of HTTPS trusted origins | `https://prahari.onrender.com,https://api.prahari.org` |
| `SITE_URL` | Base URL of the deployed application | `https://prahari.onrender.com` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgres://user:password@hostname:5432/dbname` |
| `REDIS_URL` | Redis connection URL | `redis://default:password@hostname:6379/0` |
| `GROQ_API_KEY` | Primary Groq AI API Key | `gsk_lf...` |

### Optional Environment Variables

| Variable | Description | Default / Placeholder |
|:--- |:--- |:--- |
| `GROQ_API_KEY_2` | Secondary Groq API Key for failover | `gsk_sy...` |
| `SECURE_HSTS_SECONDS` | HTTP Strict Transport Security duration | `31536000` (1 Year) |
| `DEBUG` | Enable debug mode (MUST BE `False` in Prod) | `False` |
| `PYTHON_VERSION` | Python runtime version | `3.10.0` |

---

## 3. Build & Start Commands

### Web Service (Django + Daphne)
- **Build Command:**
  ```bash
  pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python -c "from rag.ingest import ingest_legal_documents, ingest_medical_protocols; ingest_legal_documents(); ingest_medical_protocols()"
  ```
- **Start Command:**
  ```bash
  daphne -b 0.0.0.0 -p $PORT config.asgi:application
  ```

### Celery Worker Service
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  celery -A config worker --loglevel=info --pool=solo --concurrency=1
  ```

---

## 4. Render Blueprint Configuration (`render.yaml`)

The repository includes a ready-to-deploy Infrastructure-as-Code specification in [`render.yaml`](file:///d:/My%20Projects/Django/Prahari/render.yaml):

```yaml
services:
  - type: web
    name: prahari-web
    runtime: python
    buildCommand: |
      pip install -r requirements.txt
      python manage.py collectstatic --noinput
      python manage.py migrate
      python -c "from rag.ingest import ingest_legal_documents, ingest_medical_protocols; ingest_legal_documents(); ingest_medical_protocols()"
    startCommand: >
      daphne -b 0.0.0.0 -p $PORT
      config.asgi:application
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: config.settings.prod
      - key: DATABASE_URL
        fromDatabase:
          name: prahari-db
          property: connectionString
      - key: REDIS_URL
        sync: false
      - key: SECRET_KEY
        generateValue: true
      - key: GROQ_API_KEY
        sync: false
      - key: ALLOWED_HOSTS
        sync: false
      - key: CSRF_TRUSTED_ORIGINS
        sync: false
      - key: SITE_URL
        sync: false
    healthCheckPath: /health/

  - type: worker
    name: prahari-celery
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: >
      celery -A config worker
      --loglevel=info --pool=solo
      --concurrency=1
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: config.settings.prod
      - key: DATABASE_URL
        fromDatabase:
          name: prahari-db
          property: connectionString
      - key: REDIS_URL
        sync: false
      - key: SECRET_KEY
        sync: false
      - key: GROQ_API_KEY
        sync: false

databases:
  - name: prahari-db
    plan: free
```

---

## 5. Health Checks & Production Monitoring

Prahari provides two dedicated health check endpoints for cloud load balancers and orchestrator liveness/readiness probes:

1. **Lightweight Liveness Check (`GET /health/`):** Returns HTTP 200 `{"status": "ok", "service": "prahari"}`. Used by Render health probes.
2. **System Readiness Check (`GET /api/health/`):** Validates PostgreSQL database connectivity, Redis connection, and Celery pipeline availability. Returns HTTP 200 on healthy or HTTP 503 on database/redis failure.

---

## 6. Static File Serving

Static assets (CSS, JavaScript, branding SVGs) are managed via **WhiteNoise** with manifest compression (`CompressedManifestStaticFilesStorage`). Executing `python manage.py collectstatic --noinput` during the build step populates `staticfiles/` for efficient direct delivery.

---

## 7. Security Enforcement Checklist

Before deploying to production, confirm that:
- [x] `DEBUG` is set to `False`.
- [x] `SECRET_KEY` is randomized and kept secret.
- [x] `ALLOWED_HOSTS` matches your domain name(s).
- [x] `CSRF_TRUSTED_ORIGINS` includes `https://` schema.
- [x] `SESSION_COOKIE_SECURE = True` and `CSRF_COOKIE_SECURE = True` (enforced automatically in `prod.py`).
- [x] `SECURE_HSTS_SECONDS` is set to `31536000`.
- [x] Return Key verification rate limiting (5 attempts / 15-minute lockout) is active via Redis/Cache.
