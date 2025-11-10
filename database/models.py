"""SQLAlchemy models for agentic SOAP note system."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class TaskStatus(str, enum.Enum):
    """Task processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    LLM_COMPLETE = "llm_complete"
    BROWSER_RUNNING = "browser_running"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


class NoteSource(str, enum.Enum):
    """Source of the clinical note."""
    WEB_PORTAL = "web_portal"
    SLACK_BOT = "slack_bot"
    EMAIL = "email"
    API_DIRECT = "api_direct"


class Patient(Base):
    """Patient demographic and identifier information."""

    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)

    # Identifiers
    patient_id = Column(String(50), unique=True, nullable=False, index=True)
    emr_patient_id = Column(String(100), index=True)  # EMR-specific ID

    # Demographics
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(DateTime)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    note_drafts = relationship("NoteDraft", back_populates="patient")

    def __repr__(self):
        return f"<Patient {self.patient_id}: {self.first_name} {self.last_name}>"


class NoteDraft(Base):
    """AI-generated SOAP note drafts awaiting clinician review."""

    __tablename__ = "note_drafts"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)

    # Input data
    raw_input = Column(Text, nullable=False)  # Original employee submission
    source = Column(Enum(NoteSource), nullable=False, default=NoteSource.API_DIRECT)
    submitted_by = Column(String(100))  # Employee/staff name or ID

    # Structured SOAP components (AI-generated)
    subjective = Column(Text)
    objective = Column(Text)
    assessment = Column(Text)
    plan = Column(Text)

    # Metadata
    soap_json = Column(JSON)  # Full structured JSON from LLM
    confidence_score = Column(Integer)  # 0-100 LLM confidence

    # Visit information
    visit_date = Column(DateTime, nullable=False)
    visit_type = Column(String(50))  # PT, OT, SLP, Nursing, etc.

    # Processing status
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, index=True)
    error_message = Column(Text)

    # EMR integration
    emr_draft_url = Column(String(500))  # Link to draft in EMR
    emr_draft_id = Column(String(100))
    emr_submitted_at = Column(DateTime)

    # Clinician review
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    finalized_in_emr = Column(Boolean, default=False)

    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="note_drafts")
    task_logs = relationship("TaskLog", back_populates="note_draft")

    def __repr__(self):
        return f"<NoteDraft {self.id}: Patient {self.patient_id} - {self.status}>"


class TaskLog(Base):
    """Detailed audit log of task processing steps."""

    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    note_draft_id = Column(Integer, ForeignKey("note_drafts.id"), nullable=False, index=True)

    # Task execution details
    task_name = Column(String(100), nullable=False)  # e.g., "llm_structuring", "browser_automation"
    status = Column(Enum(TaskStatus), nullable=False)

    # Execution metadata
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Details
    input_data = Column(JSON)  # Snapshot of input
    output_data = Column(JSON)  # Snapshot of output
    error_details = Column(Text)
    retry_count = Column(Integer, default=0)

    # System info
    worker_id = Column(String(100))  # Celery worker or process ID
    ip_address = Column(String(50))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    note_draft = relationship("NoteDraft", back_populates="task_logs")

    def __repr__(self):
        return f"<TaskLog {self.id}: {self.task_name} - {self.status}>"
