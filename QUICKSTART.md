# 🚀 Quick Start Guide - Agentic SOAP Note System

## Prerequisites

1. **Docker & Docker Compose** installed
2. **DGX Spark** running with LLM endpoint at `http://localhost:8000/infer`
3. **Git** (for version control)

---

## 📦 Installation

### Step 1: Start the Services

```bash
# Start PostgreSQL, Redis, and FastAPI app
docker-compose up -d

# Check logs
docker-compose logs -f api
```

Wait for the message: `✅ Database initialized successfully`

### Step 2: Verify Services

```bash
# Check health endpoint
curl http://localhost:8001/health

# Expected response:
# {
#   "status": "healthy",
#   "app_name": "Agentic SOAP Note System",
#   "version": "1.0.0",
#   "environment": "development",
#   "timestamp": "2025-11-10T..."
# }
```

### Step 3: Access API Documentation

Open in your browser:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

---

## 🧪 Testing the Pipeline

### Test 1: Submit a Simple Note

```bash
curl -X POST http://localhost:8001/api/intake \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PT-12345",
    "raw_input": "Patient walked 100 feet with contact guard assist. Reports mild knee pain rated 3/10. Gait steady with good balance. Continue strengthening exercises and progress to supervision level next visit.",
    "visit_date": "2025-11-10T14:30:00",
    "visit_type": "PT",
    "submitted_by": "Jane Smith, PTA",
    "source": "api_direct",
    "patient_first_name": "John",
    "patient_last_name": "Doe",
    "patient_dob": "1965-05-15T00:00:00"
  }'
```

**Expected Response:**
```json
{
  "task_id": 1,
  "status": "llm_complete",
  "message": "Note structured successfully. Ready for EMR entry.",
  "created_at": "2025-11-10T15:30:00"
}
```

### Test 2: Check Task Status

```bash
# Replace {task_id} with the ID from previous response
curl http://localhost:8001/api/tasks/1
```

**Expected Response:**
```json
{
  "task_id": 1,
  "status": "llm_complete",
  "patient_id": "PT-12345",
  "visit_date": "2025-11-10T14:30:00",
  "created_at": "2025-11-10T15:30:00",
  "updated_at": "2025-11-10T15:30:05",
  "soap_components": {
    "subjective": "Patient reports mild knee pain rated 3/10 during ambulation.",
    "objective": "Patient ambulated 100 feet with contact guard assist (CGA). Gait steady with good balance observed.",
    "assessment": "Patient demonstrating good progress in mobility with minimal assistance. Pain level manageable.",
    "plan": "Continue current strengthening exercises. Progress to supervision level for next visit. Monitor pain levels.",
    "confidence_score": 87
  },
  "emr_draft_url": null,
  "emr_draft_id": null,
  "error_message": null
}
```

---

## 🔍 Troubleshooting

### Issue: "Connection refused to LLM endpoint"

**Cause:** DGX LLM server not running or wrong endpoint

**Solution:**
1. Verify LLM server is running: `curl http://localhost:8000/infer`
2. Update `.env` file with correct endpoint
3. Restart containers: `docker-compose restart api`

### Issue: "Database connection failed"

**Cause:** PostgreSQL not ready

**Solution:**
```bash
# Check database health
docker-compose ps

# Restart database
docker-compose restart db

# Wait 10 seconds, then restart API
docker-compose restart api
```

### Issue: "Invalid JSON from LLM"

**Cause:** LLM response format doesn't match expected structure

**Solution:**
1. Check LLM logs: `docker-compose logs api | grep LLM`
2. Verify LLM endpoint response format matches `core/parser.py` expectations
3. Update `_extract_json` method in `core/parser.py` if needed

---

## 📊 Database Access

```bash
# Connect to PostgreSQL
docker exec -it agentic_postgres psql -U agent_user -d agentic_db

# Useful queries:
# List all patients
SELECT * FROM patients;

# List all note drafts
SELECT id, patient_id, status, visit_date, confidence_score
FROM note_drafts
ORDER BY created_at DESC;

# View task logs
SELECT task_name, status, duration_seconds
FROM task_logs
ORDER BY created_at DESC;
```

---

## 🛑 Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data!)
docker-compose down -v
```

---

## 📈 Next Steps

1. **Customize LLM Endpoint**: Update `.env` with your actual DGX endpoint format
2. **Configure EMR**: Add real EMR credentials in `.env`
3. **Implement Browser Automation**: Complete the Playwright scripts in `automation/playwright/`
4. **Add Async Processing**: Uncomment Celery worker in `docker-compose.yml`
5. **Build Web Portal**: Create React/Vue frontend for easier note submission

---

## 🔐 Security Checklist

- [ ] Change `SECRET_KEY` in `.env` for production
- [ ] Use strong database passwords
- [ ] Enable SSL/TLS for API endpoints
- [ ] Implement authentication middleware
- [ ] Enable audit logging
- [ ] Encrypt PHI at rest and in transit
- [ ] Regular security audits

---

## 📞 Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review API docs: http://localhost:8001/docs
- Check database state (see Database Access above)
