#!/bin/bash

###############################################################################
# Healthcare Agent Platform - Integration Tests
# Comprehensive end-to-end testing of all platform features
#
# This script tests:
# - SOAP note generation workflow
# - Patient intake workflow
# - Appointment scheduling
# - Insurance verification
# - Claim submission
# - EMR integration
# - Vector database
# - Natural language interface
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
VERBOSE=false

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TEST_RESULTS=()

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
    echo -e "\n${YELLOW}▶ Test: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ PASS: $1${NC}"
    TEST_RESULTS+=("PASS: $1")
    ((TESTS_PASSED++))
}

print_failure() {
    echo -e "${RED}✗ FAIL: $1${NC}"
    TEST_RESULTS+=("FAIL: $1")
    ((TESTS_FAILED++))
}

api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=${4:-200}

    if [ "$VERBOSE" = true ]; then
        echo "Request: $method $endpoint"
        if [ -n "$data" ]; then
            echo "Data: $data"
        fi
    fi

    if [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL$endpoint" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint" 2>&1)
    fi

    status_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$VERBOSE" = true ]; then
        echo "Status: $status_code"
        echo "Response: $body"
    fi

    if [ "$status_code" = "$expected_status" ]; then
        echo "$body"
        return 0
    else
        echo "ERROR: Expected status $expected_status, got $status_code"
        echo "$body"
        return 1
    fi
}

###############################################################################
# Test Suites
###############################################################################

test_soap_note_workflow() {
    print_header "Test Suite: SOAP Note Generation"

    # Test 1: Submit raw SOAP note
    print_test "Submit PT evaluation note"

    local note_data='{
        "patient_name": "Integration Test Patient",
        "raw_text": "Patient is a 45yo male with chief complaint of right shoulder pain x 3 weeks. Pain rated 7/10, worse with overhead activities. No history of trauma. ROM: Flexion 140 degrees (limited), abduction 100 degrees (limited). Strength 4/5 throughout. Special tests: Empty can test positive, Hawkins-Kennedy positive. Assessment: Rotator cuff tendinopathy. Plan: Start manual therapy, rotator cuff strengthening program, modalities for pain management. Patient educated on activity modification.",
        "visit_type": "PT",
        "visit_number": 1,
        "date_of_service": "'$(date +%Y-%m-%d)'"
    }'

    if result=$(api_call "POST" "/api/intake/submit" "$note_data"); then
        note_id=$(echo "$result" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)

        if [ -n "$note_id" ]; then
            print_success "SOAP note submitted (ID: $note_id)"

            # Test 2: Retrieve generated note
            print_test "Retrieve generated SOAP note"

            if result=$(api_call "GET" "/api/intake/note/$note_id"); then
                if echo "$result" | grep -q "subjective"; then
                    print_success "SOAP note retrieved with structured sections"
                else
                    print_failure "SOAP note missing structured sections"
                fi
            else
                print_failure "Failed to retrieve SOAP note"
            fi

            # Test 3: Check CPT code suggestions
            print_test "Verify CPT code suggestions"

            if echo "$result" | grep -q "cpt_codes"; then
                cpt_count=$(echo "$result" | grep -o "97[0-9]*" | wc -l)
                if [ "$cpt_count" -gt 0 ]; then
                    print_success "CPT codes suggested ($cpt_count codes)"
                else
                    print_failure "No CPT codes suggested"
                fi
            else
                print_failure "CPT codes field missing"
            fi

            # Test 4: Check ICD-10 code suggestions
            print_test "Verify ICD-10 code suggestions"

            if echo "$result" | grep -q "icd10_codes"; then
                icd_count=$(echo "$result" | grep -o "M[0-9]*\.[0-9]*" | wc -l)
                if [ "$icd_count" -gt 0 ]; then
                    print_success "ICD-10 codes suggested ($icd_count codes)"
                else
                    print_failure "No ICD-10 codes suggested"
                fi
            else
                print_failure "ICD-10 codes field missing"
            fi
        else
            print_failure "Note ID not returned in response"
        fi
    else
        print_failure "Failed to submit SOAP note"
    fi
}

test_patient_intake_workflow() {
    print_header "Test Suite: Patient Intake"

    # Test 1: Create patient intake
    print_test "Create new patient intake"

    local patient_data='{
        "first_name": "Integration",
        "last_name": "TestPatient",
        "date_of_birth": "1980-05-15",
        "phone_number": "555-0123",
        "email": "integration.test@example.com",
        "address": "123 Test Street",
        "city": "Test City",
        "state": "CA",
        "zip_code": "90001",
        "insurance_company": "Blue Cross Blue Shield",
        "member_id": "TEST123456789",
        "group_number": "GRP001",
        "primary_complaint": "Chronic low back pain",
        "onset_date": "'$(date -d '6 months ago' +%Y-%m-%d)'",
        "pain_level": 6
    }'

    if result=$(api_call "POST" "/api/intake/patient" "$patient_data"); then
        patient_id=$(echo "$result" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)

        if [ -n "$patient_id" ]; then
            print_success "Patient intake created (ID: $patient_id)"

            # Test 2: Retrieve patient
            print_test "Retrieve patient intake"

            if result=$(api_call "GET" "/api/intake/patient/$patient_id"); then
                if echo "$result" | grep -q "TestPatient"; then
                    print_success "Patient intake retrieved"
                else
                    print_failure "Patient data incorrect"
                fi
            else
                print_failure "Failed to retrieve patient"
            fi

            # Test 3: Update patient
            print_test "Update patient intake"

            local update_data='{"pain_level": 5}'
            if result=$(api_call "PATCH" "/api/intake/patient/$patient_id" "$update_data"); then
                print_success "Patient intake updated"
            else
                print_failure "Failed to update patient"
            fi
        else
            print_failure "Patient ID not returned"
        fi
    else
        print_failure "Failed to create patient intake"
    fi
}

test_appointment_scheduling() {
    print_header "Test Suite: Appointment Scheduling"

    # Test 1: Create appointment
    print_test "Schedule new appointment"

    local appt_data='{
        "patient_id": 1,
        "therapist_id": 1,
        "scheduled_start": "'$(date -d 'tomorrow 10:00' '+%Y-%m-%dT%H:%M:%S')'",
        "scheduled_end": "'$(date -d 'tomorrow 11:00' '+%Y-%m-%dT%H:%M:%S')'",
        "visit_type": "PT",
        "status": "scheduled"
    }'

    if result=$(api_call "POST" "/api/appointments" "$appt_data"); then
        appt_id=$(echo "$result" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)

        if [ -n "$appt_id" ]; then
            print_success "Appointment scheduled (ID: $appt_id)"

            # Test 2: Get appointment details
            print_test "Retrieve appointment details"

            if result=$(api_call "GET" "/api/appointments/$appt_id"); then
                print_success "Appointment details retrieved"
            else
                print_failure "Failed to retrieve appointment"
            fi

            # Test 3: Update appointment
            print_test "Update appointment status"

            local update_data='{"status": "confirmed"}'
            if result=$(api_call "PATCH" "/api/appointments/$appt_id" "$update_data"); then
                print_success "Appointment status updated"
            else
                print_failure "Failed to update appointment"
            fi
        else
            print_failure "Appointment ID not returned"
        fi
    else
        print_failure "Failed to schedule appointment"
    fi
}

test_insurance_verification() {
    print_header "Test Suite: Insurance Verification"

    # Test 1: Verify insurance eligibility
    print_test "Verify insurance eligibility"

    local insurance_data='{
        "payer_name": "Blue Cross Blue Shield",
        "member_id": "TEST123456789",
        "date_of_service": "'$(date +%Y-%m-%d)'",
        "service_type_code": "30"
    }'

    if result=$(api_call "POST" "/api/insurance/verify" "$insurance_data"); then
        if echo "$result" | grep -q "verification_status"; then
            print_success "Insurance verification completed"

            # Check for coverage details
            if echo "$result" | grep -q "copay_amount"; then
                print_success "Copay information returned"
            else
                print_failure "Copay information missing"
            fi

            if echo "$result" | grep -q "deductible"; then
                print_success "Deductible information returned"
            else
                print_failure "Deductible information missing"
            fi
        else
            print_failure "Verification status missing"
        fi
    else
        print_failure "Insurance verification failed"
    fi
}

test_claims_submission() {
    print_header "Test Suite: Claims Submission"

    # Test 1: Auto-generate claim from appointment
    print_test "Auto-generate claim from appointment"

    local claim_data='{
        "appointment_id": 1,
        "auto_generate": true
    }'

    if result=$(api_call "POST" "/api/claims/auto-generate" "$claim_data"); then
        claim_id=$(echo "$result" | grep -o '"claim_number":"[^"]*"' | head -1 | cut -d'"' -f4)

        if [ -n "$claim_id" ]; then
            print_success "Claim auto-generated (Number: $claim_id)"

            # Test 2: Submit claim
            print_test "Submit claim to clearinghouse"

            if result=$(api_call "POST" "/api/claims/$claim_id/submit" "{}"); then
                if echo "$result" | grep -q "status"; then
                    print_success "Claim submitted"
                else
                    print_failure "Claim submission status missing"
                fi
            else
                print_failure "Failed to submit claim"
            fi

            # Test 3: Check claim status
            print_test "Check claim status"

            if result=$(api_call "GET" "/api/claims/$claim_id/status"); then
                print_success "Claim status retrieved"
            else
                print_failure "Failed to retrieve claim status"
            fi
        else
            print_failure "Claim number not returned"
        fi
    else
        print_failure "Failed to auto-generate claim"
    fi
}

test_vector_database() {
    print_header "Test Suite: Vector Database / Memory Engine"

    # Test 1: Search similar cases
    print_test "Search for similar cases"

    local search_data='{
        "query": "shoulder pain rotator cuff",
        "diagnosis": "tendinopathy",
        "limit": 5
    }'

    if result=$(api_call "POST" "/api/memory/search" "$search_data"); then
        if echo "$result" | grep -q "similar_cases"; then
            case_count=$(echo "$result" | grep -o '"case_id"' | wc -l)
            print_success "Similar cases found (Count: $case_count)"
        else
            print_failure "No similar cases structure in response"
        fi
    else
        print_failure "Similar cases search failed"
    fi

    # Test 2: Get treatment recommendations
    print_test "Get evidence-based treatment recommendations"

    local rec_data='{
        "diagnosis": "rotator cuff tendinopathy",
        "patient_age": 45,
        "severity": "moderate"
    }'

    if result=$(api_call "POST" "/api/memory/recommend-treatment" "$rec_data"); then
        if echo "$result" | grep -q "recommendations"; then
            print_success "Treatment recommendations retrieved"
        else
            print_failure "Recommendations structure missing"
        fi
    else
        print_failure "Treatment recommendation failed"
    fi
}

test_natural_language_interface() {
    print_header "Test Suite: Natural Language Interface"

    # Test 1: Schedule appointment via NL
    print_test "Schedule appointment using natural language"

    local nl_data='{
        "command": "Schedule John Doe for PT eval next Tuesday at 10am",
        "user_context": {
            "role": "front_desk",
            "user_id": 1
        }
    }'

    if result=$(api_call "POST" "/api/nl/command" "$nl_data"); then
        if echo "$result" | grep -q "intent"; then
            intent=$(echo "$result" | grep -o '"intent":"[^"]*"' | cut -d'"' -f4)
            print_success "Intent classified: $intent"

            if [ "$intent" = "schedule_appointment" ]; then
                print_success "Intent correctly identified"
            else
                print_failure "Intent incorrectly classified"
            fi
        else
            print_failure "Intent classification failed"
        fi
    else
        print_failure "Natural language processing failed"
    fi

    # Test 2: Query analytics via NL
    print_test "Query analytics using natural language"

    local analytics_nl='{
        "command": "What is the no-show rate this month?",
        "user_context": {
            "role": "admin",
            "user_id": 1
        }
    }'

    if result=$(api_call "POST" "/api/nl/command" "$analytics_nl"); then
        if echo "$result" | grep -q "response"; then
            print_success "Analytics query processed"
        else
            print_failure "Analytics response missing"
        fi
    else
        print_failure "Analytics query failed"
    fi
}

test_emr_integration() {
    print_header "Test Suite: EMR Integration (HelloNote)"

    # Test 1: Test EMR credentials
    print_test "Verify EMR credentials configured"

    if result=$(api_call "GET" "/api/emr/status"); then
        if echo "$result" | grep -q "emr_configured"; then
            print_success "EMR credentials configured"
        else
            print_failure "EMR not configured"
        fi
    else
        print_failure "EMR status check failed"
    fi

    # Test 2: Submit note to EMR (dry run)
    print_test "Dry run: Submit SOAP note to HelloNote"

    local emr_data='{
        "note_id": 1,
        "dry_run": true
    }'

    if result=$(api_call "POST" "/api/emr/submit-note" "$emr_data"); then
        if echo "$result" | grep -q "workflow"; then
            print_success "EMR workflow generated"
        else
            print_failure "EMR workflow missing"
        fi
    else
        print_failure "EMR submission dry run failed"
    fi
}

###############################################################################
# Performance Tests
###############################################################################

test_performance() {
    print_header "Test Suite: Performance"

    # Test 1: API response time
    print_test "API response time (health endpoint)"

    local start_time=$(date +%s%N)
    api_call "GET" "/health" > /dev/null
    local end_time=$(date +%s%N)
    local response_time=$(( (end_time - start_time) / 1000000 ))

    if [ "$response_time" -lt 200 ]; then
        print_success "Response time: ${response_time}ms (excellent)"
    elif [ "$response_time" -lt 500 ]; then
        print_success "Response time: ${response_time}ms (good)"
    else
        print_failure "Response time: ${response_time}ms (slow)"
    fi

    # Test 2: Concurrent requests
    print_test "Handle concurrent requests"

    local concurrent_count=10
    for i in $(seq 1 $concurrent_count); do
        api_call "GET" "/health" > /dev/null &
    done
    wait

    if [ $? -eq 0 ]; then
        print_success "Handled $concurrent_count concurrent requests"
    else
        print_failure "Failed to handle concurrent requests"
    fi
}

###############################################################################
# Main Test Execution
###############################################################################

print_header "Healthcare Agent Platform - Integration Tests"
echo "API URL: $API_URL"
echo "Started at: $(date)"
echo ""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Run all test suites
test_soap_note_workflow
test_patient_intake_workflow
test_appointment_scheduling
test_insurance_verification
test_claims_submission
test_vector_database
test_natural_language_interface
test_emr_integration
test_performance

# Print summary
print_header "Test Summary"
echo ""
echo -e "${GREEN}Tests Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Tests Failed:${NC} $TESTS_FAILED"
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
    echo "Success Rate: ${SUCCESS_RATE}%"
fi

echo ""
echo "Completed at: $(date)"
echo ""

# Print detailed results
if [ "$VERBOSE" = true ]; then
    echo "Detailed Results:"
    for result in "${TEST_RESULTS[@]}"; do
        echo "  $result"
    done
    echo ""
fi

# Exit with appropriate code
if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL INTEGRATION TESTS PASSED${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME INTEGRATION TESTS FAILED${NC}"
    exit 1
fi
