"""Intake API endpoint for receiving raw clinical notes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from core.schema import NoteIntakeRequest, NoteIntakeResponse, TaskStatusResponse, SOAPComponents
from core.parser import soap_parser
from database.session import get_db
from database.models import Patient, NoteDraft, TaskLog, TaskStatus, NoteSource
from backend.utils.audit import logger as audit_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["intake"])


@router.post("/intake", response_model=NoteIntakeResponse, status_code=status.HTTP_201_CREATED)
async def submit_note(
    request: NoteIntakeRequest,
    db: Session = Depends(get_db)
) -> NoteIntakeResponse:
    """
    Submit a raw clinical note for AI processing and EMR drafting.

    This endpoint:
    1. Validates the input
    2. Creates or retrieves patient record
    3. Stores the raw note
    4. Triggers LLM structuring (synchronously for now)
    5. Returns a task ID for tracking

    Args:
        request: NoteIntakeRequest with patient info and raw note
        db: Database session

    Returns:
        NoteIntakeResponse with task ID and status
    """
    try:
        # Audit log the intake
        audit_logger.log_info(
            event="note_intake_received",
            user_id=request.submitted_by,
            patient_id=request.patient_id,
            metadata={
                "visit_type": request.visit_type,
                "visit_date": request.visit_date.isoformat(),
                "source": request.source
            }
        )

        # Step 1: Get or create patient
        patient = db.query(Patient).filter(Patient.patient_id == request.patient_id).first()

        if not patient:
            # Create new patient if not exists
            patient = Patient(
                patient_id=request.patient_id,
                first_name=request.patient_first_name or "Unknown",
                last_name=request.patient_last_name or "Unknown",
                date_of_birth=request.patient_dob,
                emr_patient_id=request.emr_patient_id
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)
            logger.info(f"Created new patient: {request.patient_id}")

        # Step 2: Create note draft record
        note_draft = NoteDraft(
            patient_id=patient.id,
            raw_input=request.raw_input,
            source=NoteSource(request.source.value),
            submitted_by=request.submitted_by,
            visit_date=request.visit_date,
            visit_type=request.visit_type.value,
            status=TaskStatus.PENDING
        )
        db.add(note_draft)
        db.commit()
        db.refresh(note_draft)

        # Step 3: Create initial task log
        task_log = TaskLog(
            note_draft_id=note_draft.id,
            task_name="note_intake",
            status=TaskStatus.PENDING,
            input_data={
                "raw_input": request.raw_input,
                "visit_type": request.visit_type.value
            }
        )
        db.add(task_log)
        db.commit()

        logger.info(f"Created note draft {note_draft.id} for patient {request.patient_id}")

        # Step 4: Trigger LLM processing (synchronous for MVP)
        # In production, this would be async via Celery
        try:
            # Update status to processing
            note_draft.status = TaskStatus.PROCESSING
            task_log.status = TaskStatus.PROCESSING
            task_log.started_at = datetime.utcnow()
            db.commit()

            # Call LLM parser
            logger.info(f"Starting LLM parsing for note draft {note_draft.id}")
            soap_components = await soap_parser.parse_to_soap(
                raw_text=request.raw_input,
                visit_type=request.visit_type.value,
                patient_context=None  # TODO: Add patient history context
            )

            # Update note draft with SOAP components
            note_draft.subjective = soap_components.subjective
            note_draft.objective = soap_components.objective
            note_draft.assessment = soap_components.assessment
            note_draft.plan = soap_components.plan
            note_draft.confidence_score = soap_components.confidence_score
            note_draft.soap_json = soap_components.model_dump()
            note_draft.status = TaskStatus.LLM_COMPLETE

            # Update task log
            task_log.status = TaskStatus.LLM_COMPLETE
            task_log.completed_at = datetime.utcnow()
            task_log.duration_seconds = int(
                (task_log.completed_at - task_log.started_at).total_seconds()
            )
            task_log.output_data = soap_components.model_dump()

            db.commit()

            logger.info(
                f"LLM parsing complete for note draft {note_draft.id}. "
                f"Confidence: {soap_components.confidence_score}"
            )

            # Audit log success
            audit_logger.log_info(
                event="llm_parsing_complete",
                user_id=request.submitted_by,
                patient_id=request.patient_id,
                metadata={
                    "note_draft_id": note_draft.id,
                    "confidence_score": soap_components.confidence_score,
                    "duration_seconds": task_log.duration_seconds
                }
            )

        except Exception as llm_error:
            # Handle LLM processing errors
            logger.error(f"LLM parsing failed for note draft {note_draft.id}: {llm_error}")

            note_draft.status = TaskStatus.FAILED
            note_draft.error_message = str(llm_error)

            task_log.status = TaskStatus.FAILED
            task_log.error_details = str(llm_error)
            task_log.completed_at = datetime.utcnow()

            db.commit()

            # Audit log failure
            audit_logger.log_error(
                event="llm_parsing_failed",
                user_id=request.submitted_by,
                patient_id=request.patient_id,
                metadata={
                    "note_draft_id": note_draft.id,
                    "error": str(llm_error)
                }
            )

            # Don't raise error - still return task ID so user can check status
            logger.warning(f"Returning task ID {note_draft.id} despite LLM failure")

        # Step 5: Return response
        return NoteIntakeResponse(
            task_id=note_draft.id,
            status=note_draft.status,
            message=_get_status_message(note_draft.status),
            created_at=note_draft.created_at
        )

    except Exception as e:
        logger.error(f"Error in note intake: {e}", exc_info=True)
        audit_logger.log_error(
            event="note_intake_error",
            user_id=request.submitted_by if request else "unknown",
            metadata={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process note intake: {str(e)}"
        )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: int,
    db: Session = Depends(get_db)
) -> TaskStatusResponse:
    """
    Check the status of a note processing task.

    Args:
        task_id: Note draft ID
        db: Database session

    Returns:
        TaskStatusResponse with current status and SOAP components if complete
    """
    note_draft = db.query(NoteDraft).filter(NoteDraft.id == task_id).first()

    if not note_draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )

    # Build SOAP components if available
    soap_components = None
    if note_draft.status in [TaskStatus.LLM_COMPLETE, TaskStatus.COMPLETED]:
        soap_components = SOAPComponents(
            subjective=note_draft.subjective or "",
            objective=note_draft.objective or "",
            assessment=note_draft.assessment or "",
            plan=note_draft.plan or "",
            confidence_score=note_draft.confidence_score
        )

    return TaskStatusResponse(
        task_id=note_draft.id,
        status=note_draft.status,
        patient_id=note_draft.patient.patient_id,
        visit_date=note_draft.visit_date,
        created_at=note_draft.created_at,
        updated_at=note_draft.updated_at,
        soap_components=soap_components,
        emr_draft_url=note_draft.emr_draft_url,
        emr_draft_id=note_draft.emr_draft_id,
        error_message=note_draft.error_message
    )


def _get_status_message(status: TaskStatus) -> str:
    """Get human-readable message for task status."""
    messages = {
        TaskStatus.PENDING: "Note received and queued for processing.",
        TaskStatus.PROCESSING: "AI is currently structuring your note.",
        TaskStatus.LLM_COMPLETE: "Note structured successfully. Ready for EMR entry.",
        TaskStatus.BROWSER_RUNNING: "Automated EMR entry in progress.",
        TaskStatus.COMPLETED: "Draft successfully created in EMR.",
        TaskStatus.FAILED: "Processing failed. Please check error details.",
        TaskStatus.REQUIRES_REVIEW: "Draft complete but requires clinician review."
    }
    return messages.get(status, "Unknown status")
