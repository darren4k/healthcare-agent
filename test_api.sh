#!/bin/bash
# Test script for Agentic SOAP Note System API

set -e  # Exit on error

BASE_URL="http://localhost:8001"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Agentic SOAP Note System - API Tests"
echo "========================================"
echo ""

# Test 1: Health Check
echo -e "${YELLOW}Test 1: Health Check${NC}"
echo "GET $BASE_URL/health"
RESPONSE=$(curl -s -w "\n%{http_code}" $BASE_URL/health)
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ PASSED${NC} - Status code: $HTTP_CODE"
    echo "$BODY" | jq .
else
    echo -e "${RED}✗ FAILED${NC} - Status code: $HTTP_CODE"
    echo "$BODY"
fi
echo ""

# Test 2: Submit Note
echo -e "${YELLOW}Test 2: Submit Clinical Note${NC}"
echo "POST $BASE_URL/api/intake"

INTAKE_PAYLOAD='{
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

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST $BASE_URL/api/intake \
  -H "Content-Type: application/json" \
  -d "$INTAKE_PAYLOAD")

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 201 ]; then
    echo -e "${GREEN}✓ PASSED${NC} - Status code: $HTTP_CODE"
    echo "$BODY" | jq .

    # Extract task ID for next test
    TASK_ID=$(echo "$BODY" | jq -r '.task_id')
    echo ""
    echo "Task ID: $TASK_ID"
else
    echo -e "${RED}✗ FAILED${NC} - Status code: $HTTP_CODE"
    echo "$BODY"
    TASK_ID=""
fi
echo ""

# Test 3: Check Task Status
if [ -n "$TASK_ID" ]; then
    echo -e "${YELLOW}Test 3: Check Task Status${NC}"
    echo "GET $BASE_URL/api/tasks/$TASK_ID"

    RESPONSE=$(curl -s -w "\n%{http_code}" $BASE_URL/api/tasks/$TASK_ID)
    HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" -eq 200 ]; then
        echo -e "${GREEN}✓ PASSED${NC} - Status code: $HTTP_CODE"
        echo "$BODY" | jq .

        # Check if SOAP components exist
        STATUS=$(echo "$BODY" | jq -r '.status')
        echo ""
        echo "Task Status: $STATUS"

        if [ "$STATUS" == "llm_complete" ] || [ "$STATUS" == "completed" ]; then
            echo -e "${GREEN}✓ LLM Processing Complete${NC}"

            # Display SOAP components
            echo ""
            echo "SOAP Components:"
            echo "----------------"
            echo "Subjective: $(echo "$BODY" | jq -r '.soap_components.subjective')"
            echo ""
            echo "Objective: $(echo "$BODY" | jq -r '.soap_components.objective')"
            echo ""
            echo "Assessment: $(echo "$BODY" | jq -r '.soap_components.assessment')"
            echo ""
            echo "Plan: $(echo "$BODY" | jq -r '.soap_components.plan')"
            echo ""
            echo "Confidence: $(echo "$BODY" | jq -r '.soap_components.confidence_score')%"
        fi
    else
        echo -e "${RED}✗ FAILED${NC} - Status code: $HTTP_CODE"
        echo "$BODY"
    fi
else
    echo -e "${YELLOW}Test 3: SKIPPED${NC} (no task ID from previous test)"
fi
echo ""

# Test 4: Submit Another Note (Different Visit Type)
echo -e "${YELLOW}Test 4: Submit OT Note${NC}"
echo "POST $BASE_URL/api/intake"

OT_PAYLOAD='{
  "patient_id": "OT-67890",
  "raw_input": "Patient completed ADL training including dressing and grooming. Required moderate assistance with buttons. Demonstrated improved fine motor skills. Recommend adaptive equipment evaluation.",
  "visit_date": "2025-11-10T10:00:00",
  "visit_type": "OT",
  "submitted_by": "Mike Johnson, OTR",
  "source": "web_portal",
  "patient_first_name": "Mary",
  "patient_last_name": "Johnson",
  "patient_dob": "1972-08-22T00:00:00"
}'

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST $BASE_URL/api/intake \
  -H "Content-Type: application/json" \
  -d "$OT_PAYLOAD")

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 201 ]; then
    echo -e "${GREEN}✓ PASSED${NC} - Status code: $HTTP_CODE"
    echo "$BODY" | jq .
else
    echo -e "${RED}✗ FAILED${NC} - Status code: $HTTP_CODE"
    echo "$BODY"
fi
echo ""

echo "========================================"
echo "  Test Suite Complete"
echo "========================================"
