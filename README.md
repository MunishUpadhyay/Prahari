# Prahari 🛡️ — Real-Time Autonomous Emergency Response & Civic Intelligence Platform

[![Build & Test Status](https://img.shields.io/badge/pytest-78%2F78%20passing-brightgreen)](https://github.com/MunishUpadhyay/Prahari)
[![Framework](https://img.shields.io/badge/Django-5.0.6-092E20?logo=django)](https://www.djangoproject.com/)
[![Database](https://img.shields.io/badge/PostgreSQL-Supabase-336791?logo=postgresql)](https://supabase.com/)
[![Deployment](https://img.shields.io/badge/Render-ASGI%20%2B%20Celery-46E3B7?logo=render)](https://render.com/)

Prahari is a multi-tenant, autonomous emergency response platform that ingests raw civic signals (distress reports, medical emergencies, crime signals), processes them through a sequential **5-Agent AI pipeline** backed by **Retrieval-Augmented Generation (RAG)** over legal and medical knowledge bases, and streams real-time updates to an operations coordinator dashboard.

---

## 📌 Problem Statement

During civic emergencies or law-and-order incidents, citizens often face severe bottlenecks:
- **Delayed Intervention**: High signal volume overwhelms human operators, causing critical triage delays.
- **Privacy & Safety Concerns**: Victims often hesitate to file reports due to fear of identity exposure or lack of anonymous reporting options.
- **Legal & Medical Information Gap**: First responders and citizens lack immediate access to statutory provisions (BNS/BNSS/IPC) or golden-hour medical protocols.

Prahari solves these challenges by combining automated AI triage, strict privacy-first anonymous report tracking (via hashed Return Keys), legal/medical RAG retrieval, and real-time WebSocket dashboard streaming for emergency coordinators.

---

## ✨ Key Capabilities

1. **Autonomous 5-Agent AI Processing Pipeline**: Sequential pipeline categorizes domain/severity, extracts legal rights & statutory provisions, evaluates medical urgency, synthesizes actionable coordination plans, and translates outputs to the citizen's preferred language (English or Hindi).
2. **Retrieval-Augmented Generation (RAG)**: Integrates ChromaDB vector store with Sentence Transformers (`all-MiniLM-L6-v2`) to query Indian statutory codes (BNS, BNSS, IPC, CrPC) and emergency medical trauma protocols.
3. **Anonymous Reporting & Hashed Return Keys**: Citizens can file anonymous distress signals and receive a high-entropy Return Key (`PRAH-XXXX-...`) hashed using SHA-256 for secure future status lookup without revealing identity.
4. **Citizen Account Recovery & Password Reset**: Secure Django-native token-based account recovery with enumeration protection (always returning a neutral response to prevent account harvesting).
5. **Real-Time Operations Dashboard**: Coordinator portal featuring WebSocket live updates, tracking ID search (`PRAH-YYYYMMDD-XXXX`), status filters (`Pending`, `Under Review`, `Action Taken`, `Resolved`), and responsive mobile card layout.
6. **Production Hardening**: Rate-limited endpoints (brute-force protection on Return Keys and tokens), WhiteNoise static asset serving, HSTS, secure cookies, and Supabase IPv4 Supavisor connection pooling for Render compatibility.

---

## 🏗️ High-Level System Architecture

```mermaid
graph TD
    classDef citizen fill:#4f46e5,stroke:#818cf8,stroke-width:2px,color:#fff;
    classDef django fill:#090d16,stroke:#6366f1,stroke-width:2px,color:#fff;
    classDef celery fill:#06b6d4,stroke:#22d3ee,stroke-width:2px,color:#fff;
    classDef rag fill:#10b981,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef db fill:#1e293b,stroke:#475569,stroke-width:2px,color:#f8fafc;

    CitizenIn["Citizen Web / API Signal Ingestion"]:::citizen --> DjangoWeb["Django ASGI Server (Daphne)"]:::django
    DjangoWeb --> SaveDB["Save Signal to PostgreSQL"]:::db
    SaveDB --> EnqueueCelery["Enqueue Asynchronous Celery Task"]:::celery

    subgraph AI Pipeline Execution
        EnqueueCelery --> Sentinel["1. Sentinel Agent: Domain & Severity Triage"]:::celery
        Sentinel --> Rights["2. Rights Agent: Legal Provision Audit"]:::celery
        Sentinel --> Triage["3. Triage Agent: Emergency Medical Audit"]:::celery
        
        Rights --> LegalRAG["ChromaDB Legal Vector Search"]:::rag
        Triage --> MedicalRAG["ChromaDB Medical Vector Search"]:::rag
        
        LegalRAG --> Coord["4. Coordination Agent: Action Plan Synthesis"]:::celery
        MedicalRAG --> Coord
        
        Coord --> Lang["5. Language Agent: EN/HI Translation"]:::celery
    end

    Lang --> CommitDB["Update DB & Emit Audit Log"]:::db
    CommitDB --> WSBroadcast["Broadcast WebSocket (Channels / Redis)"]:::django
    WSBroadcast --> CoordDashboard["Coordinator Operations Dashboard"]:::django
    CommitDB --> CitizenStatus["Citizen Tracking Timeline"]:::citizen
```

---

## 🛠️ Technology Stack

| Layer | Component / Technology | Purpose in Prahari |
| :--- | :--- | :--- |
| **Backend Core** | Django 5.0.6 & DRF 3.15 | Core MVC architecture, REST API, authentication & session management |
| **ASGI / Real-Time** | Django Channels 4.1 & Daphne 4.1 | Asynchronous WebSocket server for live incident dashboard updates |
| **Task Queue** | Celery 5.4 & Redis 5.0 | Background queue executing the 5-agent AI pipeline asynchronously |
| **Database** | PostgreSQL 16 (via Supabase) | Primary relational database storing signals, incidents, users, audit logs |
| **Connection Pooler** | Supavisor (Session Pooler) | IPv4-compatible connection pooler routing Render traffic to Supabase |
| **Vector Database** | ChromaDB 0.6.3 | Local vector store executing cosine similarity search over legal/medical texts |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Generating dense 384-dimensional vector embeddings |
| **AI LLM Engine** | Groq API (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) | High-speed LLM inference with automatic multi-model and key failover |
| **Static Serving** | WhiteNoise 6.7 | Compressed manifest static asset delivery in production |
| **Testing** | pytest 8.3 & pytest-django 4.8 | Automated test suite validating API, identity, celery, RAG, and hardening |

---

## 👥 User Workflows

### 1. Citizen Workflow
- **Signal Submission**: Submit emergency signals with title, description, location, domain (Legal, Health, Crime, General), and optional images.
- **Anonymous Reporting**: Toggle anonymous mode to submit without registering. Receive a high-entropy Return Key (`PRAH-XXXX-...`) to track status privately.
- **Identified Reporting**: Authenticated citizens view a consolidated history of all past signals and linked anonymous reports under `/profile/`.
- **Account Recovery**: Secure password reset flow (`/citizen/password-reset/`) using Django token generators with enumeration safety.

### 2. Coordinator Workflow
- **Dashboard Overview**: Monitor incoming incidents streamed live via WebSockets.
- **Status Filter Controls**: Filter incidents by status (`All`, `Pending`, `Under Review`, `Action Taken`, `Resolved`).
- **Tracking ID Search**: Locate incidents using human-readable tracking IDs (`PRAH-YYYYMMDD-XXXX`).
- **Incident Resolution**: Review AI-generated legal provisions, medical triage recommendations, and action plans, attach coordinator notes, and resolve incidents.

---

## 🔒 Security & Privacy Features

- **Return Key Hashing**: Return Keys are stored using SHA-256 hashes. Raw keys are displayed only once upon submission.
- **Brute-Force Protection**: Return Key lookup and token endpoints are protected by Redis/cache rate limiting (5 attempts / 15-minute lockout).
- **Account Enumeration Protection**: Password reset requests always return neutral success responses regardless of email existence.
- **Sanitized Public APIs**: Internal LLM reasoning logs, raw prompt templates, and coordinator notes are stripped from public citizen responses.
- **Production Hardening**: Enforced SSL redirects, HSTS (`SECURE_HSTS_SECONDS=31536000`), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, and `SameSite=Lax`.

---

## 📁 Project Directory Structure

```text
Prahari/
├── apps/
│   ├── agents/             # 5-Agent AI pipeline logic, LLM wrappers & fallbacks
│   ├── audit/              # Operations audit log tracking pipeline execution latency
│   ├── incidents/          # Incidents backend, coordinator views, WebSocket routing
│   ├── notifications/      # Notification dispatchers
│   ├── resources/          # Resource directory & equipment pools
│   ├── signals/            # Signal ingestion, citizen views, profile & password reset
│   └── tenants/            # Multi-tenant isolation layer
├── config/                 # Django settings (base.py, dev.py, prod.py), ASGI, Celery, URLs
├── docs/                   # System documentation & postman collections (audits archived locally)
├── pipeline/               # Celery processing queue tasks and task coordinator
├── prompts/                # Plaintext system prompts loaded by AI Agents
├── rag/                    # ChromaDB vector store ingestion & retriever logic
├── static/                 # CSS & JavaScript assets
├── templates/              # HTML layout templates (glassmorphism UI)
├── tests/                  # Automated pytest test suite (78 tests)
├── DEPLOYMENT.md           # Production deployment & operations guide
├── manage.py               # Django CLI entrypoint
├── render.yaml             # Render Infrastructure-as-Code Blueprint
└── requirements.txt        # Python package dependencies
```

---

## 💻 Local Development Setup

### Prerequisites
- Python 3.10+
- Redis Server (local or Docker)
- PostgreSQL (optional for dev, SQLite supported in dev mode)

### Installation Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/MunishUpadhyay/Prahari.git
   cd Prahari
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```

5. **Run Database Migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Initialize Knowledge Base (RAG Ingestion)**:
   ```bash
   python manage.py ingest_knowledge_base
   ```

7. **Run Automated Tests**:
   ```bash
   pytest
   ```

8. **Start Application Servers**:
   - **Terminal 1 (Daphne Web Server)**:
     ```bash
     daphne -b 127.0.0.1 -p 8000 config.asgi:application
     ```
   - **Terminal 2 (Celery Worker)**:
     ```bash
     celery -A config worker --loglevel=info --pool=solo
     ```

---

## 🔑 Environment Variables Reference

Configure the following environment variables in production:

| Variable | Description | Example / Placeholder |
| :--- | :--- | :--- |
| `DJANGO_SETTINGS_MODULE` | Active settings module | `config.settings.prod` |
| `SECRET_KEY` | Secret key for cryptographic signing | `your-production-secret-key` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgres://user:pass@aws-0-region.pooler.supabase.com:6543/postgres` |
| `REDIS_URL` | Redis broker and cache URL | `redis://default:pass@redis-host:6379/0` |
| `ALLOWED_HOSTS` | Allowed HTTP host domain names | `prahari.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for HTTPS forms | `https://prahari.onrender.com` |
| `SITE_URL` | Base application URL | `https://prahari.onrender.com` |
| `GROQ_API_KEY` | Primary Groq AI API Key | `gsk_your_primary_key` |
| `GROQ_API_KEY_2` | Secondary Groq API Key (Failover) | `gsk_your_secondary_key` |

---

## 🚀 Production Deployment Overview

Prahari is packaged for deployment on **Render** using [`render.yaml`](file:///d:/My%20Projects/Django/Prahari/render.yaml):

- **Web Service (`prahari-web`)**: Daphne ASGI server handling HTTP & WebSockets with WhiteNoise static serving.
- **Worker Service (`prahari-celery`)**: Celery background worker processing AI pipelines.
- **Database**: External Supabase PostgreSQL connected via Supavisor Session Pooler (port `6543`) for dual-stack IPv4 compatibility.
- **Health Checks**: Live orchestrator health probes configured at `/health/` and `/api/health/`.

For step-by-step deployment instructions, refer to [`DEPLOYMENT.md`](file:///d:/My%20Projects/Django/Prahari/DEPLOYMENT.md).

---

## ⚠️ Important Limitations & Scope Notes

- **Transactional Email**: Password reset tokens and notification dispatches currently log to console/stub backend in development. Production deployments require configuring standard SMTP environment variables.
- **Geospatial Queries**: Nearby resource searches use bounding-box math fallbacks when native PostGIS extension is not enabled on the host database.
- **Supabase Free Tier**: Free tier Supabase databases pause after 7 days of inactivity; production deployment requires periodic pinging or Pro tier to maintain continuous uptime.

---

## 📄 Verification & License

- **Test Suite Status**: **78 / 78 passing tests** (`pytest`).
- **License**: MIT License.
