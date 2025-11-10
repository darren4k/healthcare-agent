# Deployment Operations Guide

Complete guide for deploying, operating, and maintaining the Healthcare Agent Platform in production.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Deployment Steps (1-10)](#deployment-steps)
3. [Daily Operations](#daily-operations)
4. [Monitoring & Alerts](#monitoring--alerts)
5. [Backup & Recovery](#backup--recovery)
6. [Security Operations](#security-operations)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance Tasks](#maintenance-tasks)

---

## Quick Start

### Complete Deployment (All Steps)

```bash
# Step 1-5: Initial deployment
./scripts/deploy_production.sh

# Step 6: Verify deployment
./scripts/test_deployment.sh

# Step 7: Setup SSL
sudo ./scripts/setup_ssl.sh --domain api.yourdomain.com --email admin@yourdomain.com

# Step 9: Setup monitoring
./scripts/setup_monitoring.sh

# Step 10: Configure backups
# Add to crontab:
0 2 * * * /path/to/healthcare-agent/scripts/backup_db.sh >> /var/log/backup.log 2>&1

# Run integration tests
./scripts/run_integration_tests.sh
```

---

## Deployment Steps

### Steps 1-5: Initial Deployment

**Covered by**: `scripts/deploy_production.sh`

```bash
./scripts/deploy_production.sh
```

This automated script handles:
- ✓ Environment validation
- ✓ Directory creation
- ✓ SSL certificate generation (self-signed for testing)
- ✓ Docker image building
- ✓ Database initialization
- ✓ Migrations
- ✓ Data seeding
- ✓ Vector database initialization
- ✓ Service startup
- ✓ Health checks

**Duration**: 10-15 minutes

**Requirements**:
- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum
- 50GB disk space
- Configured `.env` file

---

### Step 6: Verify Deployment

**Script**: `scripts/test_deployment.sh`

```bash
./scripts/test_deployment.sh
```

**What it tests**:
- ✓ API health endpoints
- ✓ Database connectivity
- ✓ Redis connectivity
- ✓ Celery workers
- ✓ SOAP note submission
- ✓ Patient intake
- ✓ External API credentials (HelloNote, Insurance, Twilio, SendGrid)
- ✓ LLM endpoint
- ✓ Security configuration
- ✓ Response times
- ✓ Concurrent request handling

**Expected output**:
```
========================================
✓ ALL CRITICAL TESTS PASSED
========================================

Tests Passed: 45
Tests Failed: 0
Success Rate: 100%
```

---

### Step 7: Configure SSL Certificate

**Script**: `scripts/setup_ssl.sh`

#### Production (Let's Encrypt):

```bash
sudo ./scripts/setup_ssl.sh \
  --domain api.yourdomain.com \
  --email admin@yourdomain.com
```

Features:
- ✓ Automatic certificate generation via Certbot
- ✓ Auto-renewal configuration (daily cron job)
- ✓ Nginx integration
- ✓ Certificate verification
- ✓ 90-day validity with automatic renewal

#### Development (Self-Signed):

```bash
./scripts/setup_ssl.sh --self-signed
```

⚠️ **Note**: Self-signed certificates will show browser warnings. Use only for testing.

---

### Step 8: Configure Domain

**Manual configuration required**

1. **Update DNS Records**:

```
A    api.yourdomain.com    -> YOUR_SERVER_IP
A    app.yourdomain.com    -> YOUR_SERVER_IP
```

2. **Update `.env` file**:

```bash
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

3. **Restart services**:

```bash
docker-compose -f docker-compose.prod.yml restart
```

4. **Test HTTPS**:

```bash
curl https://api.yourdomain.com/health
```

---

### Step 9: Set Up Monitoring

**Script**: `scripts/setup_monitoring.sh`

```bash
./scripts/setup_monitoring.sh
```

**Monitoring Stack**:
- **Prometheus**: Metrics collection (port 9090)
- **Grafana**: Visualization dashboards (port 3000)
- **Alertmanager**: Alert routing (port 9093)
- **Exporters**: PostgreSQL, Redis, Nginx, System, Containers

**Access**:
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

**Pre-configured Alerts**:
- API service down
- High error rate (>5%)
- High response time (>2s)
- Database connection issues
- Redis failures
- Celery worker failures
- High CPU/Memory usage
- Low disk space
- Business metrics anomalies

**Alert Notifications**:

Edit `monitoring/alertmanager.yml` to configure:
- Email notifications
- Slack webhooks
- PagerDuty integration

---

### Step 10: Configure Backups

**Scripts**:
- `scripts/backup_db.sh` (backup)
- `scripts/restore_db.sh` (restore)

#### Setup Automated Daily Backups:

```bash
# Add to crontab
crontab -e

# Add this line (daily at 2 AM):
0 2 * * * /path/to/healthcare-agent/scripts/backup_db.sh >> /var/log/backup.log 2>&1
```

#### Manual Backup:

```bash
# Full backup (database + Redis + config)
./scripts/backup_db.sh

# Database only
./scripts/backup_db.sh --type db

# Redis only
./scripts/backup_db.sh --type redis

# Config only
./scripts/backup_db.sh --type config
```

**Backup includes**:
- PostgreSQL full dump (compressed)
- Redis RDB snapshot (compressed)
- Configuration files (docker-compose, .env, nginx, SSL certs)
- Database schema (for quick reference)
- Table statistics
- MD5 checksums for integrity verification
- Backup manifest

**Default Settings**:
- Location: `./backups/`
- Retention: 30 days
- Compression: gzip level 6
- Checksum: MD5

**Configure Remote Storage** (optional):

```bash
# Set environment variable
export BACKUP_REMOTE_PATH="s3://my-bucket/healthcare-backups"

# Or for rsync
export BACKUP_REMOTE_PATH="user@backup-server:/backups/healthcare"
```

---

## Daily Operations

### Starting Services

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Stopping Services

```bash
docker-compose -f docker-compose.prod.yml down
```

### Restarting Services

```bash
# All services
docker-compose -f docker-compose.prod.yml restart

# Specific service
docker-compose -f docker-compose.prod.yml restart api
```

### Viewing Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f api

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100 api

# Filter errors only
docker-compose -f docker-compose.prod.yml logs api | grep -i error
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

## Monitoring & Alerts

### Grafana Dashboards

1. **Access Grafana**: http://localhost:3000
2. **Default credentials**: admin/admin (change on first login)
3. **Pre-configured dashboards**:
   - Healthcare Agent API Dashboard
   - Database Metrics
   - Redis Metrics
   - System Metrics
   - Business Metrics

### Import Additional Dashboards

```
- PostgreSQL: Dashboard ID 9628
- Redis: Dashboard ID 11835
- Node Exporter: Dashboard ID 1860
- Nginx: Dashboard ID 12708
```

### View Prometheus Metrics

```bash
# API metrics
curl http://localhost:8001/metrics

# PostgreSQL metrics
curl http://localhost:9187/metrics

# Redis metrics
curl http://localhost:9121/metrics

# Nginx metrics
curl http://localhost:9113/metrics
```

### Test Alerts

```bash
# Trigger API down alert
docker-compose -f docker-compose.prod.yml stop api

# Wait 2-3 minutes, check Alertmanager
curl http://localhost:9093/api/v2/alerts

# Restore service
docker-compose -f docker-compose.prod.yml start api
```

### Configure Alert Notifications

Edit `monitoring/alertmanager.yml`:

```yaml
receivers:
  - name: 'critical-receiver'
    email_configs:
      - to: 'oncall@yourdomain.com'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#critical-alerts'
```

Reload configuration:

```bash
docker-compose -f monitoring/docker-compose.monitoring.yml restart alertmanager
```

---

## Backup & Recovery

### List Available Backups

```bash
./scripts/restore_db.sh --list
```

Output:
```
Found 15 backup(s):

[1] 2025 11 10 02 00 00
    Name: healthcare_backup_20251110_020000
    Size: 2.3GB
    - PostgreSQL database ✓
    - Redis data ✓
    - Configuration files ✓
```

### Restore Latest Backup

```bash
./scripts/restore_db.sh --latest
```

⚠️ **Warning**: This will overwrite existing data!

### Restore Specific Backup

```bash
./scripts/restore_db.sh --backup healthcare_backup_20251110_020000
```

### Restore Database Only

```bash
./scripts/restore_db.sh --backup healthcare_backup_20251110_020000 --type db
```

### Restore Without Confirmation

```bash
./scripts/restore_db.sh --latest --yes
```

⚠️ **Use with caution!** This skips safety confirmation.

### Verify Backup Integrity

Backups are automatically verified with MD5 checksums during restore. Manual verification:

```bash
cd backups
md5sum -c healthcare_backup_20251110_020000_postgres.sql.gz.md5
```

### Remote Backup Configuration

#### AWS S3:

```bash
# Install AWS CLI
apt-get install awscli

# Configure credentials
aws configure

# Set backup destination
export BACKUP_REMOTE_PATH="s3://my-healthcare-backups"

# Run backup (will auto-upload)
./scripts/backup_db.sh
```

#### Rsync:

```bash
# Set backup destination
export BACKUP_REMOTE_PATH="user@backup-server:/backups/healthcare"

# Setup SSH key authentication
ssh-copy-id user@backup-server

# Run backup (will auto-upload)
./scripts/backup_db.sh
```

---

## Security Operations

### SSL Certificate Renewal

Automatic renewal is configured by default. Manual renewal:

```bash
sudo certbot renew

# Copy renewed certificates
sudo cp /etc/letsencrypt/live/*/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/*/privkey.pem nginx/ssl/key.pem

# Reload nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### Security Headers Verification

```bash
curl -I https://api.yourdomain.com | grep -E "(Strict-Transport-Security|X-Frame-Options|X-Content-Type|X-XSS-Protection)"
```

Expected output:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
```

### Rate Limiting Test

```bash
# Test API rate limit (10 req/s)
for i in {1..20}; do curl -s http://localhost:8001/health & done

# Should see 429 Too Many Requests for some requests
```

### Change Default Passwords

```bash
# Grafana
# Access http://localhost:3000, login with admin/admin
# Will prompt to change password

# Database (update .env)
nano .env
# Update DB_PASSWORD
docker-compose -f docker-compose.prod.yml restart db

# JWT Secret (update .env)
nano .env
# Update JWT_SECRET_KEY with: openssl rand -hex 32
docker-compose -f docker-compose.prod.yml restart api
```

### View Security Audit Log

```bash
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d healthcare_agent_prod -c "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 100;"
```

---

## Troubleshooting

### API Not Responding

```bash
# Check if container is running
docker-compose -f docker-compose.prod.yml ps api

# Check logs
docker-compose -f docker-compose.prod.yml logs --tail=100 api

# Check health
curl http://localhost:8001/health

# Restart API
docker-compose -f docker-compose.prod.yml restart api
```

### Database Connection Failed

```bash
# Check database is running
docker-compose -f docker-compose.prod.yml ps db

# Check database logs
docker-compose -f docker-compose.prod.yml logs --tail=100 db

# Test database connection
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d healthcare_agent_prod -c "SELECT 1;"

# Check connections
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d healthcare_agent_prod -c "SELECT count(*) FROM pg_stat_activity;"

# Reset database (DESTRUCTIVE!)
docker-compose -f docker-compose.prod.yml down
docker volume rm healthcare-agent_postgres_data
docker-compose -f docker-compose.prod.yml up -d
```

### Celery Workers Not Processing Tasks

```bash
# Check worker status
docker-compose -f docker-compose.prod.yml ps celery

# Check logs
docker-compose -f docker-compose.prod.yml logs --tail=100 celery

# Inspect active tasks
docker-compose -f docker-compose.prod.yml exec celery celery -A celery_app inspect active

# Check queue length
docker-compose -f docker-compose.prod.yml exec redis redis-cli llen celery

# Restart workers
docker-compose -f docker-compose.prod.yml restart celery celery-beat
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose -f docker-compose.prod.yml ps redis

# Test connection
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping

# Check memory usage
docker-compose -f docker-compose.prod.yml exec redis redis-cli info memory

# Clear Redis (DESTRUCTIVE!)
docker-compose -f docker-compose.prod.yml exec redis redis-cli FLUSHALL

# Restart Redis
docker-compose -f docker-compose.prod.yml restart redis
```

### External API Integration Failures

#### HelloNote EMR:

```bash
# Verify credentials
grep HELLONOTE_ .env

# Test manually
docker-compose -f docker-compose.prod.yml exec api python -c "
from browser_agent.emr_agent import EMRAgent
agent = EMRAgent('hellonote')
print(agent.test_connection())
"
```

#### Insurance Clearinghouse:

```bash
# Verify credentials
grep CHANGE_HEALTHCARE .env

# Test eligibility check
curl -X POST http://localhost:8001/api/insurance/verify \
  -H "Content-Type: application/json" \
  -d '{
    "payer_name": "Blue Cross",
    "member_id": "TEST123",
    "date_of_service": "'$(date +%Y-%m-%d)'"
  }'
```

#### Twilio SMS:

```bash
# Verify credentials
grep TWILIO .env

# Send test SMS
docker-compose -f docker-compose.prod.yml exec api python -c "
from twilio.rest import Client
import os
client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
message = client.messages.create(
    body='Healthcare Agent test',
    from_=os.getenv('TWILIO_PHONE_NUMBER'),
    to='+15551234567'  # Update with your phone
)
print(message.sid)
"
```

### High Memory Usage

```bash
# Check memory by service
docker stats --no-stream

# Check API memory
docker-compose -f docker-compose.prod.yml exec api ps aux

# Restart high-memory services
docker-compose -f docker-compose.prod.yml restart api celery
```

### Disk Space Issues

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up old images
docker image prune -a

# Clean up old containers
docker container prune

# Clean up old backups
find backups/ -name "healthcare_backup_*" -mtime +30 -delete
```

---

## Maintenance Tasks

### Update Application Code

```bash
# Pull latest code
git pull origin claude/project-review-011CUygLTXRT3qg7wRN2R7YX

# Rebuild images
docker-compose -f docker-compose.prod.yml build --no-cache

# Stop services
docker-compose -f docker-compose.prod.yml down

# Run migrations
docker-compose -f docker-compose.prod.yml up -d db redis
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Verify
./scripts/test_deployment.sh
```

### Database Maintenance

```bash
# Vacuum database
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d healthcare_agent_prod -c "VACUUM ANALYZE;"

# Check table sizes
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d healthcare_agent_prod -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
"

# Reindex database
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d healthcare_agent_prod -c "REINDEX DATABASE healthcare_agent_prod;"
```

### Log Rotation

```bash
# Setup logrotate for Docker logs
sudo tee /etc/logrotate.d/docker-containers << EOF
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    missingok
    delaycompress
    copytruncate
}
EOF

# Test logrotate
sudo logrotate -f /etc/logrotate.d/docker-containers
```

### Scale Services

```bash
# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery=4

# Scale API workers (edit docker-compose.prod.yml)
# Change: --workers 4 to --workers 8
docker-compose -f docker-compose.prod.yml up -d api
```

### Weekly Maintenance Checklist

- [ ] Review monitoring dashboards
- [ ] Check alert notifications
- [ ] Verify backups are running
- [ ] Review error logs
- [ ] Check disk space
- [ ] Review security audit logs
- [ ] Update SSL certificates (if needed)
- [ ] Test restore procedure (monthly)

---

## Integration Testing

### Run Full Test Suite

```bash
./scripts/run_integration_tests.sh
```

### Run Specific Test Suites

```bash
# Verbose mode
./scripts/run_integration_tests.sh --verbose

# Custom API URL
./scripts/run_integration_tests.sh --api-url https://api.yourdomain.com
```

**Test Coverage**:
- ✓ SOAP note generation workflow
- ✓ Patient intake workflow
- ✓ Appointment scheduling
- ✓ Insurance verification
- ✓ Claims submission
- ✓ Vector database similarity search
- ✓ Natural language interface
- ✓ EMR integration
- ✓ Performance benchmarks

---

## Support & Documentation

**Documentation**:
- [Production Deployment Guide](PRODUCTION_DEPLOYMENT_GUIDE.md)
- [Complete Platform Summary](COMPLETE_PLATFORM_SUMMARY.md)
- [API Documentation](http://localhost:8001/docs)

**Scripts**:
- `deploy_production.sh` - Initial deployment (Steps 1-5)
- `test_deployment.sh` - Deployment verification (Step 6)
- `setup_ssl.sh` - SSL configuration (Step 7)
- `setup_monitoring.sh` - Monitoring setup (Step 9)
- `backup_db.sh` - Database backup (Step 10)
- `restore_db.sh` - Database restore (Step 10)
- `run_integration_tests.sh` - Integration testing

**Monitoring**:
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

---

## Production Checklist

Before launching to production:

### Security
- [ ] Changed all default passwords
- [ ] Generated new JWT secret
- [ ] Configured SSL certificates (Let's Encrypt)
- [ ] Enabled firewall (ports 80, 443, 22 only)
- [ ] Configured CORS properly
- [ ] Enabled rate limiting
- [ ] Reviewed HIPAA compliance
- [ ] Completed security audit

### Infrastructure
- [ ] Set up automated backups
- [ ] Configured backup retention (30 days)
- [ ] Tested restore procedure
- [ ] Configured monitoring/alerts
- [ ] Set up alert notifications (email/Slack)
- [ ] Configured DNS records
- [ ] Verified SSL certificate auto-renewal

### External Services
- [ ] Configured HelloNote credentials
- [ ] Tested EMR integration
- [ ] Configured insurance clearinghouse (Change Healthcare/Availity)
- [ ] Submitted test claim
- [ ] Configured Twilio (SMS)
- [ ] Sent test SMS reminder
- [ ] Configured SendGrid (Email)
- [ ] Sent test email
- [ ] Configured vector database (Pinecone/pgvector)
- [ ] Configured LLM endpoint

### Testing
- [ ] Ran deployment verification (test_deployment.sh)
- [ ] Ran integration tests (run_integration_tests.sh)
- [ ] Tested SOAP note submission
- [ ] Tested patient intake
- [ ] Tested appointment scheduling
- [ ] Tested insurance verification
- [ ] Tested claim submission
- [ ] Load tested API (concurrent requests)
- [ ] Verified response times (<500ms)

### Operations
- [ ] Documented deployment procedures
- [ ] Trained operations team
- [ ] Created runbooks for common issues
- [ ] Set up on-call rotation
- [ ] Configured log aggregation
- [ ] Set up performance monitoring

### Business Readiness
- [ ] Created test patient intake
- [ ] Scheduled test appointment
- [ ] Generated test SOAP note
- [ ] Submitted test claim
- [ ] Verified end-to-end workflow
- [ ] Monitored for 24 hours
- [ ] Prepared for pilot launch (1 clinic)

---

**Status**: Production Deployment Steps 1-10 Complete ✅

**Platform Version**: 1.0.0
**Last Updated**: November 10, 2025
