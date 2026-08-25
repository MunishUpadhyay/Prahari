# PRAHARI - FULL TECHNICAL & ARCHITECTURE AUDIT

**Audit Date:** 2026-08-25
**Ground Truth:** Source code (not README)

---

## 1. Executive Summary

Prahari is a real-time civic incident intelligence platform built on Django 5 with a multi-agent AI pipeline. The project is significantly more complete than a typical portfolio scaffold -- it has a working 5-agent Celery pipeline, a functional ChromaDB RAG system, a WebSocket-backed coordinator dashboard, JWT-secured APIs, and a citizen-facing HTML portal.

CRITICAL GAPS:
- Multi-tenancy is broken -- the middleware always returns Tenant.objects.first(), creating no actual tenant isolation.
- PostGIS is configured but the geospatial query logic is entirely commented out and returns HTTP 501.
- The AuditLog model exists but is never written to anywhere in the codebase.
- The fallback LLM models (openai/gpt-oss-120b, openai/gpt-oss-20b) are Groq-internal models -- public availability is unverifiable from the repo.
- Zero tests exist despite test dependencies being listed in requirements.txt.
- CI/CD is completely absent.
- Webhook tenant wiring is a TODO with an explicit HTTP 501 response.
- SMS notifications are simulated -- only saved to the database, never sent.
- Agents are sophisticated sequential LLM call chains, not autonomously "agentic" in the LangGraph/ReAct sense.

The core pipeline (signal -> Celery -> 5 agents -> ChromaDB RAG -> WebSocket broadcast) is functionally implemented and the most genuinely impressive engineering achievement of the project.

**Overall Production Readiness: 4.5/10**

---

## 2. Repository Overview

```
Prahari/
ss apps/
    ss agents/          # 5 agents + BaseAgent + monkeypatching startup hooks
    ss audit/           # AuditLog model (DEFINED but NEVER USED)
    ss incidents/       # Incident model + coordinator views + API views
    ss notifications/   # SMS simulation (DB only, no actual dispatch)
    ss resources/       # Resource model + NearbyResourcesView (HTTP 501)
    ss signals/         # Signal model + citizen views + SignalIngestView
    ss tenants/         # Tenant model + TenantMiddleware (broken isolation)
ss config/
    ss asgi.py          # ProtocolTypeRouter -- HTTP + WebSocket
    ss celery.py        # Celery app factory
    ss urls.py          # Root URL config
    ss settings/
        ss base.py      # Shared settings
        ss dev.py       # SQLite, DEBUG=True, CORS open
        ss dev_nogis.py # No-GIS dev variant
        ss prod.py      # PostgreSQL/PostGIS with GDAL fallback
ss pipeline/
    ss consumers.py     # DashboardConsumer (WebSocket)
    ss routing.py       # ws/dashboard/ WebSocket route
    ss tasks.py         # 5-step Celery pipeline
ss prompts/             # 6 .txt system prompts
ss rag/
    ss chroma_db/       # Persisted SQLite vector DB
    ss ingest.py        # 887-line ingestion script
    ss retriever.py     # 3 retrieval functions
ss templates/           # 8 Django HTML templates
ss docker-compose.yml   # PostGIS + Redis services only
ss render.yaml          # Render.com deployment
ss start.sh             # Single-process production start
ss requirements.txt     # All dependencies listed
```

Key counts:
- Python files: ~30 | Templates: 8 HTML | Prompts: 6 TXT
- Models: 6 (Signal, Incident, Tenant, Resource, AuditLog, Notification)
- Celery tasks: 5 pipeline tasks + 1 notification task
- Management commands: 2 (seed_demo, ingest_knowledge_base)
- Tests: 0


---

## 3. Actual Architecture (What Actually Works)

The core pipeline:

  Citizen Form/API -> Signal.create() -> ingest_signal.delay() -> Redis Broker
                                                                        |
                                  Celery Worker (pool=solo, concurrency=1)
                                  ingest_signal -> signal.status=processing
                                  classify_domain -> SentinelAgent (Groq 70B)
                                  route_to_agents -> domain conditional:
                                    legal  -> RightsAgent + RAG(legal)
                                    health -> TriageAgent + RAG(medical)
                                    cross  -> both + conflict resolution
                                  coordination_agent -> CoordinationAgent
                                  push_to_websocket -> LanguageAgent (Hindi)
                                                    -> WebSocket broadcast
                                                    -> Notification.create()
                                                    -> ingest_incident_to_history()
                                              |                     |
                                   Incident.agent_outputs    Redis Channel Layer
                                   (JSONField all outputs)           |
                                              |          DashboardConsumer.send()
                                   Citizen polling API        Coordinator Dashboard
                                   /report/<id>/status/

---

## 4. End-to-End Data Flow (Legal Domain)

1. Citizen POSTs to /submit/ with raw_text, contact_number, preferred_language
2. citizen_views.py:citizen_submit() creates a Signal record in DB
3. Anonymous code generated if anonymous=on (SHA-256 hash stored in metadata)
4. ingest_signal.delay(signal_id) enqueued on Redis
5. Celery: ingest_signal sets signal.status = processing
6. classify_domain -> SentinelAgent.run(signal) -> Groq API -> domain set
7. route_to_agents -> domain=legal -> RightsAgent.run(signal)
   RAG: retrieve_legal_provisions(signal.raw_text, n_results=3) -> ChromaDB -> top-3 injected
   Groq LLM call -> JSON response validated/sanitized
8. Incident.objects.update_or_create(signal=signal) -- incident created with severity
9. coordination_agent -> CoordinationAgent.run() -> synthesizes brief
10. push_to_websocket -> LanguageAgent.run() -> Hindi translation (7 chunked calls)
11. ingest_incident_to_history() -> saves incident embedding to ChromaDB
12. channel_layer.group_send dashboard_{tenant_id} -> Redis pub/sub
13. DashboardConsumer.dashboard_update() pushes JSON to WebSocket clients
14. Signal status set to processed
15. send_notification.delay() if contact number -> creates Notification DB record (simulated)

---

## 5. Backend Audit

### Django App Status
| App | Purpose | Completeness |
|-----|---------|-------------|
| apps.signals | Signal ingestion, citizen portal | Functionally complete |
| apps.incidents | Incident management, coordinator portal | Mostly complete |
| apps.agents | 5-agent system + BaseAgent | Implemented |
| apps.tenants | Multi-tenancy | Model good; middleware broken |
| apps.audit | Tamper-evident audit log | Model defined; NEVER written to |
| apps.resources | Nearby resource lookup | Model OK; API returns HTTP 501 |
| apps.notifications | SMS notifications | DB simulation only |

### API Endpoints Status
| Method | URL | Auth | Status |
|--------|-----|------|--------|
| POST | /submit/ | None | Working |
| GET | /report/id/status/ | None | Working |
| GET/POST | /coordinator/dashboard/ | @login_required | Working |
| GET | /coordinator/incident/id/ | @login_required | Working |
| POST | /coordinator/incident/id/resolve/ | @login_required | Working |
| POST | /api/signals/ | JWT optional | Working |
| GET | /api/incidents/ | JWT required | Working |
| GET | /api/incidents/id/similar/ | None (AllowAny) | Working |
| GET | /api/incidents/id/legal-notice/ | None (AllowAny) | Working |
| GET | /api/resources/nearby/ | JWT required | HTTP 501 |
| POST | /api/webhooks/register/ | JWT required | HTTP 501 |
| POST | /api/auth/token/ | None | Working |
| GET | /api/docs/ | None | Swagger OK |

### Notable Issues
1. SignalIngestView.get_permissions(): No Authorization header means permissions=[]. Rate limiting is the only guard.
2. IncidentListView.get_queryset(): Code comment confirms "Stopgap tenant resolution." All authenticated users see ALL incidents.
3. SimilarIncidentsView and LegalNoticeView: permission_classes=[AllowAny]. Contact info unauthenticated-accessible.
4. coordinator_resolve_incident(): No authorization scoping beyond @login_required.
5. LegalNoticeView: Calls LegalNoticeAgent().run() synchronously -- blocking LLM call, 5-30s response time.

---

## 6. Database Audit

### Signal Model
- id: UUID PK | tenant: FK Tenant CASCADE | raw_text: TextField | image: ImageField (not actively used)
- source_type: text/image/webhook | location: PointField or JSONField (GIS conditional)
- domain: CharField | status: pending/processing/processed/failed | metadata: JSONField
- contact_number: CharField | preferred_language: default=hindi | created_at: auto_now_add
- Indexes: (tenant, status), (domain)

### Incident Model
- id: UUID PK | signal: OneToOne Signal CASCADE | severity_score: FloatField 0.0-1.0
- severity_label: low/medium/high/critical | domain: CharField | agent_outputs: JSONField
- situation_brief: TextField | recommended_resources: JSONField (DEAD -- always empty list)
- is_resolved: BooleanField | coordinator_status: pending/under_review/action_taken/resolved
- Indexes: (is_resolved), (severity_label), (domain)

### Other Models
- Tenant: SHA-256 api_key_hash + verify_api_key() method. NEVER called from any view.
- AuditLog: SHA-256 tamper-evident hash. NEVER written to from anywhere.
- Resource: GIS PointField/JSONField. Always empty (no seeded data).
- Notification: DB record created. No real SMS API called.

### Database Issues
1. N+1 on Incident.save(): Performs Incident.objects.get(pk=self.pk) to compare previous status on every save.
2. Missing updated_at on Signal: Status transitions not timestamped.
3. db.sqlite3 appears committed to repo with real demo data.
4. recommended_resources JSONField always empty -- dead field, never populated.

---

## 7. Redis / Celery Audit

Redis serves 4 roles simultaneously: Celery broker, Celery result backend, Channel layer, Rate-limit cache.

Celery config: pool=solo, concurrency=1 (single-threaded)
Result backend: django-db in dev, redis in prod
django_celery_beat installed but NO Beat schedules defined

Task chain (manual .delay(), NOT native Celery chains .si()/.chain()):
  ingest_signal -> classify_domain -> route_to_agents -> coordination_agent -> push_to_websocket

### Failure Scenarios
- LLM 429: Fallback to next model; if all fail, task raises
- LLM complete failure: Task raises; signal.status stays 'processing' FOREVER
- Redis down: Celery cannot receive tasks
- Celery worker dies mid-task: May be redelivered (acks_late not set)
- DB write fails: Chain stops; signal stuck
- WebSocket push fails: Caught with except Exception -- non-critical, task continues
- Same incident twice: update_or_create -- idempotent

CRITICAL GAP: No on_failure handler sets signal.status = 'failed'. Stuck signals detected only by 5-minute client timeout.
RETRY BUG: route_to_agents and coordination_agent have max_retries=3 but NEVER call self.retry(). Dead configuration.

---

## 8. Agent Architecture Audit

### Inventory
| Agent | Class | Line | RAG? | Monkeypatched? |
|-------|-------|------|------|----------------|
| Sentinel | SentinelAgent | agents.py:29 | No | YES (incidents/apps.py) |
| Rights | RightsAgent | agents.py:70 | YES legal | No |
| Triage | TriageAgent | agents.py:183 | YES medical | No |
| Coordination | CoordinationAgent | agents.py:292 | No | No |
| Language | LanguageAgent | agents.py:467 | No | YES (signals/apps.py) |
| LegalNotice (UNDOCUMENTED) | LegalNoticeAgent | agents.py:603 | No | No |

NOTE: README says 5 agents. Codebase has 6. LegalNoticeAgent is absent from README.

### Sentinel Agent
- Input: signal.raw_text, signal.source_type
- Output: {severity_score, severity_label, domain, escalate, reasoning}
- Monkeypatched at startup: original run() in agents.py is dead code at runtime

### Rights Agent
- Input: signal.raw_text, sentinel_result[domain]
- RAG: retrieve_legal_provisions(signal.raw_text, n_results=3) -> ChromaDB
- Output: {rights_violated, severity, legal_provisions, immediate_actions, authority_to_contact, case_strength, nearest_authority_type, legal_timeline}
- Extensive per-field type validation + fallback construction

### Triage Agent
- Input: signal.raw_text, sentinel_result[domain]
- RAG: retrieve_medical_protocols(signal.raw_text, n_results=3) -> ChromaDB
- Output: {triage_severity, primary_concern, interventions, required_facility, response_time, hospital_denial_detected, confidence, golden_window, emergency_contacts}
- Special: escalate_to_rights_agent bool -- dynamically triggers RightsAgent for cross-domain

### Coordination Agent
- Input: signal.raw_text + all prior agent outputs
- No RAG -- synthesizes existing outputs
- Output: {situation_title, overall_severity, what_is_happening, immediate_actions, resources_needed, authorities_to_notify, situation_brief, conflict_resolution, escalation_path, evidence_to_collect}

### Language Agent
- Input: coord_result dict + target_language
- Monkeypatched at startup: 7 chunked LLM calls + regex post-processing for ~30 Hindi legal/time terms
- Original run() in agents.py is dead code at runtime

### Legal Notice Agent (6th, undocumented in README)
- Input: signal.raw_text + rights_result + target_language
- Output: Raw text string (NOT JSON) -- formal legal notice document
- Called SYNCHRONOUSLY in web request cycle via LegalNoticeView

### Honest Assessment: Are These Agentic?
These are sophisticated sequential LLM call chains with domain-conditional routing, NOT agentic in the ReAct/tool-use sense.

WHAT THEY ARE: Dedicated system prompts, input/output schemas with validation, domain-conditional routing,
RAG context injection, cross-agent data flow, dynamic dispatch (Triage->Rights escalation), fallback/normalization.

WHAT THEY ARE NOT: No tool use, no function calling, no multi-step reasoning, no self-reflection,
no memory beyond single pipeline, no parallel execution, no autonomous decision-making.

Honest label: "Structured LLM pipeline with RAG augmentation and domain-conditional routing"

---

## 9. Monkeypatching Audit

Two AppConfig.ready() hooks override agent behavior at startup:
1. incidents/apps.py: Replaces BaseAgent.call_groq (adds 120B fallback) and SentinelAgent.run (domain normalization)
2. signals/apps.py: Replaces LanguageAgent.run with 173-line chunked translation implementation

Problems:
- Patches depend on import order; INSTALLED_APPS reordering can break behavior
- Original LanguageAgent.run and SentinelAgent.run in agents.py are DEAD CODE at runtime
- Testing patched vs. unpatched agents requires careful test setup
- Business logic scattered: agents.py, incidents/apps.py, signals/apps.py

Correct approach: Move all this logic directly into the agent classes in agents.py.

---

## 10. RAG Audit

### ChromaDB Collections
- legal_provisions: ~25 hardcoded Python strings (Constitution Art 21/22, CrPC, BNSS, BNS, DK Basu, consumer/labour/property law, FIR guidance)
- medical_protocols: ~12 hardcoded Python strings (START triage, MCI, sepsis, cardiac arrest, trauma, drowning, burns, pediatric, diabetic, snake bite)
- incident_history: Dynamic -- embedded at pipeline completion (self-improving knowledge loop)

### Config
- Embedding: all-MiniLM-L6-v2 (local CPU via sentence-transformers)
- Chunking: NONE -- each document is one vector (even 100-line BNSS/CrPC mapping)
- Retrieval: collection.query(query_texts=[query], n_results=3)
- Metadata filtering: Fields defined (category, act, section) but NEVER used in queries
- Distance threshold: NONE -- top-3 always returned regardless of relevance
- Query transformation: None | Reranking: None | Hybrid search: None

### RAG Quality: Prototype-level
- Documents are hardcoded strings (not real PDF ingestion pipeline)
- No chunking for long documents
- No relevance threshold (irrelevant provisions always injected)
- No evaluation dataset
- No citation tracking in LLM output

---

## 11. RAG Evaluation

No automated RAG evaluation exists anywhere in the codebase.
No evaluation datasets, no precision/recall, no Hit@K, no faithfulness metrics, no Ragas, no LangSmith.
Retrieval quality is entirely assumed, not measured.

---

## 12. Authentication and Security Audit

### Mechanisms
- Django session auth: Coordinator dashboard (@login_required) -- Working
- JWT (simplejwt): REST API, WebSocket -- Working
- Tenant API key: api_key_hash and verify_api_key() exist -- NEVER called from any view
- IP rate limiting: Redis sliding window on /api/signals/ -- Working

### Security Issues

P0 CRITICAL:
1. Cross-tenant data access: IncidentListView always uses first active tenant. Code explicitly confirms: "No real multi-tenant routing." Any authenticated user sees ALL incidents.
2. Unprotected APIs: SimilarIncidentsView and LegalNoticeView have permission_classes=[AllowAny]. Unauthenticated access to full incident data including contact info, rights violations, agent outputs.

P1 HIGH:
3. Coordinator resolve not scoped: @login_required only -- any Django user can resolve any incident.
4. JWT falls back to SECRET_KEY: If JWT_SECRET env not set, SECRET_KEY signs JWTs. Leaked SECRET_KEY = all tokens compromised.
5. Tenant API key phantom: Tenant.api_key_hash and verify_api_key() exist but are never called from anywhere.

P2 MEDIUM:
6. CORS open in dev (CORS_ALLOW_ALL_ORIGINS=True).
7. JWT in WebSocket query string -- standard for browsers, logged in server access logs.
8. No input sanitization on raw_text before LLM injection -- prompt injection risk.

---

## 13. Multi-Tenancy Audit

The ENTIRE tenant isolation implementation in apps/tenants/middleware.py:

    def get_tenant_from_request(request):
        # For demo purposes, return the first tenant
        # In production this would be resolved from JWT claims
        return Tenant.objects.first()

There is NO actual tenant isolation. Every request is assigned to the first tenant in the DB.

### Component Status
| Component | Exists? | Works? |
|-----------|---------|--------|
| Tenant model with SHA-256 API key | Yes | N/A |
| Tenant.verify_api_key() | Yes | Never called |
| TenantMiddleware | Yes | Broken (always first tenant) |
| JWT claims tenant extraction | No | Not implemented |
| User -> Tenant relationship | No | Not implemented |
| Per-tenant query scoping | No | All views see all data |

Classification: Single-tenant with multi-tenant scaffolding

---

## 14. WebSocket Audit

Connection: ws://host/ws/dashboard/?token=JWT&tenant_id=uuid
1. DashboardConsumer.connect() extracts JWT from query string
2. JWT validated via AccessToken(token) -- user fetched from DB
3. Tenant: Tenant.objects.filter(is_active=True).order_by('id').first() (stopgap)
4. Consumer joins dashboard_tenant_id group via Redis channel layer
5. await self.accept()

Push path: Celery task -> async_to_sync(channel_layer.group_send) -> Redis -> DashboardConsumer.dashboard_update() -> self.send()

Notes:
- async_to_sync in Celery: correct standard pattern
- No message acknowledgment -- fire-and-forget
- JWT in query string: standard for browser WS, logged in server access logs
- Token type: correctly passes access token (not refresh token)

---

## 15. PostGIS Audit

Configuration:
- django.contrib.gis in INSTALLED_APPS in base.py
- docker-compose.yml uses postgis/postgis:16-3.4
- prod.py falls back to plain PostgreSQL if GDAL unavailable
- Signal.location and Resource.location conditionally PointField or JSONField

Implementation: COMPLETELY COMMENTED OUT

NearbyResourcesView code:
    # TODO: implement PostGIS Distance annotation
    # from django.contrib.gis.geos import Point
    # from django.contrib.gis.db.models.functions import Distance
    logger.info("Nearby resources endpoint hit -- PostGIS query not yet wired.")
    return Response({"detail": "Geospatial query scaffold -- PostGIS wiring pending."}, status=501)

CONCLUSION: Zero geospatial queries implemented. PostGIS is a configured dependency that provides zero functional value currently.

---

## 16. Observability and Audit Module

AuditLog model: Thoughtfully designed with SHA-256 tamper-evident hash. Entire codebase search for "from apps.audit" returns ZERO results. Never imported, never used.

What IS recorded:
- agent_outputs JSONField: all 5 agents complete output
- agent_outputs["timing"]: {start, end, duration_ms} per agent

What IS NOT recorded:
- Groq API token usage (available in Groq response but never captured)
- Retrieved RAG chunks per call
- Which model was used when fallback fired
- Error details (console only)
- Request trace IDs

---

## 17. Testing Audit

Test files found: ZERO

requirements.txt includes: pytest==8.3.2, pytest-django==4.8.0, pytest-asyncio==0.23.8, factory-boy==3.3.1, coverage==7.6.1
These testing libraries are installed but the test suite does not exist.

Critical missing tests:
- Agent JSON parsing (parse_json_response): High -- LLM output is unpredictable
- Celery pipeline end-to-end: High
- WebSocket auth JWT rejection: High
- Tenant isolation: Critical (data leakage if multi-tenant attempted)
- Rate limiting: Medium
- Signal status polling API: Medium

---

## 18. Docker / Deployment Audit

docker-compose.yml: Infrastructure only (PostGIS + Redis). No Django app container.

render.yaml:
  - web service: Daphne ASGI
  - worker service: Celery (pool=solo, concurrency=1)
  - database: prahari-db (Render free PostgreSQL)

Issues:
- No Redis service in render.yaml -- REDIS_URL must be manually configured. App fails at startup if missing.
- prahari-db is plain PostgreSQL (Render free tier). PostGIS extension may not be available.
- start.sh contradiction: Starts both Celery and Daphne but render.yaml defines separate services. start.sh creates a duplicate Celery worker on the web dyno.
- ChromaDB ephemeral: rag/chroma_db/ lost on every deploy. Not automated in build command.

---

## 19. CI/CD Audit

No CI/CD pipeline exists.
No .github/ directory, no GitHub Actions, no linting (ruff/flake8/mypy), no pre-commit hooks, no automated tests.
Deployment: Render auto-deploy on push with zero automated validation.

---

## 20. Code Quality Audit

Positives: Clean app separation, BaseAgent inheritance, prompts/ externalized, UUID PKs, select_related for N+1 avoidance, TextChoices, update_fields usage.

Issues:
1. Monkeypatching in AppConfig.ready(): 173 lines of LanguageAgent replacement in signals/apps.py. Original LanguageAgent.run is dead code.
2. JSON parsing duplicated: extract_json_from_text() in tasks.py duplicates base.py:parse_json_response(). Same problem solved twice.
3. Business logic in Celery tasks: severity scoring, domain routing in pipeline/tasks.py, untestable without a worker.
4. push_to_websocket() is 200+ lines with nested helper functions.
5. Runtime class mutation in coordinator_views.py: modifying IncidentListSerializer.Meta.fields at runtime.
6. No type hints on tasks.
7. Logging inconsistency: mix of logger.info() and print() in agents.
8. Double assignment typo in ingest.py:546: collection = collection = client.get_or_create_collection(...)
9. rag/chroma_db hardcoded as relative path -- breaks if started from different directory.
10. HTTP 400 triggers LLM fallback -- "400" in str(exc) catches bad requests, masking prompt engineering bugs.

---

## 21. Supabase Investigation

Grep result: ZERO occurrences of "supabase" anywhere in the repository.
No Supabase SDK, URL, auth, or imports anywhere.
Database is PostgreSQL (production) and SQLite (development).

---

## 22. Groq / Model Investigation

Models in code:
- llama-3.3-70b-versatile: base.py:36, primary model -- Active Groq model
- openai/gpt-oss-120b: base.py:61, fallback 1 -- Groq-internal, externally unverifiable
- openai/gpt-oss-20b: base.py:62, fallback 2 -- Groq-internal, externally unverifiable

openai/gpt-oss-* models appear to be Groq-internal, not listed in public Groq documentation.
README notes llama-3.1-8b-instant was removed when decommissioned, suggesting active model maintenance.

Fallback trigger logic bug:
    is_rate_limit = (
        "429" in str(exc) or
        "rate_limit" in str(exc).lower() or
        "400" in str(exc) or   # BUG: catches HTTP 400 Bad Request
        "decommissioned" in str(exc).lower()
    )
HTTP 400 Bad Request (e.g., prompt too long, invalid params) triggers fallback instead of raising error.
This masks prompt engineering bugs.

Dual fallback redundancy: base.py:call_groq() already has 3-model fallback.
incidents/apps.py:fallback_call_groq monkeypatches call_groq() to add another wrapper.
Creates redundant and potentially conflicting logic.

---

## 23. README vs Code Consistency

| README Claim | Status | Evidence |
|-------------|--------|---------|
| 5-agent AI pipeline | Partial | 6 agents exist; LegalNoticeAgent undocumented |
| RAG over Indian legal databases | Partial | ~25 hardcoded strings, not real DB |
| ChromaDB vector store | Yes | rag/chroma_db/ SQLite-backed |
| Groq LLaMA 3.3 70B | Yes | base.py:36 |
| Fallback openai/gpt-oss-120b | Code yes | base.py:61, Groq-internal |
| Fallback openai/gpt-oss-20b | Code yes | base.py:62, Groq-internal |
| PostgreSQL 16 + PostGIS 3.4 | Partial | docker-compose has PostGIS; queries commented out |
| JWT authorization | Yes | simplejwt; REST API + WebSocket |
| Django Channels WebSocket | Yes | consumers.py working |
| Redis channel layer | Yes | Settings configured |
| Celery task queue | Yes | tasks.py working |
| Tenant isolation | NO | middleware.py:7 always first tenant |
| Audit system | NO | Model exists; never called |
| Webhook registration | NO | HTTP 501 |
| Nearby resource lookup | NO | HTTP 501; query commented out |
| English + Hindi translation | Yes | LanguageAgent + patched run |
| Live operations dashboard | Yes | WebSocket coordinator dashboard working |
| Citizen status tracking | Yes | /report/id/status/ polling working |
| Legal notice generation | Yes | LegalNoticeView + LegalNoticeAgent; synchronous |
| Anonymous reporting | Yes | SHA-256 hash + session |
| Domain conditional routing | Yes | route_to_agents working |

---

## 24. Implementation Status Matrix

FULLY IMPLEMENTED (verified from source):
Django backend + DRF, Swagger/OpenAPI, Celery pipeline, Redis (broker + cache + channels),
ChromaDB RAG, Incident history RAG, All 5 pipeline agents, LegalNoticeAgent (6th undocumented),
WebSocket broadcast, Citizen portal HTML, Coordinator dashboard HTML, JWT auth, Session auth,
IP rate limiting, Anonymous reporting, Similar incidents RAG, Demo seeding.

PARTIALLY IMPLEMENTED:
Legal knowledge base (hardcoded strings not real ingestion),
Medical knowledge base (hardcoded strings not real ingestion).

NOT IMPLEMENTED (verified absent):
Multi-tenancy (middleware broken), AuditLog (model only, never written to),
PostGIS spatial queries (commented out), Nearby resource API (HTTP 501),
Webhook registration (HTTP 501), SMS notifications (simulated DB only),
Supabase (not present), CI/CD (no .github/), Tests (zero test files),
RAG evaluation, Token usage tracking.

---

## 25. Production Readiness Scores

| Category | Score | Key Reasons |
|----------|-------|-------------|
| Backend Engineering | 6/10 | Working stack; zero tests, monkeypatching, HTTP 501 stubs |
| Database Engineering | 5/10 | Good design; N+1 on save, dead AuditLog, PostGIS unused |
| Distributed Systems | 5.5/10 | Redis multi-role correct; retry never fires, no failure handler |
| AI/LLM Engineering | 6/10 | Good fallback + validation; HTTP 400 triggers fallback bug |
| RAG | 4/10 | Correct architecture; no chunking, threshold, or evaluation |
| Agent Architecture | 5/10 | Good pipeline design; monkeypatching, dead code at runtime |
| Security | 4/10 | JWT + session correct; cross-tenant leakage, AllowAny on incidents |
| Testing | 0/10 | Zero tests |
| DevOps | 4/10 | Render config correct; ChromaDB ephemeral, start.sh contradicts render.yaml |
| Observability | 3/10 | Per-agent timing captured; AuditLog inert, no token tracking |
| Maintainability | 5/10 | Good structure; monkeypatching, duplicated logic, long functions |
| OVERALL | 4.8/10 | |

---

## 26. Strongest Engineering Aspects (Portfolio Value)

1. END-TO-END AI PIPELINE (5/5 stars)
   Signal -> Celery -> 5 LLM agents -> RAG -> WebSocket -> coordinator dashboard.
   Complete, working integration. EXCEPTIONAL for Backend and AI/GenAI interviews.

2. DOMAIN-CONDITIONAL AGENT ROUTING (4/5 stars)
   Legal skips Triage; health skips Rights; cross triggers both + conflict resolution.
   escalate_to_rights_agent dynamic dispatch shows edge-case thinking.
   GREAT AI pipeline design discussion point.

3. DUAL KNOWLEDGE BASE SEPARATION (4/5 stars)
   Two distinct ChromaDB collections queried by domain-appropriate agents.
   Demonstrates RAG domain separation. GOOD GenAI engineering interview point.

4. TAMPER-EVIDENT AUDITLOG DESIGN (4/5 stars)
   SHA-256 hash over (incident_id|action|performed_by|timestamp).
   Even though never written to, the design thinking is impressive.
   STRONG backend/security interview discussion.

5. LLM FALLBACK CHAIN WITH KEY ROTATION (4/5 stars)
   3-model fallback + 2 API keys = production-relevant reliability engineering.
   GOOD distributed systems + AI reliability discussion.

6. BILINGUAL OUTPUT ARCHITECTURE (4/5 stars)
   7 chunked LLM translation calls + 30-term regex for Hindi legal/time terms.
   Shows real-world LLM output engineering. UNIQUE AI Engineer interview angle.

7. INCIDENT HISTORY RAG (3/5 stars)
   Third ChromaDB collection grows at runtime -- self-improving knowledge loop.
   STRONG GenAI architecture discussion.

8. ANONYMOUS REPORTING WITH HASHED CODES (3/5 stars)
   SHA-256 hash in metadata; raw code shown once via session. Privacy-aware civic design.
   GOOD backend interview story.

9. ON-DEMAND LEGAL NOTICE GENERATION (3/5 stars)
   6th undocumented agent drafts formal legal notices in English/Hindi.
   IMPRESSIVE AI feature demonstrating extending agent architecture.

10. RENDER-DEPLOYABLE PRODUCTION CONFIG (3/5 stars)
    Separate web + Celery worker, env var management, HTTPS headers, WhiteNoise.
    Evidence of actual deployment experience. DEVOPS credibility.

---

## 27. Weakest Parts

P0 CRITICAL (Fix immediately for portfolio credibility):

P0-1: ZERO TESTS
Most damaging gap. Testing libraries installed but test suite does not exist.
Even 5 unit tests for parse_json_response() would be better than zero.

P0-2: MULTI-TENANCY BROKEN
Middleware says "For demo purposes" and always returns Tenant.objects.first().
Actively wrong -- a second tenant would have their data assigned to tenant 1.

P0-3: AUDITLOG NEVER WRITTEN TO
SHA-256 tamper-evident audit trail designed but completely inert.
Either wire it (minimum: incident creation and resolution events) or remove it.

P1 HIGH VALUE:

P1-1: POSTGIS QUERIES COMMENTED OUT
HTTP 501 returned. The 5-line PostGIS implementation is literally commented out.
Lowest-effort, highest-impact fix available.

P1-2: LEGALNOTICEAGENT SYNCHRONOUS IN WEB REQUEST
Blocking LLM call in Django view (5-30 second response times). Should be a Celery task.

P1-3: CHROMADB EPHEMERAL ON RENDER
rag/chroma_db/ lost on every deploy. ingest_knowledge_base should be in Render build command.

P1-4: RETRY DECORATORS NEVER TRIGGERED
route_to_agents and coordination_agent have max_retries=3 but self.retry() never called. Dead config.

P1-5: signal.status NEVER SET TO FAILED
Pipeline failures leave signals stuck in 'processing' indefinitely. Celery on_failure handler required.

P2 NICE TO HAVE:
- RAG distance threshold filtering (reject if distance > 0.75)
- Streaming LLM responses for coordinator dashboard
- Groq token usage capture per agent call
- Real SMS via Twilio or MSG91

---

## 28. What Should NOT Be Changed

1. BaseAgent abstract class -- Clean inheritance with prompt_name, model, max_tokens. Do not replace with LangChain.
2. ChromaDB persistence strategy -- Local ChromaDB is appropriate for this scale.
3. Celery + Redis architecture -- Correct choice. Solo pool fits Render constraints.
4. Dual auth (session for coordinator, JWT for API) -- Correct pattern for two different clients.
5. Externalized system prompts (prompts/ directory) -- Excellent for prompt engineering iteration.
6. Domain routing logic -- Domain.choices enum and route_to_agents conditional dispatch is well-designed.
7. Anonymous code generation -- SHA-256 hash in metadata + session display is correct privacy implementation.
8. Structured output validation per agent -- Defensive programming, keep it.

---

## 29. Upgrade Roadmap

PHASE 1: Foundation Fixes (1-2 weeks) -- HIGHEST PRIORITY
1. Write tests: parse_json_response() unit tests, agent integration test with mocked Groq, pipeline E2E test, WebSocket auth rejection tests.
2. Wire AuditLog: write on incident created, incident resolved, and pipeline complete events.
3. Fix signal.status=failed: add Celery on_failure handler to each pipeline task.
4. Fix retry: add self.retry(exc=exc) in exception handlers for route_to_agents and coordination_agent.
5. Remove monkeypatching: move patched_language_agent_run into LanguageAgent.run() in agents.py. Move SentinelAgent domain normalization into the class. Delete overrides from apps.py.

PHASE 2: Multi-Tenancy (1 week) -- VERY HIGH BACKEND VALUE
1. Add Profile model with tenant = ForeignKey(Tenant) extending Django User.
2. Fix TenantMiddleware to resolve from request.user.profile.tenant.
3. Add tenant_id claim to JWT via custom token serializer.
4. Scope all API queries to signal__tenant=request.tenant.

PHASE 3: PostGIS Query (3 days) -- HIGH VALUE, LOW EFFORT
1. Uncomment the 5-line PostGIS distance query in NearbyResourcesView.
2. Seed demo resources with lat/lon in seed_demo.py.
3. Add spatial index via migration.

PHASE 4: Observability (1 week) -- HIGH AI/GENAI INTERVIEW VALUE
1. Capture Groq usage.prompt_tokens and usage.completion_tokens in call_groq().
2. Wire AuditLog (from Phase 1).
3. Add trace ID per pipeline execution.
4. Expose /api/incidents/id/audit/ endpoint.

PHASE 5: RAG Quality (1 week) -- HIGH GENAI INTERVIEW VALUE
1. Add distance threshold in retriever.py (filter if distance > 0.75).
2. Chunk the large legal mapping document into ~5 smaller chunks.
3. Add 5-query evaluation dataset as a pytest test verifying retrieval hits.

PHASE 6: CI/CD (3 days) -- CREDIBILITY
1. .github/workflows/test.yml -- pytest on push.
2. .github/workflows/lint.yml -- ruff.
3. Pre-commit hooks.

PHASE 7: Real SMS (1 day) -- FEATURE COMPLETION
1. Replace Notification.objects.create() simulation with twilio_client.messages.create().

Total: 4-6 weeks of focused engineering.

---

## 30. Final Assessment

CURRENT STATE:
Prahari is a functional full-stack AI pipeline application demonstrating real distributed systems
and LLM engineering, substantially beyond a tutorial clone. The core pipeline works end-to-end.

CRITICAL GAPS visible to experienced interviewers:
- Zero tests (testing libraries installed but unused)
- Broken multi-tenancy (middleware always returns first tenant)
- HTTP 501 stubs for PostGIS and webhooks
- AuditLog designed but never used
- Monkeypatching as primary extension mechanism
- ChromaDB on ephemeral Render filesystem

TARGET STATE (after roadmap):
- 30+ tests with mocked LLM calls and coverage reporting
- Working multi-tenant isolation with proper data scoping
- Real PostGIS spatial queries
- RAG with threshold filtering and evaluation dataset
- AuditLog tracking every pipeline step
- Token usage captured per agent call
- CI/CD with automated test runs on every push
- Clean agent code without monkeypatching

---

## Questions for the Developer

1. Are openai/gpt-oss-120b and openai/gpt-oss-20b verified to work on your Groq account in production?
2. Is the Render deployment currently live? Is ChromaDB being re-ingested after deploys?
3. Does the Render PostgreSQL instance have the PostGIS extension enabled? If not, Signal.location PointField migration created the wrong column type in production.
4. Is db.sqlite3 in .gitignore? It appears committed, containing real demo data.
5. Why two overlapping fallback mechanisms (base.py:call_groq AND incidents/apps.py:fallback_call_groq)? Was the monkeypatch meant to replace the base logic or stack on top of it?
6. The start.sh starts both Celery and Daphne, but render.yaml defines separate web + worker services. Which one is actually used in production?
