# Prahari 🛡️

Prahari is a real-time civic intelligence system designed to empower citizens, support NGOs, and assist coordinators by connecting legal, healthcare, and emergency domains. It ingests raw civic signals (text, images, webhooks), dynamically routes them through a multi-agent AI pipeline using specialized legal RAG and medical protocols, and translates the analysis into English or Hindi in real time. Connected coordinators can monitor incoming alerts via a live WebSocket dashboard, escalate issues, generate legal notices, follow evidence checklists, and manage cases E2E, while citizens can submit reports and check statuses securely—even anonymously via unique 6-character access codes.

---

## Tech Stack

- **Core Framework**: Django 5 + Django REST Framework (DRF)
- **Real-Time Streaming**: Django Channels 4 (ASGI/Daphne)
- **Message Broker & Channel Layer**: Redis 7
- **Task Queue & Pipeline Routing**: Celery 5
- **Database**: PostgreSQL 16 + PostGIS 3.4 (Geospatial data support)
- **Vector Database**: ChromaDB (RAG embedding storage)
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Primary LLM**: Groq LLaMA 3.3 70B (`llama-3.3-70b-versatile`)
- **Fallback LLM**: Groq LLaMA 3.1 8B (`llama-3.1-8b-instant` fallback routing)
- **Token Authentication**: JSON Web Tokens (JWT)

---

## Features

- **5-Agent Pipeline**: Specialized AI agents (*Sentinel*, *Rights*, *Triage*, *Coordination*, *Language*) run in a Celery-backed sequential processing chain.
- **WebSocket Operations Dashboard**: Real-time incident streaming, visual notifications, and status monitoring for organization coordinators.
- **Multi-lingual Support**: Citizen report status translates dynamically into English and Hindi.
- **RAG Knowledge Base**: Semantic search over Indian legal provisions (CrPC, IPC, BNSS, BNS) and medical protocols (Trauma Golden Hour, Stroke FAST, STEMI, etc.).
- **Legal Notice Generator**: One-click professional legal draft generator with words limits constraints and actionable, measurable demands.
- **Evidence Collection Guide**: Tailored evidence lists showing what to collect, why it is important, and how to obtain it.
- **Anonymous Submission Mode**: Submit signals securely without a contact number, protected behind a SHA256 hashed 6-character access code and client-side page lockout.
- **Case Outcome Predictor**: Analyzes historical cases and calculates resolution rates, average severity levels, and typical resolutions from similar database records.
- **Multi-Tenant API Security**: Dedicated API key validation, domain scoping, and JWT authorization for third-party client integrations.

---

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository_url>
   cd Prahari
   ```
2. **Copy `.env.example` to `.env` and fill values**:
   ```bash
   cp .env.example .env
   ```
3. **Start local infrastructure (Docker)**:
   ```bash
   docker compose up -d
   ```
4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```
6. **Ingest legal and medical knowledge base**:
   ```bash
   python manage.py ingest_knowledge_base
   ```
7. **Populate demo signals and process through agent pipeline**:
   ```bash
   python manage.py seed_demo
   ```
8. **Start the Celery worker** (Terminal 2):
   ```bash
   .venv\Scripts\celery -A config worker --loglevel=info --pool=solo
   ```
9. **Start Daphne ASGI Web Server** (Terminal 3):
   ```bash
   .venv\Scripts\daphne -b 0.0.0.0 -p 8000 config.asgi:application
   ```
10. **Open local application**:
    - URL: http://localhost:8000/

---

## Environment Variables

The following environment variables configure the Prahari environment inside `.env`:

- `SECRET_KEY`: Standard Django secret key used for session cryptographic signing.
- `DEBUG`: Boolean flag (`True` or `False`) to enable/disable debug mode.
- `ALLOWED_HOSTS`: Comma-separated list of allowed host/domain names that this Django site can serve.
- `DB_NAME`: PostgreSQL database name.
- `DB_USER`: PostgreSQL user.
- `DB_PASSWORD`: PostgreSQL password.
- `DB_HOST`: PostgreSQL database host address.
- `DB_PORT`: PostgreSQL database port (default `5432` or `5433`).
- `REDIS_URL`: Redis URL used for the Celery broker and Channels layer.
- `JWT_SECRET`: Secret key used for signing JSON Web Tokens.
- `GROQ_API_KEY`: Primary Groq API key for LLaMA model agents.
- `GROQ_API_KEY_2`: Secondary fallback Groq API key used to bypass rate-limiting.
- `SITE_URL`: Optional absolute base URL of the site used for constructing share links.

---

## API Documentation

Interactive API docs are available at:
`http://localhost:8000/api/docs/`
