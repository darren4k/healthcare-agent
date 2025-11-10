"""Revenue cycle management database models."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from database.session import Base


class ClaimStatus(enum.Enum):
    """Claim processing status."""
    DRAFT = "draft"
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PARTIALLY_APPROVED = "partially_approved"
    DENIED = "denied"
    APPEALED = "appealed"
    PAID = "paid"
    VOIDED = "voided"


class DenialReason(enum.Enum):
    """Common denial reasons."""
    MISSING_INFO = "missing_info"
    INVALID_CODING = "invalid_coding"
    NOT_COVERED = "not_covered"
    AUTH_REQUIRED = "auth_required"
    DUPLICATE_CLAIM = "duplicate_claim"
    TIMELY_FILING = "timely_filing"
    MEDICAL_NECESSITY = "medical_necessity"
    CREDENTIALING = "credentialing"
    OTHER = "other"


class PaymentMethod(enum.Enum):
    """Payment methods."""
    INSURANCE = "insurance"
    PATIENT_CASH = "patient_cash"
    PATIENT_CARD = "patient_card"
    PATIENT_CHECK = "patient_check"
    PAYMENT_PLAN = "payment_plan"
    CHARITY_CARE = "charity_care"


# ========== Insurance Claims ==========

class Claim(Base):
    """Insurance claim for services rendered."""
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, index=True)
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    therapist_id = Column(Integer, ForeignKey("therapists.id"), nullable=False, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=True, index=True)
    insurance_verification_id = Column(Integer, ForeignKey("insurance_verifications.id"), nullable=True)

    # Claim identifiers
    claim_number = Column(String(50), unique=True, index=True)  # Internal claim number
    payer_claim_number = Column(String(50), nullable=True, index=True)  # Payer's claim control number

    # Payer information
    payer_name = Column(String(200), nullable=False)
    payer_id = Column(String(100), nullable=False)  # Payer identifier
    member_id = Column(String(100), nullable=False)
    group_number = Column(String(100), nullable=True)

    # Service details
    date_of_service = Column(Date, nullable=False, index=True)
    service_from_date = Column(Date, nullable=False)
    service_to_date = Column(Date, nullable=False)

    # Billing codes
    cpt_codes = Column(JSON, nullable=False)  # List of CPT codes with modifiers
    icd10_codes = Column(JSON, nullable=False)  # List of ICD-10 diagnosis codes

    # Financial
    total_charges = Column(Float, nullable=False)
    allowed_amount = Column(Float, nullable=True)
    paid_amount = Column(Float, nullable=True, default=0.0)
    patient_responsibility = Column(Float, nullable=True)
    adjustment_amount = Column(Float, nullable=True, default=0.0)

    # Status
    status = Column(SQLEnum(ClaimStatus), nullable=False, default=ClaimStatus.DRAFT, index=True)

    # Submission
    submitted_at = Column(DateTime, nullable=True)
    submitted_by = Column(String(100), nullable=True)
    submission_method = Column(String(50), nullable=True)  # EDI, paper, portal
    submission_reference = Column(String(200), nullable=True)

    # Response
    adjudication_date = Column(Date, nullable=True)
    check_number = Column(String(100), nullable=True)
    check_date = Column(Date, nullable=True)
    eob_received = Column(Boolean, default=False)
    eob_path = Column(String(500), nullable=True)  # Path to EOB document

    # Denials
    is_denied = Column(Boolean, default=False, index=True)
    denial_reason = Column(SQLEnum(DenialReason), nullable=True)
    denial_reason_text = Column(Text, nullable=True)
    appeal_deadline = Column(Date, nullable=True)
    appeal_count = Column(Integer, default=0)

    # Notes
    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    claim_lines = relationship("ClaimLine", back_populates="claim", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="claim")
    adjustments = relationship("ClaimAdjustment", back_populates="claim")


class ClaimLine(Base):
    """Individual line item on a claim."""
    __tablename__ = "claim_lines"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)

    # Service line number
    line_number = Column(Integer, nullable=False)

    # Procedure code
    cpt_code = Column(String(10), nullable=False)
    cpt_description = Column(String(500), nullable=True)
    modifiers = Column(JSON, nullable=True)  # List of CPT modifiers

    # Units and charges
    units = Column(Integer, nullable=False, default=1)
    charge_amount = Column(Float, nullable=False)
    allowed_amount = Column(Float, nullable=True)
    paid_amount = Column(Float, nullable=True, default=0.0)

    # Dates
    service_date = Column(Date, nullable=False)

    # Status
    is_paid = Column(Boolean, default=False)
    is_denied = Column(Boolean, default=False)
    denial_reason = Column(String(500), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    claim = relationship("Claim", back_populates="claim_lines")


class ClaimAdjustment(Base):
    """Adjustments made to claims (denials, reductions, etc)."""
    __tablename__ = "claim_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)

    # Adjustment details
    adjustment_type = Column(String(50), nullable=False)  # denial, reduction, contractual, etc.
    adjustment_code = Column(String(20), nullable=True)  # CARC/RARC codes
    adjustment_amount = Column(Float, nullable=False)
    adjustment_reason = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(100), nullable=True)

    # Relationships
    claim = relationship("Claim", back_populates="adjustments")


# ========== Payments ==========

class Payment(Base):
    """Payment received from payer or patient."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)

    # Payment details
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    payment_amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False, index=True)

    # Payer information
    payer_name = Column(String(200), nullable=False)
    check_number = Column(String(100), nullable=True)
    transaction_id = Column(String(200), nullable=True)

    # Allocation
    applied_to_charges = Column(Float, nullable=False, default=0.0)
    applied_to_copay = Column(Float, nullable=False, default=0.0)
    applied_to_deductible = Column(Float, nullable=False, default=0.0)
    applied_to_coinsurance = Column(Float, nullable=False, default=0.0)

    # Processing
    is_posted = Column(Boolean, default=False)
    posted_at = Column(DateTime, nullable=True)
    posted_by = Column(String(100), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    claim = relationship("Claim", back_populates="payments")


# ========== Authorization ==========

class Authorization(Base):
    """Prior authorization for services."""
    __tablename__ = "authorizations"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    patient_intake_id = Column(Integer, ForeignKey("patient_intakes.id"), nullable=False, index=True)
    insurance_verification_id = Column(Integer, ForeignKey("insurance_verifications.id"), nullable=True)

    # Authorization details
    auth_number = Column(String(100), unique=True, nullable=False, index=True)
    payer_name = Column(String(200), nullable=False)

    # Service details
    cpt_codes = Column(JSON, nullable=False)  # List of authorized CPT codes
    icd10_codes = Column(JSON, nullable=False)  # List of diagnosis codes

    # Approval
    approved_visits = Column(Integer, nullable=False)
    used_visits = Column(Integer, default=0)
    remaining_visits = Column(Integer, nullable=False)

    # Dates
    effective_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=False, index=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Requesting provider
    requesting_provider = Column(String(200), nullable=True)
    requesting_provider_npi = Column(String(20), nullable=True)

    # Notes
    clinical_notes = Column(Text, nullable=True)
    administrative_notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ========== Billing Codes ==========

class BillingCode(Base):
    """CPT/ICD-10 code intelligence and frequency tracking."""
    __tablename__ = "billing_codes"

    id = Column(Integer, primary_key=True, index=True)

    # Code details
    code_type = Column(String(20), nullable=False, index=True)  # CPT, ICD10, HCPCS
    code = Column(String(20), nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Specialty relevance
    specialty = Column(String(100), nullable=True, index=True)  # PT, OT, SLP

    # Frequency and patterns
    usage_count = Column(Integer, default=0)
    approval_rate = Column(Float, nullable=True)  # Percentage approved by insurance
    avg_reimbursement = Column(Float, nullable=True)

    # Common pairings
    commonly_paired_with = Column(JSON, nullable=True)  # List of commonly co-billed codes

    # Modifiers
    common_modifiers = Column(JSON, nullable=True)  # List of common modifiers

    # Documentation requirements
    documentation_requirements = Column(Text, nullable=True)
    medical_necessity_criteria = Column(Text, nullable=True)

    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== Denial Management ==========

class DenialAppeal(Base):
    """Appeal for denied claims."""
    __tablename__ = "denial_appeals"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)

    # Appeal details
    appeal_number = Column(String(50), unique=True, index=True)
    appeal_level = Column(String(50), nullable=False)  # first, second, third

    # Submission
    submitted_at = Column(DateTime, nullable=False)
    submitted_by = Column(String(100), nullable=False)
    submission_method = Column(String(50), nullable=True)

    # Justification
    clinical_rationale = Column(Text, nullable=False)
    supporting_documents = Column(JSON, nullable=True)  # List of document paths

    # Outcome
    decision = Column(String(50), nullable=True)  # approved, denied, partially_approved
    decision_date = Column(Date, nullable=True)
    decision_rationale = Column(Text, nullable=True)

    # Recovery
    recovered_amount = Column(Float, nullable=True, default=0.0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========== Revenue Analytics ==========

class RevenueMetric(Base):
    """Daily/monthly revenue metrics snapshot."""
    __tablename__ = "revenue_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Time period
    metric_date = Column(Date, nullable=False, unique=True, index=True)
    metric_type = Column(String(20), nullable=False, index=True)  # daily, weekly, monthly

    # Visit metrics
    total_visits = Column(Integer, default=0)
    completed_visits = Column(Integer, default=0)
    cancelled_visits = Column(Integer, default=0)
    no_show_visits = Column(Integer, default=0)

    # Financial metrics
    total_charges = Column(Float, default=0.0)
    total_payments = Column(Float, default=0.0)
    total_adjustments = Column(Float, default=0.0)
    outstanding_ar = Column(Float, default=0.0)  # Accounts receivable

    # Claims metrics
    claims_submitted = Column(Integer, default=0)
    claims_approved = Column(Integer, default=0)
    claims_denied = Column(Integer, default=0)
    claims_pending = Column(Integer, default=0)

    # Approval rates
    first_pass_approval_rate = Column(Float, nullable=True)
    overall_approval_rate = Column(Float, nullable=True)

    # Timing metrics
    avg_days_to_payment = Column(Float, nullable=True)
    avg_days_in_ar = Column(Float, nullable=True)

    # Collection rate
    collection_rate = Column(Float, nullable=True)  # (Payments / Charges) * 100

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
