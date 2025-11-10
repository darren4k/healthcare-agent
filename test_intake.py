"""Simple Python test script for the intake API."""
import requests
import json
from datetime import datetime
from typing import Dict, Any


BASE_URL = "http://localhost:8001"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")


def test_health_check():
    """Test the health check endpoint."""
    print("Testing: GET /health")

    response = requests.get(f"{BASE_URL}/health")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200, "Health check failed"
    assert response.json()["status"] == "healthy", "Status not healthy"

    print("✓ Health check passed")


def test_submit_note() -> int:
    """Test submitting a clinical note."""
    print("Testing: POST /api/intake")

    payload = {
        "patient_id": "PT-TEST-001",
        "raw_input": (
            "Patient ambulated 150 feet with rolling walker. "
            "Reports decreased pain in right hip, now 2/10. "
            "Balance has improved significantly. "
            "Plan to transition to cane next week."
        ),
        "visit_date": datetime.now().isoformat(),
        "visit_type": "PT",
        "submitted_by": "Sarah Thompson, PT",
        "source": "api_direct",
        "patient_first_name": "Alice",
        "patient_last_name": "Williams",
        "patient_dob": "1958-03-12T00:00:00"
    }

    print(f"Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(
        f"{BASE_URL}/api/intake",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201, f"Failed to submit note: {response.text}"

    task_id = response.json()["task_id"]
    print(f"✓ Note submitted successfully. Task ID: {task_id}")

    return task_id


def test_get_task_status(task_id: int):
    """Test retrieving task status."""
    print(f"Testing: GET /api/tasks/{task_id}")

    response = requests.get(f"{BASE_URL}/api/tasks/{task_id}")

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    assert response.status_code == 200, "Failed to get task status"

    # Check for SOAP components
    if data.get("soap_components"):
        print("\n" + "-"*60)
        print("SOAP Components:")
        print("-"*60)
        soap = data["soap_components"]
        print(f"\nSubjective:\n{soap['subjective']}")
        print(f"\nObjective:\n{soap['objective']}")
        print(f"\nAssessment:\n{soap['assessment']}")
        print(f"\nPlan:\n{soap['plan']}")
        print(f"\nConfidence Score: {soap['confidence_score']}%")
        print("-"*60)

    print(f"✓ Task status retrieved. Status: {data['status']}")


def main():
    """Run all tests."""
    print_section("Agentic SOAP Note System - API Tests")

    try:
        # Test 1: Health Check
        print_section("Test 1: Health Check")
        test_health_check()

        # Test 2: Submit Note
        print_section("Test 2: Submit Clinical Note")
        task_id = test_submit_note()

        # Test 3: Get Task Status
        print_section("Test 3: Get Task Status")
        test_get_task_status(task_id)

        print_section("✓ All Tests Passed")

    except AssertionError as e:
        print(f"\n✗ Test Failed: {e}")
        return 1
    except requests.exceptions.ConnectionError:
        print("\n✗ Connection Error: Is the API server running?")
        print(f"   Make sure the server is running at {BASE_URL}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
