"""Scheduling and visit management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timedelta
import logging

from database.session import get_db
from database.scheduling_models import (
    PatientIntake, Therapist, Facility, Appointment,
    AppointmentReminder, TimeOffRequest, InsuranceVerification,
    AppointmentStatus, TherapistSpecialty, VisitType, InsuranceStatus
)
from core.scheduling_schemas import (
    PatientIntakeCreate, PatientIntakeResponse,
    AppointmentCreate, AppointmentUpdate, AppointmentResponse, AppointmentListResponse,
    TherapistAssignmentRequest, TherapistAssignmentResponse,
    InsuranceVerificationRequest, InsuranceVerificationResponse,
    ReminderCreate, ReminderResponse,
    CheckInRequest, CheckOutRequest,
    NoShowPredictionRequest, NoShowPredictionResponse,
    ScheduleAnalytics, TherapistProductivityMetrics,
    TherapistAvailability
)
from core.therapist_assignment import TherapistAssignmentEngine
from core.reminder_service import ReminderService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])


# ========== Patient Intake Endpoints ==========

@router.post("/intake/patient", response_model=PatientIntakeResponse)
async def submit_patient_intake(
    intake_data: PatientIntakeCreate,
    db: Session = Depends(get_db)
):
    """
    Submit patient intake form.

    Collects demographics, insurance, clinical info, and scheduling preferences.
    Triggers automatic insurance verification and therapist assignment.
    """
    try:
        # Create patient intake record
        intake = PatientIntake(
            # Demographics
            first_name=intake_data.first_name,
            last_name=intake_data.last_name,
            date_of_birth=intake_data.date_of_birth,
            phone_number=intake_data.phone_number,
            email=intake_data.email,
            address_line1=intake_data.address_line1,
            address_line2=intake_data.address_line2,
            city=intake_data.city,
            state=intake_data.state,
            zip_code=intake_data.zip_code,

            # Emergency Contact
            emergency_contact_name=intake_data.emergency_contact_name,
            emergency_contact_phone=intake_data.emergency_contact_phone,
            emergency_contact_relationship=intake_data.emergency_contact_relationship,

            # Insurance
            primary_insurance_name=intake_data.primary_insurance_name,
            primary_insurance_id=intake_data.primary_insurance_id,
            primary_insurance_group=intake_data.primary_insurance_group,
            secondary_insurance_name=intake_data.secondary_insurance_name,
            secondary_insurance_id=intake_data.secondary_insurance_id,

            # Clinical
            referring_physician=intake_data.referring_physician,
            diagnosis=intake_data.diagnosis,
            medical_history=intake_data.medical_history,
            medications=intake_data.medications,
            allergies=intake_data.allergies,

            # Preferences
            preferred_therapist_id=intake_data.preferred_therapist_id,
            preferred_day_of_week=str(intake_data.preferred_day_of_week) if intake_data.preferred_day_of_week else None,
            preferred_time_of_day=intake_data.preferred_time_of_day,
            language_preference=intake_data.language_preference,
            special_accommodations=intake_data.special_accommodations,

            # Status
            intake_status="pending",
            insurance_status=InsuranceStatus.PENDING,
            submitted_at=datetime.utcnow()
        )

        db.add(intake)
        db.commit()
        db.refresh(intake)

        logger.info(f"Patient intake submitted: {intake.id} - {intake.first_name} {intake.last_name}")

        # TODO: Trigger async tasks
        # - Insurance verification (if insurance provided)
        # - Therapist assignment recommendation
        # - Send welcome email/SMS

        return PatientIntakeResponse(
            id=intake.id,
            first_name=intake.first_name,
            last_name=intake.last_name,
            intake_status=intake.intake_status,
            insurance_status=intake.insurance_status.value,
            submitted_at=intake.submitted_at
        )

    except Exception as e:
        logger.error(f"Error submitting patient intake: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit intake: {str(e)}")


@router.get("/intake/patient/{intake_id}", response_model=PatientIntakeResponse)
async def get_patient_intake(
    intake_id: int,
    db: Session = Depends(get_db)
):
    """Get patient intake details by ID."""
    intake = db.query(PatientIntake).filter(PatientIntake.id == intake_id).first()

    if not intake:
        raise HTTPException(status_code=404, detail="Patient intake not found")

    return PatientIntakeResponse(
        id=intake.id,
        first_name=intake.first_name,
        last_name=intake.last_name,
        intake_status=intake.intake_status,
        insurance_status=intake.insurance_status.value,
        submitted_at=intake.submitted_at
    )


# ========== Appointment Endpoints ==========

@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db)
):
    """
    Create new appointment.

    Supports:
    - Manual therapist assignment or auto-assignment
    - Recurring appointments
    - Conflict detection
    - Automatic reminder scheduling
    """
    try:
        # Validate patient intake exists
        intake = db.query(PatientIntake).filter(
            PatientIntake.id == appointment_data.patient_intake_id
        ).first()

        if not intake:
            raise HTTPException(status_code=404, detail="Patient intake not found")

        # Auto-assign therapist if not provided
        therapist_id = appointment_data.therapist_id
        if not therapist_id:
            # Use intelligent therapist assignment
            assignment_engine = TherapistAssignmentEngine(db)
            therapist, confidence, reason = assignment_engine.assign_therapist(
                patient_intake=intake,
                appointment_datetime=appointment_data.scheduled_start,
                duration_minutes=appointment_data.duration_minutes,
                required_specialty=TherapistSpecialty(appointment_data.visit_type.value) if hasattr(appointment_data.visit_type, 'value') else None,
                facility_id=appointment_data.facility_id
            )

            if not therapist:
                raise HTTPException(status_code=400, detail=f"No available therapists: {reason}")

            therapist_id = therapist.id
            logger.info(f"Auto-assigned therapist {therapist_id} (confidence: {confidence}): {reason}")

        # Calculate scheduled_end
        scheduled_end = appointment_data.scheduled_start + timedelta(
            minutes=appointment_data.duration_minutes
        )

        # Check for conflicts
        conflicts = db.query(Appointment).filter(
            Appointment.therapist_id == therapist_id,
            Appointment.status.in_([
                AppointmentStatus.SCHEDULED,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.IN_PROGRESS
            ]),
            Appointment.scheduled_start < scheduled_end,
            Appointment.scheduled_end > appointment_data.scheduled_start
        ).first()

        if conflicts:
            raise HTTPException(
                status_code=409,
                detail=f"Therapist has conflicting appointment at this time"
            )

        # Create appointment
        appointment = Appointment(
            patient_intake_id=appointment_data.patient_intake_id,
            therapist_id=therapist_id,
            facility_id=appointment_data.facility_id,
            scheduled_start=appointment_data.scheduled_start,
            scheduled_end=scheduled_end,
            duration_minutes=appointment_data.duration_minutes,
            visit_type=VisitType(appointment_data.visit_type.value),
            status=AppointmentStatus.SCHEDULED,
            is_recurring=appointment_data.is_recurring,
            recurring_pattern=appointment_data.recurring_pattern,
            chief_complaint=appointment_data.chief_complaint,
            scheduling_notes=appointment_data.scheduling_notes,
            created_at=datetime.utcnow()
        )

        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        logger.info(f"Appointment created: {appointment.id} for patient {intake.first_name} {intake.last_name}")

        # Create appointment reminders
        try:
            reminder_service = ReminderService(db)
            import asyncio
            reminders = asyncio.run(reminder_service.schedule_reminders_for_appointment(appointment))
            logger.info(f"Scheduled {len(reminders)} reminders for appointment {appointment.id}")
        except Exception as e:
            logger.error(f"Failed to schedule reminders: {str(e)}")
            # Don't fail the appointment creation if reminder scheduling fails

        # TODO: Trigger async tasks
        # - Send confirmation email/SMS
        # - If recurring, create future appointments

        return AppointmentResponse(
            id=appointment.id,
            patient_intake_id=appointment.patient_intake_id,
            therapist_id=appointment.therapist_id,
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            duration_minutes=appointment.duration_minutes,
            visit_type=appointment.visit_type.value,
            status=appointment.status.value,
            is_recurring=appointment.is_recurring,
            created_at=appointment.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating appointment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create appointment: {str(e)}")


@router.get("/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    therapist_id: Optional[int] = Query(None),
    patient_intake_id: Optional[int] = Query(None),
    facility_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List appointments with filters.

    Filters:
    - therapist_id: Filter by therapist
    - patient_intake_id: Filter by patient
    - facility_id: Filter by facility
    - status: Filter by status (scheduled, completed, etc.)
    - start_date/end_date: Filter by date range
    - page/page_size: Pagination
    """
    query = db.query(Appointment)

    # Apply filters
    if therapist_id:
        query = query.filter(Appointment.therapist_id == therapist_id)

    if patient_intake_id:
        query = query.filter(Appointment.patient_intake_id == patient_intake_id)

    if facility_id:
        query = query.filter(Appointment.facility_id == facility_id)

    if status:
        try:
            status_enum = AppointmentStatus(status)
            query = query.filter(Appointment.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if start_date:
        query = query.filter(Appointment.scheduled_start >= datetime.combine(start_date, datetime.min.time()))

    if end_date:
        query = query.filter(Appointment.scheduled_start <= datetime.combine(end_date, datetime.max.time()))

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    appointments = query.order_by(Appointment.scheduled_start.desc()).offset(offset).limit(page_size).all()

    # Convert to response models
    appointment_responses = [
        AppointmentResponse(
            id=apt.id,
            patient_intake_id=apt.patient_intake_id,
            therapist_id=apt.therapist_id,
            scheduled_start=apt.scheduled_start,
            scheduled_end=apt.scheduled_end,
            duration_minutes=apt.duration_minutes,
            visit_type=apt.visit_type.value,
            status=apt.status.value,
            is_recurring=apt.is_recurring,
            created_at=apt.created_at
        )
        for apt in appointments
    ]

    return AppointmentListResponse(
        appointments=appointment_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.put("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    update_data: AppointmentUpdate,
    db: Session = Depends(get_db)
):
    """
    Update appointment.

    Supports:
    - Rescheduling (update scheduled_start/scheduled_end)
    - Status changes (checked_in, completed, cancelled)
    - Adding notes
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    try:
        # Update fields
        if update_data.scheduled_start:
            appointment.scheduled_start = update_data.scheduled_start

        if update_data.scheduled_end:
            appointment.scheduled_end = update_data.scheduled_end

        if update_data.status:
            appointment.status = AppointmentStatus(update_data.status.value)

        if update_data.actual_start:
            appointment.actual_start = update_data.actual_start

        if update_data.actual_end:
            appointment.actual_end = update_data.actual_end

        if update_data.check_in_time:
            appointment.check_in_time = update_data.check_in_time

        if update_data.check_out_time:
            appointment.check_out_time = update_data.check_out_time

        if update_data.cancellation_reason:
            appointment.cancellation_reason = update_data.cancellation_reason
            appointment.cancelled_at = datetime.utcnow()

        if update_data.scheduling_notes:
            appointment.scheduling_notes = update_data.scheduling_notes

        appointment.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(appointment)

        logger.info(f"Appointment updated: {appointment.id}")

        return AppointmentResponse(
            id=appointment.id,
            patient_intake_id=appointment.patient_intake_id,
            therapist_id=appointment.therapist_id,
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            duration_minutes=appointment.duration_minutes,
            visit_type=appointment.visit_type.value,
            status=appointment.status.value,
            is_recurring=appointment.is_recurring,
            created_at=appointment.created_at
        )

    except Exception as e:
        logger.error(f"Error updating appointment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update appointment: {str(e)}")


# ========== Therapist Assignment Endpoints ==========

@router.post("/therapist-assignment", response_model=TherapistAssignmentResponse)
async def assign_therapist(
    assignment_request: TherapistAssignmentRequest,
    db: Session = Depends(get_db)
):
    """
    Intelligent therapist assignment.

    Considers:
    - Specialty matching
    - Availability at requested time
    - Current caseload
    - Patient preferences
    - Geographic proximity (for mobile therapy)
    - Language requirements

    Returns best match with confidence score and reasoning.
    """
    try:
        # Get patient intake for preferences
        intake = db.query(PatientIntake).filter(
            PatientIntake.id == assignment_request.patient_intake_id
        ).first()

        if not intake:
            raise HTTPException(status_code=404, detail="Patient intake not found")

        # Use intelligent therapist assignment engine
        assignment_engine = TherapistAssignmentEngine(db)
        therapist, confidence, reason = assignment_engine.assign_therapist(
            patient_intake=intake,
            appointment_datetime=assignment_request.appointment_datetime,
            duration_minutes=assignment_request.duration_minutes,
            required_specialty=TherapistSpecialty(assignment_request.required_specialty.value) if assignment_request.required_specialty else None,
            facility_id=assignment_request.facility_id
        )

        if not therapist:
            raise HTTPException(status_code=404, detail=f"No available therapists: {reason}")

        logger.info(
            f"Therapist assigned: {therapist.id} ({therapist.first_name} "
            f"{therapist.last_name}) - Confidence: {confidence}"
        )

        return TherapistAssignmentResponse(
            therapist_id=therapist.id,
            therapist_name=f"{therapist.first_name} {therapist.last_name}",
            specialty=therapist.specialty.value,
            confidence_score=confidence,
            reason=reason,
            available_slot=assignment_request.appointment_datetime
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning therapist: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to assign therapist: {str(e)}")


# ========== Insurance Verification Endpoints ==========

@router.post("/insurance-verification", response_model=InsuranceVerificationResponse)
async def verify_insurance(
    verification_request: InsuranceVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Verify insurance eligibility.

    In production, this would:
    - Call insurance API (Change Healthcare, Availity, etc.)
    - Parse eligibility response
    - Extract copay, deductible, authorization requirements

    For now, returns mock verification.
    """
    try:
        # Validate patient intake exists
        intake = db.query(PatientIntake).filter(
            PatientIntake.id == verification_request.patient_intake_id
        ).first()

        if not intake:
            raise HTTPException(status_code=404, detail="Patient intake not found")

        # TODO: Call real insurance verification API
        # For now, create mock verification

        verification = InsuranceVerification(
            patient_intake_id=verification_request.patient_intake_id,
            payer_name=verification_request.payer_name,
            member_id=verification_request.member_id,
            group_number=verification_request.group_number,
            verification_status=InsuranceStatus.VERIFIED,
            verified_at=datetime.utcnow(),
            verified_by="system",
            is_active=True,
            effective_date=datetime.utcnow() - timedelta(days=30),
            termination_date=datetime.utcnow() + timedelta(days=365),
            copay_amount=25.00,
            deductible_amount=1500.00,
            deductible_met=450.00,
            requires_authorization=False,
            visits_authorized=20,
            visits_used=0,
            raw_response={"mock": True}
        )

        db.add(verification)

        # Update intake insurance status
        intake.insurance_status = InsuranceStatus.VERIFIED

        db.commit()
        db.refresh(verification)

        logger.info(f"Insurance verified: {verification.id} for patient intake {intake.id}")

        return InsuranceVerificationResponse(
            verification_id=verification.id,
            verification_status=verification.verification_status.value,
            is_active=verification.is_active,
            effective_date=verification.effective_date.date() if verification.effective_date else None,
            termination_date=verification.termination_date.date() if verification.termination_date else None,
            copay_amount=verification.copay_amount,
            deductible_amount=verification.deductible_amount,
            deductible_met=verification.deductible_met,
            requires_authorization=verification.requires_authorization,
            visits_authorized=verification.visits_authorized,
            verified_at=verification.verified_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying insurance: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to verify insurance: {str(e)}")


# ========== Reminder Endpoints ==========

@router.post("/reminders", response_model=ReminderResponse)
async def create_reminder(
    reminder_data: ReminderCreate,
    db: Session = Depends(get_db)
):
    """
    Create appointment reminder.

    Supports SMS, email, and push notifications.
    Typically created automatically when appointment is scheduled.
    """
    try:
        # Validate appointment exists
        appointment = db.query(Appointment).filter(
            Appointment.id == reminder_data.appointment_id
        ).first()

        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        # Calculate reminder time
        reminder_time = appointment.scheduled_start - timedelta(hours=reminder_data.hours_before)

        # Create reminder
        reminder = AppointmentReminder(
            appointment_id=reminder_data.appointment_id,
            reminder_type=reminder_data.reminder_type,
            reminder_time=reminder_time,
            hours_before=reminder_data.hours_before,
            message_template=reminder_data.message_template or "default_reminder",
            created_at=datetime.utcnow()
        )

        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        logger.info(f"Reminder created: {reminder.id} for appointment {appointment.id}")

        return ReminderResponse(
            id=reminder.id,
            appointment_id=reminder.appointment_id,
            reminder_type=reminder.reminder_type,
            reminder_time=reminder.reminder_time,
            hours_before=reminder.hours_before,
            sent_at=reminder.sent_at,
            delivery_status=reminder.delivery_status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating reminder: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create reminder: {str(e)}")


# ========== Check-In/Check-Out Endpoints ==========

@router.post("/check-in")
async def check_in_patient(
    check_in_data: CheckInRequest,
    db: Session = Depends(get_db)
):
    """
    Patient check-in.

    Updates appointment status to CHECKED_IN.
    Records check-in time and copay collection.
    """
    try:
        appointment = db.query(Appointment).filter(
            Appointment.id == check_in_data.appointment_id
        ).first()

        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        # Update appointment
        appointment.status = AppointmentStatus.CHECKED_IN
        appointment.check_in_time = check_in_data.check_in_time or datetime.utcnow()
        appointment.copay_collected = check_in_data.copay_collected

        if check_in_data.copay_amount:
            appointment.copay_amount = check_in_data.copay_amount

        if check_in_data.notes:
            appointment.scheduling_notes = check_in_data.notes

        appointment.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"Patient checked in: Appointment {appointment.id}")

        return {
            "success": True,
            "appointment_id": appointment.id,
            "check_in_time": appointment.check_in_time,
            "message": "Patient checked in successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking in patient: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to check in: {str(e)}")


@router.post("/check-out")
async def check_out_patient(
    check_out_data: CheckOutRequest,
    db: Session = Depends(get_db)
):
    """
    Patient check-out.

    Updates appointment status to COMPLETED.
    Records check-out time.
    Links to session notes if available.
    """
    try:
        appointment = db.query(Appointment).filter(
            Appointment.id == check_out_data.appointment_id
        ).first()

        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        # Update appointment
        appointment.status = AppointmentStatus.COMPLETED
        appointment.check_out_time = check_out_data.check_out_time or datetime.utcnow()

        if check_out_data.session_notes_id:
            appointment.session_notes_id = check_out_data.session_notes_id

        if not appointment.actual_end:
            appointment.actual_end = appointment.check_out_time

        appointment.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"Patient checked out: Appointment {appointment.id}")

        return {
            "success": True,
            "appointment_id": appointment.id,
            "check_out_time": appointment.check_out_time,
            "next_appointment_scheduled": check_out_data.next_appointment_scheduled,
            "message": "Patient checked out successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking out patient: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to check out: {str(e)}")


# ========== No-Show Prediction Endpoints ==========

@router.post("/no-show-prediction", response_model=NoShowPredictionResponse)
async def predict_no_show(
    prediction_request: NoShowPredictionRequest,
    db: Session = Depends(get_db)
):
    """
    Predict no-show risk for appointment.

    In production, this would use ML model considering:
    - Patient's historical no-show rate
    - Time of day (early morning = higher risk)
    - Day of week
    - Weather forecast
    - Reminder confirmation status
    - Distance from clinic

    For now, returns rule-based prediction.
    """
    try:
        appointment = db.query(Appointment).filter(
            Appointment.id == prediction_request.appointment_id
        ).first()

        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        # Get patient history
        patient_appointments = db.query(Appointment).filter(
            Appointment.patient_intake_id == appointment.patient_intake_id,
            Appointment.id != appointment.id
        ).all()

        # Calculate historical no-show rate
        total_past = len(patient_appointments)
        no_shows = sum(1 for apt in patient_appointments if apt.status == AppointmentStatus.NO_SHOW)
        no_show_rate = (no_shows / total_past * 100) if total_past > 0 else 0

        # Rule-based scoring
        risk_score = 0
        risk_factors = []
        recommendations = []

        # Factor 1: Historical no-shows
        if no_shows >= 2:
            risk_score += 30
            risk_factors.append(f"Patient has {no_shows} previous no-shows")
            recommendations.append("Call patient to confirm")

        # Factor 2: Time of day
        hour = appointment.scheduled_start.hour
        if hour < 9:
            risk_score += 20
            risk_factors.append(f"Appointment is early morning ({hour} AM)")
            recommendations.append("Send additional reminder morning of appointment")
        elif hour >= 17:
            risk_score += 15
            risk_factors.append(f"Appointment is late evening ({hour}:00)")

        # Factor 3: Reminder confirmation
        if not appointment.confirmation_received:
            risk_score += 25
            risk_factors.append("No reminder confirmation received")
            recommendations.append("Send additional reminder 2 hours before")

        # Factor 4: New patient
        if total_past == 0:
            risk_score += 15
            risk_factors.append("First appointment (new patient)")
            recommendations.append("Send welcome message with clear directions")

        # Determine risk level
        if risk_score >= 60:
            risk_level = "high"
            recommendations.append("Consider overbooking this slot")
        elif risk_score >= 30:
            risk_level = "medium"
            recommendations.append("Monitor confirmation status closely")
        else:
            risk_level = "low"

        if not risk_factors:
            risk_factors.append("No significant risk factors identified")

        if not recommendations:
            recommendations.append("Standard reminder protocol sufficient")

        logger.info(f"No-show prediction: Appointment {appointment.id} - Risk: {risk_level} ({risk_score}%)")

        return NoShowPredictionResponse(
            appointment_id=appointment.id,
            risk_score=min(risk_score, 100),
            risk_level=risk_level,
            risk_factors=risk_factors,
            recommendations=recommendations
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting no-show: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to predict no-show: {str(e)}")


# ========== Analytics Endpoints ==========

@router.get("/analytics/schedule", response_model=ScheduleAnalytics)
async def get_schedule_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    therapist_id: Optional[int] = Query(None),
    facility_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Schedule analytics and metrics.

    Returns:
    - Total appointments
    - Completion/cancellation/no-show rates
    - Fill rate
    - Average duration
    - Top visit types
    - Busiest time slots
    """
    try:
        # Default to last 30 days if no dates provided
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).date()
        if not end_date:
            end_date = datetime.utcnow().date()

        query = db.query(Appointment).filter(
            Appointment.scheduled_start >= datetime.combine(start_date, datetime.min.time()),
            Appointment.scheduled_start <= datetime.combine(end_date, datetime.max.time())
        )

        if therapist_id:
            query = query.filter(Appointment.therapist_id == therapist_id)

        if facility_id:
            query = query.filter(Appointment.facility_id == facility_id)

        appointments = query.all()

        total = len(appointments)
        scheduled = sum(1 for apt in appointments if apt.status == AppointmentStatus.SCHEDULED)
        completed = sum(1 for apt in appointments if apt.status == AppointmentStatus.COMPLETED)
        cancelled = sum(1 for apt in appointments if apt.status == AppointmentStatus.CANCELLED)
        no_shows = sum(1 for apt in appointments if apt.status == AppointmentStatus.NO_SHOW)

        # Calculate fill rate (completed / total possible)
        fill_rate = (completed / total * 100) if total > 0 else 0

        # Average duration
        durations = [apt.duration_minutes for apt in appointments if apt.duration_minutes]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Top visit types
        visit_types = {}
        for apt in appointments:
            vt = apt.visit_type.value
            visit_types[vt] = visit_types.get(vt, 0) + 1

        # Busiest time slots (group by hour)
        time_slots = {}
        for apt in appointments:
            hour = apt.scheduled_start.hour
            time_slot = f"{hour:02d}:00"
            time_slots[time_slot] = time_slots.get(time_slot, 0) + 1

        busiest_slots = [
            {"time_slot": slot, "count": count}
            for slot, count in sorted(time_slots.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return ScheduleAnalytics(
            total_appointments=total,
            scheduled=scheduled,
            completed=completed,
            cancelled=cancelled,
            no_shows=no_shows,
            fill_rate=round(fill_rate, 2),
            average_duration_minutes=round(avg_duration, 2),
            top_visit_types=visit_types,
            busiest_time_slots=busiest_slots
        )

    except Exception as e:
        logger.error(f"Error getting schedule analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")


@router.get("/analytics/therapist/{therapist_id}", response_model=TherapistProductivityMetrics)
async def get_therapist_metrics(
    therapist_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Therapist productivity metrics.

    Returns:
    - Total appointments
    - Completion rate
    - Cancellation/no-show counts
    - Average session duration
    - Total billable minutes
    - Utilization rate
    - Documentation completion rate
    """
    try:
        therapist = db.query(Therapist).filter(Therapist.id == therapist_id).first()

        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")

        # Default to last 30 days
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).date()
        if not end_date:
            end_date = datetime.utcnow().date()

        appointments = db.query(Appointment).filter(
            Appointment.therapist_id == therapist_id,
            Appointment.scheduled_start >= datetime.combine(start_date, datetime.min.time()),
            Appointment.scheduled_start <= datetime.combine(end_date, datetime.max.time())
        ).all()

        total = len(appointments)
        completed = sum(1 for apt in appointments if apt.status == AppointmentStatus.COMPLETED)
        cancelled = sum(1 for apt in appointments if apt.status == AppointmentStatus.CANCELLED)
        no_shows = sum(1 for apt in appointments if apt.status == AppointmentStatus.NO_SHOW)

        # Average session duration (actual, not scheduled)
        actual_durations = []
        for apt in appointments:
            if apt.actual_start and apt.actual_end:
                duration = (apt.actual_end - apt.actual_start).total_seconds() / 60
                actual_durations.append(duration)

        avg_duration = sum(actual_durations) / len(actual_durations) if actual_durations else 0

        # Total billable minutes
        billable_minutes = sum(apt.duration_minutes for apt in appointments if apt.status == AppointmentStatus.COMPLETED)

        # Utilization rate (billable / available)
        # Assume 8-hour workday = 480 minutes per day
        num_days = (end_date - start_date).days + 1
        available_minutes = num_days * 480
        utilization_rate = (billable_minutes / available_minutes * 100) if available_minutes > 0 else 0

        # Documentation completion rate
        completed_with_notes = sum(
            1 for apt in appointments
            if apt.status == AppointmentStatus.COMPLETED and apt.session_notes_id
        )
        doc_completion_rate = (completed_with_notes / completed * 100) if completed > 0 else 0

        return TherapistProductivityMetrics(
            therapist_id=therapist.id,
            therapist_name=f"{therapist.first_name} {therapist.last_name}",
            total_appointments=total,
            completed_appointments=completed,
            cancelled_appointments=cancelled,
            no_shows=no_shows,
            average_session_duration=round(avg_duration, 2),
            total_billable_minutes=billable_minutes,
            utilization_rate=round(utilization_rate, 2),
            patient_satisfaction=therapist.average_rating,
            documentation_completion_rate=round(doc_completion_rate, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting therapist metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")
