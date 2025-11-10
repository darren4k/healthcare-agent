# Phase 2 Implementation Plan: Multi-Channel Intake & Intelligence

## 🎯 Goals

Transform the system from API-only to a multi-channel intake platform with:
- **Web Portal** for easy employee note submission
- **Slack Bot** for quick mobile/desktop submissions
- **Email Intake** for flexible text/audio submissions
- **Feedback System** for clinician corrections and learning
- **Dashboard** for monitoring and analytics

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTAKE CHANNELS (Phase 2)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Web Portal  │  │ Slack Bot   │  │ Email IMAP  │            │
│  │  (React)    │  │  (Bolt)     │  │  (aiomail)  │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                 │                 │                    │
│         └─────────────────┴─────────────────┘                    │
│                           ▼                                      │
│                  ┌────────────────────┐                          │
│                  │  Intake API        │                          │
│                  │  POST /api/intake  │                          │
│                  └────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │   LLM Structuring     │
               └───────────┬───────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │   PostgreSQL DB       │
               └───────────┬───────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │ Feedback Collection   │
               │ POST /api/feedback    │
               └───────────────────────┘
```

---

## 📦 Components to Build

### 1. Web Portal (React + Vite)
**Directory:** `/frontend/`

**Features:**
- Clean, accessible form for note submission
- Patient lookup/autocomplete
- Visit type selection
- Real-time submission status
- SOAP note preview
- Mobile-responsive design

**Tech Stack:**
- React 18 + Vite
- TailwindCSS for styling
- React Hook Form for validation
- Axios for API calls
- React Query for data fetching

---

### 2. Slack Bot Integration
**Directory:** `/integrations/slack/`

**Features:**
- Slash command: `/note [patient_id] | [raw note]`
- Interactive modal for structured input
- Confirmation messages with task ID
- Direct message notifications to clinicians
- Status check: `/status [task_id]`

**Tech Stack:**
- Slack Bolt for Python
- FastAPI webhook endpoint
- ngrok for local development

**Example Usage:**
```
/note PT-12345 | Patient walked 100ft with CGA. Mild knee pain 3/10. Continue plan.

Bot Response:
✅ Note submitted! Task ID: 42
📝 Status: Processing...
🔗 View: http://portal.app/tasks/42
```

---

### 3. Email Intake Pipeline
**Directory:** `/integrations/email/`

**Features:**
- Monitor dedicated inbox: `notes@youragency.ai`
- Parse email subject and body
- Extract attachments (audio, PDF)
- Auto-extract patient ID and visit type
- Send confirmation email with task link

**Email Format:**
```
Subject: PT-12345 | 11/10 Visit

Body:
Patient walked 100ft with rolling walker.
Reports decreased pain 2/10.
Balance improved.
Plan: Progress to cane next week.

Attachments: voice_note.mp3
```

**Tech Stack:**
- aiosmtplib + aioimaplib
- Email parser with regex
- Audio transcription (Whisper API optional)
- Scheduled polling (every 2 minutes)

---

### 4. Feedback Collection API
**Directory:** `/api/feedback.py`

**Features:**
- Endpoint: `POST /api/feedback`
- Capture clinician edits to SOAP notes
- Store original vs. edited versions
- Calculate edit distance metrics
- Flag common correction patterns
- Feed into learning loop (Phase 5)

**Schema:**
```json
{
  "task_id": 42,
  "clinician_id": "dr_smith",
  "edited_soap": {
    "subjective": "...",
    "objective": "...",
    "assessment": "...",
    "plan": "..."
  },
  "feedback_notes": "Need more specificity in objective measurements",
  "satisfaction_score": 4
}
```

---

### 5. Dashboard UI
**Directory:** `/frontend/src/pages/Dashboard.jsx`

**Features:**
- Recent submissions table
- Processing status indicators
- SOAP note cards with confidence scores
- Filter by date, patient, status
- Quick actions: View, Edit, Approve
- Analytics: Notes per day, avg confidence, processing time

**Metrics:**
- Total notes processed
- Average confidence score
- Processing time trends
- Most active submitters
- Error rate

---

## 🔧 Implementation Order

### Week 1: Web Portal Foundation
**Days 1-2:** Setup React project, basic form
**Days 3-4:** API integration, status display
**Day 5:** Polish UI, mobile responsive

### Week 2: Slack Integration
**Days 1-2:** Slack app setup, slash commands
**Day 3:** Webhook endpoint, message parsing
**Days 4-5:** Interactive modals, notifications

### Week 3: Email & Feedback
**Days 1-2:** Email monitoring pipeline
**Day 3:** Audio transcription integration
**Days 4-5:** Feedback collection API

---

## 📂 New Directory Structure

```
healthcare-agent/
├── frontend/                          # React web portal
│   ├── src/
│   │   ├── components/
│   │   │   ├── NoteForm.jsx
│   │   │   ├── TaskStatus.jsx
│   │   │   ├── SOAPDisplay.jsx
│   │   │   └── PatientLookup.jsx
│   │   ├── pages/
│   │   │   ├── Submit.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   └── TaskDetail.jsx
│   │   ├── api/
│   │   │   └── client.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
│
├── integrations/
│   ├── slack/
│   │   ├── __init__.py
│   │   ├── bot.py                    # Slack Bolt app
│   │   ├── handlers.py               # Command handlers
│   │   └── formatters.py             # Message formatting
│   │
│   └── email/
│       ├── __init__.py
│       ├── monitor.py                # IMAP polling
│       ├── parser.py                 # Email parsing
│       └── transcribe.py             # Audio transcription
│
├── api/
│   ├── intake.py                     # Existing
│   ├── feedback.py                   # NEW: Feedback collection
│   └── dashboard.py                  # NEW: Dashboard data
│
└── workers/                          # Background tasks
    ├── __init__.py
    └── email_worker.py               # Email polling worker
```

---

## 🔐 Security Considerations

**Web Portal:**
- HTTPS only in production
- CSRF protection
- Input sanitization
- Rate limiting

**Slack Bot:**
- Verify Slack signatures
- Validate user permissions
- No PHI in channel messages
- Audit all commands

**Email:**
- Secure IMAP/SMTP (TLS)
- Attachment virus scanning
- PGP encryption option
- Auto-delete after processing

---

## 🧪 Testing Strategy

**Integration Tests:**
- Web portal form submission
- Slack command parsing
- Email inbox processing
- Feedback submission

**E2E Tests:**
- Submit note via web → Check database
- Send Slack command → Verify response
- Email note → Confirm processing
- Submit feedback → Update metrics

---

## 📊 Success Metrics

**Adoption:**
- 80% of staff use at least one intake channel
- 50% reduction in manual note entry time
- <5 minutes from submission to SOAP draft

**Quality:**
- Average confidence score >80%
- <20% edit rate by clinicians
- Zero security incidents

**Performance:**
- <3 seconds web portal response time
- <10 seconds Slack bot response
- <5 minutes email processing latency

---

## 🚀 Getting Started

See the following implementation files:
1. `frontend/README.md` - Web portal setup
2. `integrations/slack/README.md` - Slack bot setup
3. `integrations/email/README.md` - Email pipeline setup

Run all channels:
```bash
# Terminal 1: API + Database
docker-compose up

# Terminal 2: Web Portal
cd frontend && npm run dev

# Terminal 3: Slack Bot
python -m integrations.slack.bot

# Terminal 4: Email Worker
python -m workers.email_worker
```

---

## 🔜 Phase 3 Preview

After Phase 2 completes:
- Browser automation (Playwright EMR integration)
- Async processing (Celery workers)
- Notifications (Email/Slack to clinicians)
- Advanced error recovery

---

**Ready to build!** Starting with the web portal...
