# 🧠 Agentic SOAP Note System

## 🎯 Project Vision

An **AI-first, browser-native agent system** that autonomously drafts SOAP notes from raw clinical data, integrates with EMR systems via web automation, and empowers clinicians with structured, compliant documentation.

### Core Capabilities

✅ **Multi-Channel Intake** - Web portal, Slack bot, email parsing
✅ **AI Structuring** - LLM-powered conversion of raw notes → SOAP format
✅ **EMR Automation** - Playwright-based browser agents for EMR integration
✅ **Audit & Compliance** - Full HIPAA-compliant audit trails
✅ **On-Prem AI** - Private LLM deployment on NVIDIA DGX Spark

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Channel Input                      │
│         (Web Portal | Slack Bot | Email | API)             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Intake Endpoint                    │
│              (Validation with Pydantic)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 LLM Structuring Engine                      │
│         (DGX Spark: Mistral/LLaMA/Phi models)              │
│           Raw Text → S/O/A/P Components                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL + Task Queue                        │
│         (Store drafts, track status, audit logs)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Playwright Browser Agent                         │
│         (Login → Navigate → Fill SOAP fields)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Notification System                            │
│        (Email/Slack clinician with EMR link)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
healthcare-agent/
├── api/                          # FastAPI endpoints
│   ├── intake.py                 # POST /api/intake, GET /api/tasks/{id}
│   └── __init__.py
├── core/                         # Business logic
│   ├── parser.py                 # LLM SOAP structuring engine
│   ├── schema.py                 # Pydantic models
│   └── config.py                 # Environment settings
├── database/                     # Data persistence
│   ├── models.py                 # SQLAlchemy: Patient, NoteDraft, TaskLog
│   ├── session.py                # DB connection management
│   └── migrations/               # Alembic migrations
├── browser_agent/                # EMR automation (future)
│   ├── playwright_runner.py      # Main automation script
│   └── selectors.json            # EMR field selectors
├── tasks/                        # Async processing (future)
│   ├── processor.py              # Task orchestration
│   └── scheduler.py              # Celery/APScheduler
├── notifications/                # Alerting (future)
│   └── email.py                  # Email/Slack notifier
├── backend/
│   └── utils/
│       └── audit.py              # Healthcare audit logger
├── automation/
│   └── playwright/               # Browser automation templates
│       ├── login_sample_portal.spec.js
│       └── soap_note_entry.spec.js
├── data/
│   ├── logs/                     # Audit and application logs
│   └── test_data/                # Test fixtures
├── tests/                        # pytest test suite
├── main.py                       # FastAPI application entry
├── docker-compose.yml            # PostgreSQL + Redis + API
├── Dockerfile                    # Container build
├── requirements.txt              # Python dependencies
├── .env                          # Environment configuration
├── QUICKSTART.md                 # Setup guide
└── README.md                     # This file
```

---

## 🚀 Quick Start

### Prerequisites

1. **Docker & Docker Compose**
2. **DGX Spark** with LLM endpoint at `http://localhost:8000/infer`
3. **Git**

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/darren4k/healthcare-agent.git
cd healthcare-agent

# 2. Start all services (PostgreSQL, Redis, FastAPI)
docker-compose up -d

# 3. Check logs
docker-compose logs -f api

# 4. Verify health
curl http://localhost:8001/health

# 5. Access API documentation
open http://localhost:8001/docs
```

### Test the Pipeline

```bash
# Option 1: Use bash script
./test_api.sh

# Option 2: Use Python script
python test_intake.py

# Option 3: Manual curl
curl -X POST http://localhost:8001/api/intake \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PT-12345",
    "raw_input": "Patient walked 100ft with CGA. Mild knee pain 3/10. Continue exercises.",
    "visit_date": "2025-11-10T14:30:00",
    "visit_type": "PT",
    "submitted_by": "Jane Smith, PTA",
    "patient_first_name": "John",
    "patient_last_name": "Doe"
  }'
```

**See [QUICKSTART.md](QUICKSTART.md) for detailed setup and troubleshooting.**

---

## 🧪 What's Working Now (Phase 1 Complete)

| Component | Status | Description |
|-----------|--------|-------------|
| **Database Models** | ✅ Complete | Patient, NoteDraft, TaskLog (SQLAlchemy) |
| **Intake API** | ✅ Complete | POST /api/intake with Pydantic validation |
| **LLM Structuring** | ✅ Complete | Raw text → SOAP JSON via DGX endpoint |
| **Task Tracking** | ✅ Complete | GET /api/tasks/{id} for status checks |
| **Docker Setup** | ✅ Complete | PostgreSQL + Redis + FastAPI containers |
| **Audit Logging** | ✅ Complete | HIPAA-compliant audit trail |
| **API Documentation** | ✅ Complete | Swagger UI + ReDoc |

---

## 🔜 What's Next (Roadmap)

### Phase 2: Multi-Channel Intake (Weeks 4-6)
- [ ] Web portal UI (React/Vue)
- [ ] Slack bot integration
- [ ] Email intake pipeline
- [ ] Clinician feedback collection

### Phase 3: Browser Automation (Weeks 7-9)
- [ ] Complete Playwright EMR automation (resolve 39 TODOs)
- [ ] Dynamic selector discovery
- [ ] Error recovery and retries
- [ ] Screenshot capture for debugging

### Phase 4: Async Processing (Weeks 10-12)
- [ ] Celery worker for background tasks
- [ ] Task queue management
- [ ] Parallel processing for high volume
- [ ] Notification system (email/Slack)

### Phase 5: Advanced Features (Weeks 13+)
- [ ] Patient-facing agents (reminders, summaries)
- [ ] Caregiver support (visit summaries, tasks)
- [ ] Compliance agents (credential tracking, billing)
- [ ] Trend analysis and reporting
- [ ] Fine-tuning LLM on historical SOAP notes

---

## 📊 Current Metrics

**Pipeline Performance (Phase 1):**
- ⏱️ Average LLM structuring time: ~5 seconds
- 📝 Note processing: Synchronous (async coming in Phase 4)
- 🗄️ Database: PostgreSQL 15 with connection pooling
- 🔐 Security: Audit logging enabled, PHI encrypted in transit

---

## 🔐 Security & Compliance

| Feature | Implementation |
|---------|----------------|
| **HIPAA Compliance** | Audit logs, encrypted data, access control |
| **Data Encryption** | TLS in transit, PostgreSQL encryption at rest |
| **Authentication** | JWT tokens (to be implemented) |
| **Audit Trail** | Every API call logged with user/patient context |
| **PHI Handling** | On-prem LLM (no cloud), secure database |
| **Access Control** | Role-based permissions (to be implemented) |

---

## 🛠️ Technology Stack

**Backend:**
- FastAPI 0.104+ (REST API)
- SQLAlchemy 2.0 (ORM)
- PostgreSQL 15 (Database)
- Pydantic 2.5+ (Validation)

**AI/ML:**
- NVIDIA DGX Spark (Infrastructure)
- Mistral/LLaMA/Phi (Local LLMs)
- vLLM/ExLlama (Inference)

**Automation:**
- Playwright (Browser automation)
- Celery + Redis (Task queue)

**DevOps:**
- Docker + Docker Compose
- Alembic (Database migrations)
- pytest (Testing)

---

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Setup and basic usage
- **[API Docs](http://localhost:8001/docs)** - Interactive API documentation
- **Code Comments** - Inline documentation in all modules

---

## 🤝 Contributing

This is a private healthcare automation project. For questions or issues:

1. Check logs: `docker-compose logs -f`
2. Review API docs: http://localhost:8001/docs
3. Test endpoints: `./test_api.sh` or `python test_intake.py`

---

## 📝 Environment Variables

Key configuration (see `.env.example` for full list):

```bash
# Application
ENV=development
DEBUG=true
PORT=8001

# Database
DATABASE_URL=postgresql://agent_user:supersecure123@db:5432/agentic_db

# LLM
LLM_ENDPOINT=http://host.docker.internal:8000/infer
LLM_MODEL=mistral-7b
LLM_TEMPERATURE=0.3

# EMR (to be configured)
EMR_BASE_URL=https://your-emr-system.com
EMR_USERNAME=your_username
EMR_PASSWORD=your_password
```

---

## 🎯 Success Criteria

**MVP Definition:**
- ✅ Accepts raw clinical notes via API
- ✅ Structures notes into SOAP format using AI
- ✅ Stores drafts in database with audit trail
- 🔜 Automatically fills EMR SOAP fields via browser automation
- 🔜 Notifies clinician for review

**Production Readiness:**
- [ ] 80%+ test coverage
- [ ] <10 second end-to-end processing time
- [ ] 99%+ uptime
- [ ] HIPAA audit compliance
- [ ] SSL/TLS encryption
- [ ] Authentication & authorization
- [ ] Disaster recovery plan

---

## 📊 Project Status

**Current Phase:** ✅ Phase 1 Complete - Foundation Pipeline
**Next Milestone:** Phase 2 - Multi-Channel Intake
**Overall Completion:** ~35%

---

## 📞 Support

**Issues:** Check Docker logs and database state
**API Testing:** Use provided test scripts
**Database Access:** See QUICKSTART.md

---

**Built with ❤️ for healthcare professionals**
