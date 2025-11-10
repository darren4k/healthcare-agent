"""Feedback collection API for clinician corrections."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging

from database.session import get_db
from database.models import NoteDraft, TaskLog, TaskStatus
from backend.utils.audit import logger as audit_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["feedback"])


# =============================
# Schemas
# =============================

class SOAPFeedback(BaseModel):
    """Edited SOAP components from clinician."""
    subjective: str
    objective: str
    assessment: str
    plan: str


class FeedbackRequest(BaseModel):
    """Request schema for submitting feedback."""
    task_id: int = Field(..., description="Note draft task ID")
    clinician_id: str = Field(..., min_length=1, max_length=100)
    edited_soap: SOAPFeedback
    feedback_notes: Optional[str] = None
    satisfaction_score: Optional[int] = Field(None, ge=1, le=5)


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    success: bool
    message: str
    task_id: int
    feedback_recorded: bool


# =============================
# Endpoints
# =============================

@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db)
) -> FeedbackResponse:
    """
    Submit clinician feedback on AI-generated SOAP note.

    This endpoint:
    1. Records clinician edits to original SOAP components
    2. Calculates edit distance/metrics
    3. Stores feedback for future learning
    4. Updates note draft status

    Args:
        request: FeedbackRequest with edited SOAP and feedback
        db: Database session

    Returns:
        FeedbackResponse with confirmation
    """
    try:
        # Fetch the note draft
        note_draft = db.query(NoteDraft).filter(NoteDraft.id == request.task_id).first()

        if not note_draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {request.task_id} not found"
            )

        # Store original SOAP for comparison
        original_soap = {
            "subjective": note_draft.subjective,
            "objective": note_draft.objective,
            "assessment": note_draft.assessment,
            "plan": note_draft.plan
        }

        # Calculate edit metrics
        edit_metrics = calculate_edit_metrics(original_soap, request.edited_soap.model_dump())

        # Update note draft with edited version
        note_draft.subjective = request.edited_soap.subjective
        note_draft.objective = request.edited_soap.objective
        note_draft.assessment = request.edited_soap.assessment
        note_draft.plan = request.edited_soap.plan
        note_draft.reviewed_by = request.clinician_id
        note_draft.reviewed_at = datetime.utcnow()
        note_draft.status = TaskStatus.COMPLETED

        # Update SOAP JSON
        note_draft.soap_json = {
            **note_draft.soap_json,
            **request.edited_soap.model_dump(),
            "edited": True,
            "original_soap": original_soap,
            "edit_metrics": edit_metrics,
            "feedback_notes": request.feedback_notes,
            "satisfaction_score": request.satisfaction_score
        }

        # Create feedback task log
        feedback_log = TaskLog(
            note_draft_id=note_draft.id,
            task_name="clinician_feedback",
            status=TaskStatus.COMPLETED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            input_data={
                "clinician_id": request.clinician_id,
                "original_soap": original_soap,
                "feedback_notes": request.feedback_notes,
                "satisfaction_score": request.satisfaction_score
            },
            output_data={
                "edited_soap": request.edited_soap.model_dump(),
                "edit_metrics": edit_metrics
            }
        )

        db.add(feedback_log)
        db.commit()
        db.refresh(note_draft)

        # Audit log
        audit_logger.log_info(
            event="feedback_submitted",
            user_id=request.clinician_id,
            patient_id=note_draft.patient.patient_id,
            metadata={
                "task_id": request.task_id,
                "edit_metrics": edit_metrics,
                "satisfaction_score": request.satisfaction_score
            }
        )

        logger.info(f"Feedback submitted for task {request.task_id} by {request.clinician_id}")

        return FeedbackResponse(
            success=True,
            message="Feedback recorded successfully. Thank you for improving our AI!",
            task_id=request.task_id,
            feedback_recorded=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        audit_logger.log_error(
            event="feedback_submission_error",
            user_id=request.clinician_id,
            metadata={"task_id": request.task_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


# =============================
# Helper Functions
# =============================

def calculate_edit_metrics(original: dict, edited: dict) -> dict:
    """
    Calculate edit distance metrics between original and edited SOAP.

    Args:
        original: Original SOAP components
        edited: Edited SOAP components

    Returns:
        dict with edit metrics
    """
    from difflib import SequenceMatcher

    metrics = {}

    for section in ["subjective", "objective", "assessment", "plan"]:
        orig_text = original.get(section, "")
        edit_text = edited.get(section, "")

        # Calculate similarity ratio
        similarity = SequenceMatcher(None, orig_text, edit_text).ratio()

        # Character diff
        char_diff = abs(len(edit_text) - len(orig_text))

        # Word diff
        orig_words = len(orig_text.split())
        edit_words = len(edit_text.split())
        word_diff = abs(edit_words - orig_words)

        metrics[section] = {
            "similarity": round(similarity * 100, 2),  # Percentage
            "char_diff": char_diff,
            "word_diff": word_diff,
            "edited": orig_text != edit_text
        }

    # Overall metrics
    total_similarity = sum(m["similarity"] for m in metrics.values()) / len(metrics)
    sections_edited = sum(1 for m in metrics.values() if m["edited"])

    metrics["overall"] = {
        "average_similarity": round(total_similarity, 2),
        "sections_edited": sections_edited,
        "edit_rate": round((sections_edited / len(metrics)) * 100, 2)
    }

    return metrics
