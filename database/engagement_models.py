"""Patient and caregiver engagement models - HEP, progress tracking, outcomes."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from database.session import Base


class HEPStatus(enum.Enum):
    """Home Exercise Program status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    DISCONTINUED = "discontinued"
    ON_HOLD = "on_hold"


class ExerciseDifficulty(enum.Enum):
    """Exercise difficulty level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ComplianceLevel(enum.Enum):
    """Patient compliance level."""
    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 75-89%
    FAIR = "fair"  # 50-74%
    POOR = "poor"  # < 50%


# ========== Home Exercise Programs ==========

class ExerciseLibrary(Base):
    """Library of exercises with videos/images."""
    __tablename__ = "exercise_library"

    id = Column(Integer, primary_key=True, index=True)

    # Exercise details
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)

    # Media
    video_url = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)
    demo_gif_url = Column(String(500), nullable=True)

    # Categorization
    category = Column(String(100), nullable=False, index=True)  # strength, flexibility, balance, etc.
    body_part = Column(String(100), nullable=False, index=True)  # shoulder, knee, back, etc.
    equipment_needed = Column(JSON, nullable=True)  # List of equipment

    # Difficulty
    difficulty = Column(SQLEnum(ExerciseDifficulty), nullable=False, default=ExerciseDifficulty.BEGINNER)

    # Parameters
    default_sets = Column(Integer, default=3)
    default_reps = Column(Integer, default=10)
    default_hold_seconds = Column(Integer, nullable=True)
    default_frequency_per_week = Column(Integer, default=3)

    # Precautions
    contraindications = Column(JSON, nullable=True)  # List of contraindications
    precautions = Column(Text, nullable=True)

    # Usage tracking
    times_prescribed = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeExerciseProgram(Base):
    """Patient's home exercise program."""
    __tablename__ = "home_exercise_programs"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True, index=True)

    # Program details
    program_name = Column(String(200), nullable=False)
    program_description = Column(Text, nullable=True)

    # Goals
    goals = Column(JSON, nullable=False)  # List of functional goals

    # Status
    status = Column(SQLEnum(HEPStatus), nullable=False, default=HEPStatus.ACTIVE, index=True)

    # Dates
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    last_updated_date = Column(Date, nullable=True)

    # Frequency
    frequency_per_week = Column(Integer, nullable=False, default=3)

    # Instructions
    general_instructions = Column(Text, nullable=True)
    precautions = Column(Text, nullable=True)

    # Compliance tracking
    expected_sessions_per_week = Column(Integer, default=3)
    completed_sessions = Column(Integer, default=0)
    compliance_rate = Column(Float, nullable=True)  # Percentage

    # Patient feedback
    patient_rating = Column(Integer, nullable=True)  # 1-5 stars
    patient_feedback = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    exercises = relationship("HEPExercise", back_populates="program", cascade="all, delete-orphan")
    logs = relationship("HEPLog", back_populates="program")


class HEPExercise(Base):
    """Individual exercise within a HEP."""
    __tablename__ = "hep_exercises"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    program_id = Column(Integer, ForeignKey("home_exercise_programs.id"), nullable=False, index=True)
    exercise_id = Column(Integer, ForeignKey("exercise_library.id"), nullable=False)

    # Order
    sequence_order = Column(Integer, nullable=False)

    # Prescription
    sets = Column(Integer, nullable=False)
    reps = Column(Integer, nullable=False)
    hold_seconds = Column(Integer, nullable=True)
    frequency_per_week = Column(Integer, nullable=False)

    # Progression
    progression_criteria = Column(Text, nullable=True)
    current_level = Column(String(50), default="baseline")

    # Compliance
    times_completed = Column(Integer, default=0)
    expected_completions = Column(Integer, default=0)
    compliance_rate = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    program = relationship("HomeExerciseProgram", back_populates="exercises")


class HEPLog(Base):
    """Patient log entry for HEP completion."""
    __tablename__ = "hep_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    program_id = Column(Integer, ForeignKey("home_exercise_programs.id"), nullable=False, index=True)
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)

    # Log details
    log_date = Column(Date, nullable=False, index=True)
    exercises_completed = Column(JSON, nullable=False)  # List of completed exercise IDs

    # Feedback
    difficulty_rating = Column(Integer, nullable=True)  # 1-5 (1=too easy, 5=too hard)
    pain_level_before = Column(Integer, nullable=True)  # 0-10
    pain_level_after = Column(Integer, nullable=True)  # 0-10
    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    program = relationship("HomeExerciseProgram", back_populates="logs")


# ========== Progress Tracking ==========

class OutcomeMeasure(Base):
    """Standardized outcome measure tools (LEFS, DASH, OPTIMAL etc)."""
    __tablename__ = "outcome_measures"

    id = Column(Integer, primary_key=True, index=True)

    # Measure details
    measure_name = Column(String(200), nullable=False, index=True)
    measure_acronym = Column(String(20), nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Scoring
    min_score = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False)
    mcid = Column(Float, nullable=True)  # Minimal Clinically Important Difference

    # Applicable conditions
    body_regions = Column(JSON, nullable=True)  # List of applicable body regions
    conditions = Column(JSON, nullable=True)  # List of applicable conditions

    # Questions
    questions = Column(JSON, nullable=False)  # List of questions with scoring

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PatientOutcomeScore(Base):
    """Patient's outcome measure score at a point in time."""
    __tablename__ = "patient_outcome_scores"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True, index=True)
    outcome_measure_id = Column(Integer, ForeignKey("outcome_measures.id"), nullable=False, index=True)

    # Score
    total_score = Column(Float, nullable=False)
    percentage_score = Column(Float, nullable=True)  # Normalized to 0-100

    # Timing
    assessment_type = Column(String(50), nullable=False, index=True)  # initial, interim, discharge
    assessment_date = Column(Date, nullable=False, index=True)

    # Responses
    responses = Column(JSON, nullable=False)  # Dict of question_id: response

    # Interpretation
    interpretation = Column(Text, nullable=True)

    # Change from baseline
    change_from_baseline = Column(Float, nullable=True)
    exceeds_mcid = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FunctionalGoal(Base):
    """Patient functional goals (SMART goals)."""
    __tablename__ = "functional_goals"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)

    # Goal details
    goal_statement = Column(Text, nullable=False)  # Specific, Measurable, Achievable goal

    # SMART components
    specific_action = Column(String(500), nullable=False)  # What patient will do
    measurable_criteria = Column(String(500), nullable=False)  # How success is measured
    timeframe_weeks = Column(Integer, nullable=False)  # Expected time to achieve

    # Current status
    status = Column(String(50), nullable=False, default="active", index=True)  # active, achieved, modified, discontinued
    progress_percentage = Column(Integer, default=0)  # 0-100%

    # Dates
    set_date = Column(Date, nullable=False)
    target_date = Column(Date, nullable=False)
    achieved_date = Column(Date, nullable=True)

    # Tracking
    baseline_performance = Column(String(500), nullable=True)
    current_performance = Column(String(500), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProgressNote(Base):
    """Patient progress updates between formal evaluations."""
    __tablename__ = "progress_notes"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)

    # Progress details
    note_date = Column(Date, nullable=False, index=True)
    progress_summary = Column(Text, nullable=False)

    # Objective measurements
    measurements = Column(JSON, nullable=True)  # Dict of measurement_name: value

    # Pain tracking
    pain_level = Column(Integer, nullable=True)  # 0-10
    pain_location = Column(String(200), nullable=True)

    # Function tracking
    functional_improvements = Column(JSON, nullable=True)  # List of improvements
    functional_limitations = Column(JSON, nullable=True)  # List of remaining limitations

    # Treatment response
    treatment_response = Column(String(50), nullable=True)  # excellent, good, fair, poor

    # Plan updates
    plan_updates = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ========== Patient Communication ==========

class PatientMessage(Base):
    """Secure messaging between patient and care team."""
    __tablename__ = "patient_messages"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=True)

    # Message details
    subject = Column(String(200), nullable=False)
    message_body = Column(Text, nullable=False)

    # Direction
    from_patient = Column(Boolean, nullable=False)  # True if patient sent, False if therapist sent

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    # Priority
    is_urgent = Column(Boolean, default=False)

    # Response
    response_required = Column(Boolean, default=False)
    responded_at = Column(DateTime, nullable=True)

    # Thread
    thread_id = Column(String(100), nullable=True, index=True)  # For grouping related messages

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EducationalResource(Base):
    """Educational materials shared with patients."""
    __tablename__ = "educational_resources"

    id = Column(Integer, primary_key=True, index=True)

    # Resource details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    content_type = Column(String(50), nullable=False)  # article, video, pdf, infographic

    # Content
    content_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)

    # Categorization
    category = Column(String(100), nullable=False, index=True)  # condition, exercise, recovery, etc.
    tags = Column(JSON, nullable=True)  # List of tags

    # Applicable conditions
    conditions = Column(JSON, nullable=True)  # List of applicable diagnoses

    # Usage tracking
    times_shared = Column(Integer, default=0)
    avg_rating = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PatientEducationAssignment(Base):
    """Educational resources assigned to specific patients."""
    __tablename__ = "patient_education_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("educational_resources.id"), nullable=False)

    # Assignment details
    assigned_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)

    # Completion tracking
    viewed = Column(Boolean, default=False)
    viewed_at = Column(DateTime, nullable=True)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    # Feedback
    patient_rating = Column(Integer, nullable=True)  # 1-5
    patient_feedback = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
