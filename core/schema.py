"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class NoteSourceEnum(str, Enum):
    """Source of the clinical note input."""
    WEB_PORTAL = "web_portal"
    SLACK_BOT = "slack_bot"
    EMAIL = "email"
    API_DIRECT = "api_direct"


class VisitTypeEnum(str, Enum):
    """Type of clinical visit."""
    PT = "PT"  # Physical Therapy
    OT = "OT"  # Occupational Therapy
    SLP = "SLP"  # Speech-Language Pathology
    NURSING = "Nursing"
    HOME_HEALTH = "Home Health"
    SNF = "SNF"  # Skilled Nursing Facility


class TaskStatusEnum(str, Enum):
    """Task processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    LLM_COMPLETE = "llm_complete"
    BROWSER_RUNNING = "browser_running"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


# =============================
# Request Schemas
# =============================

class NoteIntakeRequest(BaseModel):
    """Request schema for submitting raw clinical notes."""

    patient_id: str = Field(
        ...,
        description="Unique patient identifier",
        min_length=1,
        max_length=50,
        examples=["PT-12345"]
    )

    raw_input: str = Field(
        ...,
        description="Raw clinical note text from employee",
        min_length=10,
        examples=["Patient walked 100ft with CGA. Reports mild knee pain. Continue strengthening exercises."]
    )

    visit_date: datetime = Field(
        ...,
        description="Date and time of the visit",
        examples=["2025-11-10T14:30:00"]
    )

    visit_type: VisitTypeEnum = Field(
        ...,
        description="Type of clinical visit",
        examples=["PT"]
    )

    submitted_by: str = Field(
        ...,
        description="Name or ID of employee submitting the note",
        min_length=1,
        max_length=100,
        examples=["Jane Smith, PTA"]
    )

    source: NoteSourceEnum = Field(
        default=NoteSourceEnum.API_DIRECT,
        description="Source channel of the submission"
    )

    # Optional patient creation fields
    patient_first_name: Optional[str] = Field(None, max_length=100)
    patient_last_name: Optional[str] = Field(None, max_length=100)
    patient_dob: Optional[datetime] = None
    emr_patient_id: Optional[str] = Field(None, max_length=100)

    @field_validator('raw_input')
    @classmethod
    def validate_raw_input(cls, v: str) -> str:
        """Ensure raw input is not just whitespace."""
        if not v.strip():
            raise ValueError("Raw input cannot be empty or whitespace")
        return v.strip()


# =============================
# Response Schemas
# =============================

class SOAPComponents(BaseModel):
    """Structured SOAP note components."""
    subjective: str = Field(..., description="Subjective section")
    objective: str = Field(..., description="Objective section")
    assessment: str = Field(..., description="Assessment section")
    plan: str = Field(..., description="Plan section")
    confidence_score: Optional[int] = Field(None, ge=0, le=100, description="AI confidence score")


class NoteIntakeResponse(BaseModel):
    """Response after submitting a note for processing."""

    task_id: int = Field(..., description="Unique task ID for tracking")
    status: TaskStatusEnum = Field(..., description="Current task status")
    message: str = Field(..., description="Human-readable status message")
    created_at: datetime = Field(..., description="Timestamp of task creation")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": 42,
                "status": "pending",
                "message": "Note intake successful. Processing will begin shortly.",
                "created_at": "2025-11-10T15:30:00"
            }
        }


class TaskStatusResponse(BaseModel):
    """Response for checking task status."""

    task_id: int
    status: TaskStatusEnum
    patient_id: str
    visit_date: datetime
    created_at: datetime
    updated_at: datetime

    # Populated when LLM processing is complete
    soap_components: Optional[SOAPComponents] = None

    # Populated when browser automation is complete
    emr_draft_url: Optional[str] = None
    emr_draft_id: Optional[str] = None

    # Error information if failed
    error_message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": 42,
                "status": "llm_complete",
                "patient_id": "PT-12345",
                "visit_date": "2025-11-10T14:30:00",
                "created_at": "2025-11-10T15:30:00",
                "updated_at": "2025-11-10T15:31:00",
                "soap_components": {
                    "subjective": "Patient reports mild knee pain during ambulation.",
                    "objective": "Patient ambulated 100 feet with contact guard assist (CGA). Gait steady.",
                    "assessment": "Patient demonstrating progress in mobility with minimal assistance.",
                    "plan": "Continue strengthening exercises. Progress to supervision level next visit.",
                    "confidence_score": 85
                }
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    app_name: str
    version: str
    environment: str
    timestamp: datetime


# =============================
# Internal Schemas (for LLM)
# =============================

class LLMRequest(BaseModel):
    """Request format for DGX LLM endpoint."""
    prompt: str
    max_tokens: int = 1000
    temperature: float = 0.3
    stop: Optional[list[str]] = None


class LLMResponse(BaseModel):
    """Response format from DGX LLM endpoint."""
    text: str
    # Add other fields as needed based on your LLM server response format
