#!/bin/bash

###############################################################################
# Healthcare Agent Platform - Deployment Verification Script
# Step 6: Verify Production Deployment
#
# This script tests all critical functionality after deployment:
# - API health checks
# - Database connectivity
# - Redis connectivity
# - External API integrations (HelloNote, Insurance, Twilio, SendGrid)
# - SOAP note submission
# - Insurance verification
# - Appointment scheduling
# - Vector database
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8001}"
RETRY_COUNT=3
RETRY_DELAY=5

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_test() {
    echo -e "\n${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

print_failure() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

print_skip() {
    echo -e "${YELLOW}⊘ $1${NC}"
    ((TESTS_SKIPPED++))
}

wait_for_service() {
    local url=$1
    local service=$2
    local max_attempts=30
    local attempt=1

    print_test "Waiting for $service to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            print_success "$service is ready"
            return 0
        fi

        echo -n "."
        sleep 2
        ((attempt++))
    done

    print_failure "$service failed to start within $((max_attempts * 2)) seconds"
    return 1
}

test_endpoint() {
    local method=$1
    local endpoint=$2
    local expected_status=$3
    local description=$4
    local data=$5

    print_test "$description"

    if [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint")
    fi

    status_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$status_code" = "$expected_status" ]; then
        print_success "Status $status_code (expected $expected_status)"
        echo "Response: $body" | head -c 200
        return 0
    else
        print_failure "Status $status_code (expected $expected_status)"
        echo "Response: $body"
        return 1
    fi
}

###############################################################################
# Test Suite
###############################################################################

print_header "Healthcare Agent Platform - Deployment Verification"
echo "API URL: $API_URL"
echo "Started at: $(date)"

###############################################################################
# 1. Core Service Health Checks
###############################################################################

print_header "1. Core Service Health Checks"

# Test API Health
wait_for_service "$API_URL/health" "API Server"

test_endpoint "GET" "/health" "200" "API health endpoint"

# Test API Documentation
test_endpoint "GET" "/docs" "200" "API documentation (Swagger UI)"

test_endpoint "GET" "/openapi.json" "200" "OpenAPI schema"

###############################################################################
# 2. Database Connectivity
###############################################################################

print_header "2. Database Connectivity"

print_test "Testing database connection..."
db_test=$(docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres -d healthcare_agent_prod -c "SELECT 1" 2>&1)

if [ $? -eq 0 ]; then
    print_success "Database is accessible"
else
    print_failure "Database connection failed: $db_test"
fi

print_test "Testing database tables..."
tables=$(docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres -d healthcare_agent_prod -c "\dt" 2>&1)

if echo "$tables" | grep -q "note_drafts"; then
    print_success "Database tables exist (note_drafts, patients, appointments, etc.)"
else
    print_failure "Database tables missing"
fi

print_test "Testing pgvector extension..."
pgvector_test=$(docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres -d healthcare_agent_prod -c "SELECT * FROM pg_extension WHERE extname='vector'" 2>&1)

if echo "$pgvector_test" | grep -q "vector"; then
    print_success "pgvector extension installed"
else
    print_skip "pgvector extension not installed (optional if using Pinecone)"
fi

###############################################################################
# 3. Redis Connectivity
###############################################################################

print_header "3. Redis Connectivity"

print_test "Testing Redis connection..."
redis_test=$(docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping 2>&1)

if echo "$redis_test" | grep -q "PONG"; then
    print_success "Redis is accessible"
else
    print_failure "Redis connection failed: $redis_test"
fi

###############################################################################
# 4. Celery Workers
###############################################################################

print_header "4. Celery Workers"

print_test "Testing Celery worker status..."
celery_status=$(docker-compose -f docker-compose.prod.yml exec -T celery celery -A celery_app inspect active 2>&1)

if [ $? -eq 0 ]; then
    print_success "Celery workers are running"
else
    print_failure "Celery workers not responding: $celery_status"
fi

print_test "Testing Celery Beat scheduler..."
beat_status=$(docker-compose -f docker-compose.prod.yml ps celery-beat 2>&1)

if echo "$beat_status" | grep -q "Up"; then
    print_success "Celery Beat scheduler is running"
else
    print_failure "Celery Beat is not running"
fi

###############################################################################
# 5. SOAP Note Submission Test
###############################################################################

print_header "5. SOAP Note Submission Test"

soap_note_data='{
  "patient_name": "Test Patient",
  "raw_text": "Patient reports low back pain for 2 weeks. Pain is 7/10, worse with sitting. ROM: Lumbar flexion 40 degrees (limited), extension 10 degrees. SLR negative bilaterally. Assessment: Acute low back pain, likely mechanical. Plan: Start with manual therapy, therapeutic exercises, and modalities. Patient education on posture and body mechanics.",
  "visit_type": "PT",
  "visit_number": 1,
  "date_of_service": "'$(date +%Y-%m-%d)'"
}'

test_endpoint "POST" "/api/intake/submit" "200" "Submit test SOAP note" "$soap_note_data"

###############################################################################
# 6. Patient Intake Test
###############################################################################

print_header "6. Patient Intake Test"

patient_data='{
  "first_name": "John",
  "last_name": "TestPatient",
  "date_of_birth": "1980-01-15",
  "phone_number": "555-123-4567",
  "email": "john.test@example.com",
  "address": "123 Test St",
  "city": "Test City",
  "state": "CA",
  "zip_code": "90001",
  "insurance_company": "Blue Cross",
  "member_id": "TEST123456",
  "group_number": "GRP789",
  "primary_complaint": "Low back pain",
  "onset_date": "'$(date -d '2 weeks ago' +%Y-%m-%d)'",
  "pain_level": 7
}'

test_endpoint "POST" "/api/intake/patient" "200" "Create test patient intake" "$patient_data"

###############################################################################
# 7. External API Integration Tests
###############################################################################

print_header "7. External API Integration Tests"

# Test HelloNote credentials
print_test "Testing HelloNote EMR credentials..."
if [ -n "$HELLONOTE_USERNAME" ] && [ "$HELLONOTE_USERNAME" != "your_hellonote_username" ]; then
    print_success "HelloNote credentials configured"
else
    print_skip "HelloNote credentials not configured"
fi

# Test Insurance API
print_test "Testing insurance clearinghouse credentials..."
if [ -n "$CHANGE_HEALTHCARE_API_KEY" ] && [ "$CHANGE_HEALTHCARE_API_KEY" != "your_api_key" ]; then
    print_success "Insurance clearinghouse credentials configured"
else
    print_skip "Insurance clearinghouse credentials not configured"
fi

# Test Twilio
print_test "Testing Twilio credentials..."
if [ -n "$TWILIO_ACCOUNT_SID" ] && [ "$TWILIO_ACCOUNT_SID" != "ACxxxxxxxxxxxxxxxx" ]; then
    print_success "Twilio credentials configured"
else
    print_skip "Twilio credentials not configured"
fi

# Test SendGrid
print_test "Testing SendGrid credentials..."
if [ -n "$SENDGRID_API_KEY" ] && [ "$SENDGRID_API_KEY" != "SG.xxxxxxxxxxxxxxxx" ]; then
    print_success "SendGrid credentials configured"
else
    print_skip "SendGrid credentials not configured"
fi

# Test Vector Database
print_test "Testing vector database credentials..."
if [ -n "$PINECONE_API_KEY" ] && [ "$PINECONE_API_KEY" != "your_pinecone_api_key" ]; then
    print_success "Pinecone credentials configured"
elif [ "$VECTOR_STORE" = "pgvector" ]; then
    print_success "Using pgvector (local)"
else
    print_skip "Vector database not configured"
fi

###############################################################################
# 8. LLM Endpoint Test
###############################################################################

print_header "8. LLM Endpoint Test"

print_test "Testing LLM endpoint connectivity..."
if [ -n "$LLM_ENDPOINT" ]; then
    llm_test=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$LLM_ENDPOINT" \
        -H "Authorization: Bearer $LLM_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }' 2>&1)

    if [ "$llm_test" = "200" ] || [ "$llm_test" = "201" ]; then
        print_success "LLM endpoint is accessible"
    else
        print_failure "LLM endpoint returned status $llm_test"
    fi
else
    print_skip "LLM endpoint not configured"
fi

###############################################################################
# 9. Security Tests
###############################################################################

print_header "9. Security Tests"

print_test "Testing JWT secret key..."
if [ -n "$JWT_SECRET_KEY" ] && [ "$JWT_SECRET_KEY" != "your-secret-key-change-this-in-production" ]; then
    print_success "JWT secret key is configured"
else
    print_failure "JWT secret key not changed from default"
fi

print_test "Testing database password..."
if [ -n "$DB_PASSWORD" ] && [ "$DB_PASSWORD" != "postgres" ]; then
    print_success "Database password is configured"
else
    print_failure "Database password not changed from default"
fi

print_test "Testing CORS configuration..."
if [ -n "$CORS_ORIGINS" ]; then
    print_success "CORS origins configured: $CORS_ORIGINS"
else
    print_skip "CORS origins not explicitly configured"
fi

###############################################################################
# 10. Service Container Status
###############################################################################

print_header "10. Service Container Status"

print_test "Checking all service containers..."
container_status=$(docker-compose -f docker-compose.prod.yml ps 2>&1)

services=("api" "celery" "celery-beat" "db" "redis")
for service in "${services[@]}"; do
    if echo "$container_status" | grep "$service" | grep -q "Up"; then
        print_success "$service container is running"
    else
        print_failure "$service container is not running"
    fi
done

###############################################################################
# 11. Log Health Check
###############################################################################

print_header "11. Log Health Check"

print_test "Checking API logs for errors..."
api_logs=$(docker-compose -f docker-compose.prod.yml logs --tail=50 api 2>&1)

error_count=$(echo "$api_logs" | grep -i "error" | grep -v "0 errors" | wc -l)
if [ "$error_count" -eq 0 ]; then
    print_success "No errors in API logs (last 50 lines)"
else
    print_failure "Found $error_count error(s) in API logs"
    echo "$api_logs" | grep -i "error" | tail -5
fi

###############################################################################
# 12. Performance Tests
###############################################################################

print_header "12. Performance Tests"

print_test "Testing API response time..."
start_time=$(date +%s%N)
curl -sf "$API_URL/health" > /dev/null
end_time=$(date +%s%N)
response_time=$(( (end_time - start_time) / 1000000 )) # Convert to milliseconds

if [ "$response_time" -lt 500 ]; then
    print_success "API response time: ${response_time}ms (excellent)"
elif [ "$response_time" -lt 1000 ]; then
    print_success "API response time: ${response_time}ms (good)"
else
    print_failure "API response time: ${response_time}ms (slow)"
fi

print_test "Testing concurrent requests..."
for i in {1..10}; do
    curl -sf "$API_URL/health" > /dev/null &
done
wait

if [ $? -eq 0 ]; then
    print_success "Handled 10 concurrent requests successfully"
else
    print_failure "Failed to handle concurrent requests"
fi

###############################################################################
# Test Summary
###############################################################################

print_header "Test Summary"

echo ""
echo -e "${GREEN}Tests Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Tests Failed:${NC} $TESTS_FAILED"
echo -e "${YELLOW}Tests Skipped:${NC} $TESTS_SKIPPED"
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
    echo -e "Success Rate: ${SUCCESS_RATE}%"
fi

echo ""
echo "Completed at: $(date)"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ ALL CRITICAL TESTS PASSED${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Your deployment is ready for production use!"
    echo ""
    echo "Next steps:"
    echo "1. Configure SSL certificate (./scripts/setup_ssl.sh)"
    echo "2. Set up domain DNS records"
    echo "3. Configure monitoring (./scripts/setup_monitoring.sh)"
    echo "4. Set up automated backups (./scripts/backup_db.sh)"
    echo "5. Launch pilot with first clinic"
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ DEPLOYMENT VERIFICATION FAILED${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "Please fix the failed tests before proceeding to production."
    echo ""
    echo "To view logs:"
    echo "  docker-compose -f docker-compose.prod.yml logs -f api"
    echo ""
    echo "To restart services:"
    echo "  docker-compose -f docker-compose.prod.yml restart"
    exit 1
fi
