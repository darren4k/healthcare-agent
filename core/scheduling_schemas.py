"""Pydantic schemas for scheduling and visit management."""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict
from datetime import datetime, date
from enum import Enum


class VisitTypeEnum(str, Enum):
    """Visit types."""
    EVALUATION = "evaluation"
    TREATMENT = "treatment"
    RE_EVALUATION = "re_evaluation"
    DISCHARGE = "discharge"
    TELEHEALTH = "telehealth"


class TherapySpecialtyEnum(str, Enum):
    """Therapy specialties."""
    PHYSICAL_THERAPY = "physical_therapy"
    OCCUPATIONAL_THERAPY = "occupational_therapy"
    SPEECH_THERAPY = "speech_therapy"
    GENERAL = "general"


class AppointmentStatusEnum(str, Enum):
    """Appointment status."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


# ========== Patient Intake Schemas ==========

class PatientIntakeCreate(BaseModel):
    """Patient intake submission."""

    # Demographics
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    phone_number: str = Field(..., regex=r'^\+?1?\d{10,15}$')
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    zip_code: Optional[str] = Field(None, regex=r'^\d{5}(-\d{4})?$')

    # Emergency Contact
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, regex=r'^\+?1?\d{10,15}$')
    emergency_contact_relationship: Optional[str] = Field(None, max_length=50)

    # Insurance
    primary_insurance_name: Optional[str] = Field(None, max_length=255)
    primary_insurance_id: Optional[str] = Field(None, max_length=100)
    primary_insurance_group: Optional[str] = Field(None, max_length=100)
    secondary_insurance_name: Optional[str] = Field(None, max_length=255)
    secondary_insurance_id: Optional[str] = Field(None, max_length=100)

    # Clinical
    referring_physician: Optional[str] = Field(None, max_length=255)
    diagnosis: Optional[str] = None
    medical_history: Optional[str] = None
    medications: Optional[str] = None
    allergies: Optional[str] = None

    # Preferences
    preferred_therapist_id: Optional[int] = None
    preferred_day_of_week: Optional[List[str]] = None  # ["monday", "wednesday"]
    preferred_time_of_day: Optional[str] = Field(None, regex=r'^(morning|afternoon|evening)$')
    language_preference: Optional[str] = Field(None, max_length=50)
    special_accommodations: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "1980-05-15",
                "phone_number": "5551234567",
                "email": "john.doe@example.com",
                "primary_insurance_name": "Blue Cross Blue Shield",
                "primary_insurance_id": "ABC123456789",
                "diagnosis": "Low back pain",
                "preferred_time_of_day": "morning"
            }
        }


class PatientIntakeResponse(BaseModel):
    """Patient intake response."""
    id: int
    first_name: str
    last_name: str
    intake_status: str
    insurance_status: str
    submitted_at: datetime

    class Config:
        orm_mode = True


# ========== Scheduling Schemas ==========

class TherapistAvailability(BaseModel):
    """Therapist availability for scheduling."""
    therapist_id: int
    available_slots: List[datetime]
    caseload: int
    max_patients_per_day: int


class AppointmentCreate(BaseModel):
    """Create new appointment."""
    patient_intake_id: int
    therapist_id: Optional[int] = None  # Auto-assign if None
    facility_id: Optional[int] = None
    scheduled_start: datetime
    duration_minutes: int = Field(default=45, ge=15, le=180)
    visit_type: VisitTypeEnum = VisitTypeEnum.TREATMENT
    chief_complaint: Optional[str] = None
    scheduling_notes: Optional[str] = None

    # Recurring
    is_recurring: bool = False
    recurring_pattern: Optional[Dict] = None  # {"frequency": "weekly", "count": 8}

    class Config:
        schema_extra = {
            "example": {
                "patient_intake_id": 1,
                "scheduled_start": "2025-11-15T10:00:00",
                "duration_minutes": 45,
                "visit_type": "evaluation",
                "chief_complaint": "Right shoulder pain"
            }
        }


class AppointmentUpdate(BaseModel):
    """Update appointment."""
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    status: Optional[AppointmentStatusEnum] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    scheduling_notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Appointment response."""
    id: int
    patient_intake_id: int
    therapist_id: int
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    visit_type: str
    status: str
    is_recurring: bool
    created_at: datetime

    class Config:
        orm_mode = True


class AppointmentListResponse(BaseModel):
    """List of appointments."""
    appointments: List[AppointmentResponse]
    total: int
    page: int
    page_size: int


# ========== Therapist Assignment Schemas ==========

class TherapistAssignmentRequest(BaseModel):
    """Request for therapist assignment."""
    patient_intake_id: int
    required_specialty: Optional[TherapySpecialtyEnum] = None
    preferred_therapist_id: Optional[int] = None
    appointment_datetime: datetime
    duration_minutes: int = 45
    facility_id: Optional[int] = None


class TherapistAssignmentResponse(BaseModel):
    """Therapist assignment result."""
    therapist_id: int
    therapist_name: str
    specialty: str
    confidence_score: float = Field(..., ge=0, le=100)
    reason: str
    available_slot: datetime

    class Config:
        schema_extra = {
            "example": {
                "therapist_id": 5,
                "therapist_name": "Dr. Sarah Johnson",
                "specialty": "physical_therapy",
                "confidence_score": 95.5,
                "reason": "Perfect specialty match, available at requested time, low caseload",
                "available_slot": "2025-11-15T10:00:00"
            }
        }


# ========== Insurance Verification Schemas ==========

class InsuranceVerificationRequest(BaseModel):
    """Request insurance verification."""
    patient_intake_id: int
    payer_name: str
    member_id: str
    group_number: Optional[str] = None
    date_of_service: date

    class Config:
        schema_extra = {
            "example": {
                "patient_intake_id": 1,
                "payer_name": "Blue Cross Blue Shield",
                "member_id": "ABC123456789",
                "date_of_service": "2025-11-15"
            }
        }


class InsuranceVerificationResponse(BaseModel):
    """Insurance verification results."""
    verification_id: int
    verification_status: str
    is_active: bool
    effective_date: Optional[date] = None
    termination_date: Optional[date] = None
    copay_amount: Optional[float] = None
    deductible_amount: Optional[float] = None
    deductible_met: Optional[float] = None
    requires_authorization: bool = False
    visits_authorized: Optional[int] = None
    verified_at: datetime

    class Config:
        orm_mode = True


# ========== Reminder Schemas ==========

class ReminderCreate(BaseModel):
    """Create appointment reminder."""
    appointment_id: int
    reminder_type: str = Field(..., regex=r'^(sms|email|push)$')
    hours_before: int = Field(..., ge=1, le=168)  # 1 hour to 1 week
    message_template: Optional[str] = None


class ReminderResponse(BaseModel):
    """Reminder response."""
    id: int
    appointment_id: int
    reminder_type: str
    reminder_time: datetime
    hours_before: int
    sent_at: Optional[datetime] = None
    delivery_status: Optional[str] = None

    class Config:
        orm_mode = True


# ========== Check-In/Check-Out Schemas ==========

class CheckInRequest(BaseModel):
    """Patient check-in."""
    appointment_id: int
    check_in_time: Optional[datetime] = None  # Default to now
    copay_collected: bool = False
    copay_amount: Optional[float] = None
    notes: Optional[str] = None


class CheckOutRequest(BaseModel):
    """Patient check-out."""
    appointment_id: int
    check_out_time: Optional[datetime] = None  # Default to now
    session_notes_id: Optional[int] = None  # Link to note draft
    next_appointment_scheduled: bool = False
    next_appointment_id: Optional[int] = None


# ========== No-Show Prediction Schemas ==========

class NoShowPredictionRequest(BaseModel):
    """Request no-show prediction."""
    appointment_id: int


class NoShowPredictionResponse(BaseModel):
    """No-show risk prediction."""
    appointment_id: int
    risk_score: float = Field(..., ge=0, le=100)
    risk_level: str = Field(..., regex=r'^(low|medium|high)$')
    risk_factors: List[str]
    recommendations: List[str]

    class Config:
        schema_extra = {
            "example": {
                "appointment_id": 123,
                "risk_score": 65.3,
                "risk_level": "medium",
                "risk_factors": [
                    "Patient has 2 previous no-shows",
                    "Appointment is early morning (8 AM)",
                    "No reminder confirmation received"
                ],
                "recommendations": [
                    "Send additional reminder 2 hours before",
                    "Call patient to confirm",
                    "Offer reschedule if needed"
                ]
            }
        }


# ========== Analytics Schemas ==========

class ScheduleAnalytics(BaseModel):
    """Schedule analytics response."""
    total_appointments: int
    scheduled: int
    completed: int
    cancelled: int
    no_shows: int
    fill_rate: float  # percentage
    average_duration_minutes: float
    top_visit_types: Dict[str, int]
    busiest_time_slots: List[Dict[str, any]]


class TherapistProductivityMetrics(BaseModel):
    """Therapist productivity metrics."""
    therapist_id: int
    therapist_name: str
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_shows: int
    average_session_duration: float
    total_billable_minutes: int
    utilization_rate: float  # percentage
    patient_satisfaction: Optional[float] = None
    documentation_completion_rate: float
