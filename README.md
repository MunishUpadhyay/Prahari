# Prahari 🛡️

**Real-time civic intelligence backend** — connecting legal, healthcare, and emergency domains through AI-driven signal processing.

---

## Overview

Prahari ingests raw civic signals (text, images, webhooks), classifies them by domain, runs them through specialised AI agents, and streams live incident updates to connected dashboards via WebSocket.

```
Signal Ingest → Celery Pipeline → 5 AI Agents → Incident → WebSocket Push
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web framework | Django 5 + Django REST Framework |
| WebSocket | Django Channels 4 + Redis channel layer |
| Task queue | Celery 5 + Redis |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| AI agents | Groq API (LLaMA 3) |
| Vector store | ChromaDB (RAG) |
| Auth | JWT (djangorestframework-simplejwt) |

---

## Project Structure

```
prahari/
├── config/                   # Django settings, ASGI, WSGI, Celery
│   └── settings/
│       ├── base.py           # Shared settings
│       ├── dev.py            # Development overrides
│       └── prod.py           # Production overrides
├── apps/
│   ├── signals/              # Signal ingestion — POST /api/signals/
│   ├── agents/               # 5 AI agent classes
│   ├── incidents/            # Incident tracking — GET /api/incidents/
│   ├── resources/            # Geo resource lookup — GET /api/resources/nearby/
│   ├── tenants/              # Multi-tenant mgmt — POST /api/webhooks/register/
│   └── audit/                # Tamper-evident audit trail
├── pipeline/
│   ├── tasks.py              # Celery task chain (5 steps)
│   ├── consumers.py          # WebSocket DashboardConsumer
│   └── routing.py            # WebSocket URL routing
├── rag/
│   ├── ingest.py             # Document → ChromaDB ingestion
│   └── retriever.py          # RAG query interface
└── prompts/                  # System prompts for each agent
    ├── sentinel.txt
    ├── rights.txt
    ├── triage.txt
    ├── coordination.txt
    └── language.txt
```

---

## Quick Start (Local Development)

### 1. Clone and set up virtual environment

```bash
git clone <repo-url>
cd prahari
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Start infrastructure (Docker required)

```bash
docker compose up -d
```

This starts:
- **PostgreSQL 16 + PostGIS 3.4** on `localhost:5432`
- **Redis 7** on `localhost:6379`

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your GROQ_API_KEY and other secrets
```

### 4. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Start the development server

```bash
# ASGI server (supports WebSockets)
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Or standard Django dev server (HTTP only)
python manage.py runserver
```

### 6. Start Celery worker

```bash
celery -A config worker --loglevel=info
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/token/` | Obtain JWT token pair |
| `POST` | `/api/auth/token/refresh/` | Refresh JWT access token |
| `POST` | `/api/signals/` | Ingest a new civic signal |
| `GET` | `/api/incidents/` | List incidents (tenant-scoped) |
| `GET` | `/api/incidents/<id>/` | Incident detail with agent outputs |
| `GET` | `/api/resources/nearby/` | Geospatial resource lookup |
| `POST` | `/api/webhooks/register/` | Register webhook for tenant |

### WebSocket

```
ws://localhost:8000/ws/dashboard/
```

Receives live incident update messages:
```json
{
  "type": "incident.update",
  "incident_id": "<uuid>",
  "severity_label": "high",
  "domain": "emergency",
  "situation_brief": "...",
  "is_resolved": false
}
```

---

## Celery Task Chain

```
ingest_signal(signal_id)
  └─► classify_domain(signal_id)      [SentinelAgent]
        └─► route_to_agents(signal_id) [domain-specific agents]
              └─► coordination_agent(signal_id) [CoordinationAgent + LanguageAgent]
                    └─► push_to_websocket(incident_id) [Channels group_send]
```

---

## AI Agents

| Agent | Prompt | Output |
|-------|--------|--------|
| `SentinelAgent` | `prompts/sentinel.txt` | Severity score, domain, escalation flag |
| `RightsAgent` | `prompts/rights.txt` | Applicable rights, legal provisions, actions |
| `TriageAgent` | `prompts/triage.txt` | Triage level, hospital referral, indicators |
| `CoordinationAgent` | `prompts/coordination.txt` | Dispatch order, resource recommendations |
| `LanguageAgent` | `prompts/language.txt` | Plain-language situation brief |

---

## Multi-Tenancy

Each organisation (Tenant) has:
- A unique API key (stored as SHA-256 hash — raw key shown only on creation)
- An optional webhook URL for receiving incident push notifications
- Scoped access to their own Signals, Incidents, and Resources

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port |
| `REDIS_URL` | Redis connection URL |
| `JWT_SECRET` | JWT signing key |
| `GROQ_API_KEY` | Groq API key for LLM calls |

---

## License

MIT
