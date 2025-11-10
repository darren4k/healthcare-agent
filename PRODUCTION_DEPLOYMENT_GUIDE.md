# Production Deployment Guide

Complete step-by-step guide to deploy Healthcare Agent Platform to production.

---

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- 50GB disk space
- Domain name with SSL certificate

---

## Step 1: Server Setup

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

---

## Step 2: Clone Repository

```bash
# Clone repository
git clone https://github.com/your-org/healthcare-agent.git
cd healthcare-agent

# Checkout production branch
git checkout claude/project-review-011CUygLTXRT3qg7wRN2R7YX
```

---

## Step 3: Configure Environment

```bash
# Copy production environment template
cp .env.production .env

# Generate secure passwords
echo "DB_PASSWORD=$(openssl rand -hex 32)" >> .env
echo "REDIS_PASSWORD=$(openssl rand -hex 32)" >> .env
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env

# Edit .env file with your credentials
nano .env
```

### Required Configurations

#### 1. HelloNote EMR
```bash
HELLONOTE_USERNAME=your_hellonote_username
HELLONOTE_PASSWORD=your_hellonote_password
```

**How to get:**
1. Log in to HelloNote
2. Go to Account Settings
3. Generate API credentials or use your login credentials
4. Update `.env` file

#### 2. Insurance Clearinghouse (Change Healthcare)
```bash
CHANGE_HEALTHCARE_API_KEY=your_api_key
CHANGE_HEALTHCARE_USERNAME=your_username
CHANGE_HEALTHCARE_PASSWORD=your_password
```

**How to get:**
1. Sign up at https://www.changehealthcare.com/
2. Request API access for Eligibility (270/271) and Claims (837/835)
3. Complete integration certification
4. Obtain API credentials from developer portal
5. Update `.env` file

**Alternative: Availity**
```bash
INSURANCE_PROVIDER=availity
AVAILITY_API_KEY=your_api_key
```

1. Sign up at https://www.availity.com/
2. Request API access
3. Complete certification
4. Obtain credentials

#### 3. Twilio SMS (Appointment Reminders)
```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+15551234567
```

**How to get:**
1. Sign up at https://www.twilio.com/
2. Get a phone number ($1/month)
3. Copy Account SID and Auth Token from console
4. Update `.env` file

#### 4. SendGrid Email
```bash
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
```

**How to get:**
1. Sign up at https://sendgrid.com/ (free tier: 100 emails/day)
2. Create API key with "Mail Send" permissions
3. Verify sender email address
4. Update `.env` file

#### 5. Pinecone Vector Database
```bash
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=us-west1-gcp
```

**How to get:**
1. Sign up at https://www.pinecone.io/ (free tier: 1 index, 1M vectors)
2. Create project
3. Copy API key
4. Update `.env` file

**Alternative: Use pgvector (included)**
```bash
VECTOR_STORE=pgvector
# No additional configuration needed
```

#### 6. OpenAI (for embeddings)
```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**How to get:**
1. Sign up at https://platform.openai.com/
2. Add payment method
3. Create API key
4. Update `.env` file

#### 7. LLM Endpoint (DGX Spark or other)
```bash
LLM_ENDPOINT=http://your-dgx-spark-endpoint/v1/chat/completions
LLM_API_KEY=your_llm_api_key
LLM_MODEL=llama-70b-instruct
```

**How to get:**
- If using DGX Spark: Contact your NVIDIA representative
- If using other provider: Use their endpoint URL and API key
- Alternative: Use OpenAI GPT-4 endpoint

---

## Step 4: Validate Configuration

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Validate all configurations
docker-compose -f docker-compose.prod.yml run --rm api python scripts/validate_config.py
```

This will test:
- ✓ All required environment variables
- ✓ Database connection
- ✓ Redis connection
- ✓ LLM endpoint
- ✓ Twilio credentials
- ✓ SendGrid credentials
- ✓ Pinecone/vector database
- ✓ Insurance API

Fix any errors before proceeding.

---

## Step 5: Deploy to Production

```bash
# Run automated deployment script
./scripts/deploy_production.sh
```

This script will:
1. ✓ Validate environment configuration
2. ✓ Create data directories
3. ✓ Generate SSL certificates (self-signed for testing)
4. ✓ Build Docker images
5. ✓ Start database and Redis
6. ✓ Run database migrations
7. ✓ Seed initial data
8. ✓ Initialize vector database
9. ✓ Start all services
10. ✓ Run health checks

---

## Step 6: Verify Deployment

### Test API
```bash
# Health check
curl http://localhost:8001/health

# Should return:
{
  "status": "healthy",
  "app_name": "Healthcare Agent Platform",
  "version": "1.0.0",
  "environment": "production",
  "timestamp": "2025-11-10T..."
}
```

### Test SOAP Note Submission
```bash
curl -X POST http://localhost:8001/api/intake/submit \
  -H "Content-Type: application/json" \
  -d '{
    "patient_name": "Test Patient",
    "raw_text": "Patient reports low back pain for 2 weeks. Pain is 7/10, worse with sitting. Decreased lumbar ROM. Will start with manual therapy and exercises.",
    "visit_type": "PT"
  }'
```

### Access API Documentation
```bash
open http://localhost:8001/docs
```

---

## Step 7: Configure SSL Certificate

### For Production (Let's Encrypt)
```bash
# Install Certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d api.yourdomain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem nginx/ssl/key.pem

# Restart nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

---

## Step 8: Configure Domain

### Update DNS Records

Add these DNS records:
```
A     api.yourdomain.com    -> Your_Server_IP
A     app.yourdomain.com    -> Your_Server_IP
```

### Update Environment
```bash
# Edit .env
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### Restart services
```bash
docker-compose -f docker-compose.prod.yml restart
```

---

## Step 9: Set Up Monitoring

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f api

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100 api
```

### Service Status
```bash
docker-compose -f docker-compose.prod.yml ps
```

### Resource Usage
```bash
docker stats
```

---

## Step 10: Configure Backups

### Automatic Database Backups
```bash
# Create backup script
cat > scripts/backup_db.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U postgres healthcare_agent_prod \
  > backups/db_backup_$DATE.sql
find backups/ -name "db_backup_*.sql" -mtime +30 -delete
EOF

chmod +x scripts/backup_db.sh

# Add to cron (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /path/to/healthcare-agent/scripts/backup_db.sh") | crontab -
```

---

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Check configuration
docker-compose -f docker-compose.prod.yml config

# Restart service
docker-compose -f docker-compose.prod.yml restart api
```

### Database connection failed
```bash
# Check database is running
docker-compose -f docker-compose.prod.yml ps db

# Check logs
docker-compose -f docker-compose.prod.yml logs db

# Reset database
docker-compose -f docker-compose.prod.yml down
docker volume rm healthcare-agent_postgres_data
docker-compose -f docker-compose.prod.yml up -d
```

### Can't connect to external APIs
```bash
# Test from container
docker-compose -f docker-compose.prod.yml exec api curl https://api.changehealthcare.com

# Check API keys
docker-compose -f docker-compose.prod.yml exec api env | grep API_KEY
```

---

## Maintenance

### Update Application
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

### View Database
```bash
# Connect to PostgreSQL
docker-compose -f docker-compose.prod.yml exec db psql -U postgres healthcare_agent_prod

# View tables
\dt

# View data
SELECT * FROM note_drafts ORDER BY created_at DESC LIMIT 10;
```

---

## Security Checklist

- [ ] Changed all default passwords
- [ ] Generated new JWT secret
- [ ] Configured SSL certificates
- [ ] Enabled firewall (only ports 80, 443, 22)
- [ ] Configured CORS properly
- [ ] Enabled rate limiting
- [ ] Set up automated backups
- [ ] Configured monitoring/alerts
- [ ] Reviewed HIPAA compliance
- [ ] Completed security audit

---

## Support

For issues during deployment:
- Email: support@healthcare-agent.com
- Slack: #deployment-help
- Documentation: https://docs.healthcare-agent.com

---

## Next Steps

After deployment:
1. ✓ Configure HelloNote credentials and test EMR integration
2. ✓ Submit test claim to verify insurance clearinghouse
3. ✓ Send test reminder to verify Twilio/SendGrid
4. ✓ Create test patient intake
5. ✓ Schedule test appointment
6. ✓ Generate test SOAP note
7. ✓ Monitor for 24 hours
8. ✓ Launch pilot with 1 clinic
9. ✓ Scale to 3-5 clinics
10. ✓ General availability launch
