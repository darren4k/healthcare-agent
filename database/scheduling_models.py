"""Database models for scheduling and visit management."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from database.session import Base


class AppointmentStatus(enum.Enum):
    """Appointment status enum."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class TherapistSpecialty(enum.Enum):
    """Therapist specialty enum."""
    PHYSICAL_THERAPY = "physical_therapy"
    OCCUPATIONAL_THERAPY = "occupational_therapy"
    SPEECH_THERAPY = "speech_therapy"
    GENERAL = "general"


class VisitType(enum.Enum):
    """Visit type enum."""
    EVALUATION = "evaluation"
    TREATMENT = "treatment"
    RE_EVALUATION = "re_evaluation"
    DISCHARGE = "discharge"
    TELEHEALTH = "telehealth"


class InsuranceStatus(enum.Enum):
    """Insurance verification status."""
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    INVALID = "invalid"
    AUTH_REQUIRED = "auth_required"


class PatientIntake(Base):
    """Patient intake information."""
    __tablename__ = "patient_intakes"

    id = Column(Integer, primary_key=True, index=True)

    # Patient Demographics
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(DateTime, nullable=False)
    phone_number = Column(String(20), nullable=False)
    email = Column(String(255))
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))

    # Emergency Contact
    emergency_contact_name = Column(String(200))
    emergency_contact_phone = Column(String(20))
    emergency_contact_relationship = Column(String(50))

    # Insurance Information
    primary_insurance_name = Column(String(255))
    primary_insurance_id = Column(String(100))
    primary_insurance_group = Column(String(100))
    secondary_insurance_name = Column(String(255))
    secondary_insurance_id = Column(String(100))

    # Clinical Information
    referring_physician = Column(String(255))
    diagnosis = Column(Text)
    medical_history = Column(Text)
    medications = Column(Text)
    allergies = Column(Text)

    # Intake Preferences
    preferred_therapist_id = Column(Integer, ForeignKey("therapists.id"))
    preferred_day_of_week = Column(String(20))  # JSON array
    preferred_time_of_day = Column(String(20))  # morning, afternoon, evening
    language_preference = Column(String(50))
    special_accommodations = Column(Text)

    # Status
    intake_status = Column(String(50), default="pending")  # pending, in_review, approved, rejected
    insurance_status = Column(Enum(InsuranceStatus), default=InsuranceStatus.PENDING)

    # Metadata
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Documents
    documents = Column(JSON)  # List of uploaded document paths

    # Relationships
    appointments = relationship("Appointment", back_populates="intake")


class Therapist(Base):
    """Therapist profile and availability."""
    __tablename__ = "therapists"

    id = Column(Integer, primary_key=True, index=True)

    # Basic Info
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(20))

    # Professional Info
    license_number = Column(String(100))
    license_state = Column(String(2))
    specialty = Column(Enum(TherapistSpecialty), default=TherapistSpecialty.GENERAL)
    subspecialties = Column(JSON)  # List of additional specialties
    years_experience = Column(Integer)
    certifications = Column(JSON)  # List of certifications
    languages = Column(JSON)  # List of languages spoken

    # Availability
    is_active = Column(Boolean, default=True)
    is_accepting_patients = Column(Boolean, default=True)
    max_patients_per_day = Column(Integer, default=8)
    default_appointment_duration = Column(Integer, default=45)  # minutes

    # Work Schedule (JSON)
    # Example: {"monday": [{"start": "08:00", "end": "17:00"}], ...}
    work_schedule = Column(JSON)

    # Location
    primary_facility_id = Column(Integer, ForeignKey("facilities.id"))
    mobile_therapy = Column(Boolean, default=False)
    service_area_radius = Column(Float)  # miles, for mobile therapy

    # Performance Metrics
    current_caseload = Column(Integer, default=0)
    average_rating = Column(Float)
    total_patients_treated = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointments = relationship("Appointment", back_populates="therapist")
    time_off_requests = relationship("TimeOffRequest", back_populates="therapist")


class Facility(Base):
    """Physical therapy facility/clinic."""
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True, index=True)

    # Basic Info
    name = Column(String(255), nullable=False)
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    phone_number = Column(String(20))
    email = Column(String(255))

    # Operational Info
    is_active = Column(Boolean, default=True)
    timezone = Column(String(50), default="America/Chicago")
    operating_hours = Column(JSON)  # Similar format to therapist work_schedule

    # Equipment/Rooms
    treatment_rooms = Column(Integer, default=1)
    equipment_list = Column(JSON)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    therapists = relationship("Therapist", back_populates="primary_facility")
    appointments = relationship("Appointment", back_populates="facility")


class Appointment(Base):
    """Patient appointment."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)

    # Core Info
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)
    facility_id = Column(Integer, ForeignKey("facilities.id"))

    # Scheduling
    scheduled_start = Column(DateTime, nullable=False, index=True)
    scheduled_end = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=45)

    # Actual Times
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    check_in_time = Column(DateTime)
    check_out_time = Column(DateTime)

    # Appointment Details
    visit_type = Column(Enum(VisitType), default=VisitType.TREATMENT)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    is_recurring = Column(Boolean, default=False)
    recurring_pattern = Column(JSON)  # For recurring appointments

    # Clinical
    chief_complaint = Column(Text)
    treatment_goals = Column(JSON)

    # Administrative
    copay_amount = Column(Float)
    copay_collected = Column(Boolean, default=False)
    authorization_number = Column(String(100))
    visits_authorized = Column(Integer)
    visit_number = Column(Integer)  # Which visit in the series

    # Communication
    reminder_sent_24h = Column(Boolean, default=False)
    reminder_sent_2h = Column(Boolean, default=False)
    confirmation_received = Column(Boolean, default=False)

    # Cancellation/Rescheduling
    cancellation_reason = Column(Text)
    cancelled_by = Column(String(50))  # patient, therapist, system
    cancelled_at = Column(DateTime)
    rescheduled_from_id = Column(Integer, ForeignKey("appointments.id"))
    rescheduled_to_id = Column(Integer, ForeignKey("appointments.id"))

    # Notes
    scheduling_notes = Column(Text)
    session_notes_id = Column(Integer, ForeignKey("note_drafts.id"))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    intake = relationship("PatientIntake", back_populates="appointments")
    therapist = relationship("Therapist", back_populates="appointments")
    facility = relationship("Facility", back_populates="appointments")
    reminders = relationship("AppointmentReminder", back_populates="appointment")


class AppointmentReminder(Base):
    """Appointment reminder tracking."""
    __tablename__ = "appointment_reminders"

    id = Column(Integer, primary_key=True, index=True)

    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)

    # Reminder Details
    reminder_type = Column(String(50))  # sms, email, push
    reminder_time = Column(DateTime, nullable=False)  # When to send
    hours_before = Column(Integer)  # 24, 2, etc.

    # Status
    sent_at = Column(DateTime)
    delivery_status = Column(String(50))  # sent, delivered, failed, bounced
    delivery_error = Column(Text)

    # Response
    response_received = Column(Boolean, default=False)
    response_type = Column(String(50))  # confirm, reschedule, cancel
    response_at = Column(DateTime)

    # Content
    message_template = Column(String(100))
    message_sent = Column(Text)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    appointment = relationship("Appointment", back_populates="reminders")


class TimeOffRequest(Base):
    """Therapist time off requests."""
    __tablename__ = "time_off_requests"

    id = Column(Integer, primary_key=True, index=True)

    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)

    # Time Off Details
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    reason = Column(String(50))  # vacation, sick, personal, training
    notes = Column(Text)

    # Approval
    status = Column(String(50), default="pending")  # pending, approved, denied
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    denial_reason = Column(Text)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    therapist = relationship("Therapist", back_populates="time_off_requests")


class InsuranceVerification(Base):
    """Insurance eligibility verification results."""
    __tablename__ = "insurance_verifications"

    id = Column(Integer, primary_key=True, index=True)

    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"))

    # Insurance Info
    payer_name = Column(String(255))
    member_id = Column(String(100))
    group_number = Column(String(100))

    # Verification Results
    verification_status = Column(Enum(InsuranceStatus))
    verified_at = Column(DateTime)
    verified_by = Column(String(50))  # system, manual

    # Coverage Details
    is_active = Column(Boolean)
    effective_date = Column(DateTime)
    termination_date = Column(DateTime)
    copay_amount = Column(Float)
    deductible_amount = Column(Float)
    deductible_met = Column(Float)
    out_of_pocket_max = Column(Float)
    out_of_pocket_met = Column(Float)

    # Authorization
    requires_authorization = Column(Boolean, default=False)
    visits_authorized = Column(Integer)
    visits_used = Column(Integer, default=0)
    authorization_number = Column(String(100))
    authorization_expires = Column(DateTime)

    # Response Data
    raw_response = Column(JSON)  # Full API response or scraped data

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Add relationships to existing models
Therapist.primary_facility = relationship("Facility", back_populates="therapists")
Facility.therapists = relationship("Therapist", back_populates="primary_facility")
Facility.appointments = relationship("Appointment", back_populates="facility")
