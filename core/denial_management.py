"""Denial management and appeals automation."""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.revenue_models import (
    Claim, ClaimStatus, DenialReason, DenialAppeal
)

logger = logging.getLogger(__name__)


class DenialManagementEngine:
    """
    Automated denial detection, analysis, and appeal generation.

    Features:
    - Denial detection from EDI 835/ERA
    - Root cause analysis
    - Auto-generate appeal letters
    - Track appeal success rates
    - Identify prevention opportunities
    """

    def __init__(self, db: Session):
        self.db = db

    def detect_denials(self) -> List[Claim]:
        """
        Detect newly denied claims.

        Returns:
            List of denied claims
        """
        denied_claims = self.db.query(Claim).filter(
            and_(
                Claim.status == ClaimStatus.DENIED,
                Claim.is_denied == True,
                Claim.appeal_count == 0  # Not yet appealed
            )
        ).all()

        logger.info(f"Found {len(denied_claims)} newly denied claims")

        return denied_claims

    def analyze_denial(self, claim: Claim) -> Dict:
        """
        Analyze denial reason and determine if appealable.

        Args:
            claim: Denied claim

        Returns:
            Dict with analysis results
        """
        analysis = {
            "claim_id": claim.id,
            "claim_number": claim.claim_number,
            "denial_reason": claim.denial_reason.value if claim.denial_reason else "unknown",
            "denial_text": claim.denial_reason_text,
            "is_appealable": False,
            "appeal_likelihood": 0.0,
            "recommended_action": "",
            "required_documents": [],
            "appeal_strategy": ""
        }

        # Analyze based on denial reason
        if claim.denial_reason == DenialReason.MISSING_INFO:
            analysis["is_appealable"] = True
            analysis["appeal_likelihood"] = 0.85
            analysis["recommended_action"] = "Submit corrected claim with missing information"
            analysis["required_documents"] = ["Complete documentation", "Clinical notes"]
            analysis["appeal_strategy"] = "resubmit_corrected"

        elif claim.denial_reason == DenialReason.INVALID_CODING:
            analysis["is_appealable"] = True
            analysis["appeal_likelihood"] = 0.75
            analysis["recommended_action"] = "Review and correct CPT/ICD-10 codes"
            analysis["required_documents"] = ["Coding justification", "Clinical documentation"]
            analysis["appeal_strategy"] = "resubmit_corrected"

        elif claim.denial_reason == DenialReason.MEDICAL_NECESSITY:
            analysis["is_appealable"] = True
            analysis["appeal_likelihood"] = 0.60
            analysis["recommended_action"] = "Provide medical necessity documentation"
            analysis["required_documents"] = [
                "Physician referral",
                "Clinical evaluation",
                "Treatment plan",
                "Progress notes",
                "Research evidence supporting treatment"
            ]
            analysis["appeal_strategy"] = "formal_appeal"

        elif claim.denial_reason == DenialReason.NOT_COVERED:
            analysis["is_appealable"] = False
            analysis["appeal_likelihood"] = 0.20
            analysis["recommended_action"] = "Bill patient or write off"
            analysis["appeal_strategy"] = "patient_responsibility"

        elif claim.denial_reason == DenialReason.AUTH_REQUIRED:
            analysis["is_appealable"] = True
            analysis["appeal_likelihood"] = 0.50
            analysis["recommended_action"] = "Obtain retroactive authorization"
            analysis["required_documents"] = ["Authorization request form", "Clinical justification"]
            analysis["appeal_strategy"] = "authorization_request"

        elif claim.denial_reason == DenialReason.DUPLICATE_CLAIM:
            analysis["is_appealable"] = True
            analysis["appeal_likelihood"] = 0.90
            analysis["recommended_action"] = "Prove claim is not duplicate"
            analysis["required_documents"] = ["Service documentation", "Date of service proof"]
            analysis["appeal_strategy"] = "documentation_proof"

        elif claim.denial_reason == DenialReason.TIMELY_FILING:
            analysis["is_appealable"] = False
            analysis["appeal_likelihood"] = 0.15
            analysis["recommended_action"] = "Write off - missed filing deadline"
            analysis["appeal_strategy"] = "write_off"

        elif claim.denial_reason == DenialReason.CREDENTIALING:
            analysis["is_appealable"] = True
            analysis["appeal_likelihood"] = 0.70
            analysis["recommended_action"] = "Verify provider credentialing status"
            analysis["required_documents"] = ["Credentialing verification", "Enrollment confirmation"]
            analysis["appeal_strategy"] = "credentialing_verification"

        else:
            analysis["is_appealable"] = True
            analysis["appeal_likelihood"] = 0.40
            analysis["recommended_action"] = "Review denial details and documentation"
            analysis["required_documents"] = ["All clinical documentation"]
            analysis["appeal_strategy"] = "manual_review"

        # Calculate appeal deadline (typically 180 days from denial)
        if claim.adjudication_date:
            appeal_deadline = claim.adjudication_date + timedelta(days=180)
            analysis["appeal_deadline"] = appeal_deadline
            analysis["days_until_deadline"] = (appeal_deadline - date.today()).days
        else:
            analysis["appeal_deadline"] = date.today() + timedelta(days=180)
            analysis["days_until_deadline"] = 180

        return analysis

    async def generate_appeal_letter(
        self,
        claim: Claim,
        analysis: Dict
    ) -> str:
        """
        Auto-generate appeal letter using AI.

        Args:
            claim: Denied claim
            analysis: Denial analysis results

        Returns:
            Appeal letter text
        """
        # Get patient and provider information
        from database.scheduling_models import PatientIntake, Therapist

        intake = self.db.query(PatientIntake).filter(
            PatientIntake.id == claim.patient_intake_id
        ).first()

        therapist = self.db.query(Therapist).filter(
            Therapist.id == claim.therapist_id
        ).first()

        # Build appeal letter
        letter = f"""
{datetime.now().strftime('%B %d, %Y')}

{claim.payer_name}
Appeals Department
[Address]

Re: Appeal of Denied Claim
Claim Number: {claim.claim_number}
Payer Claim Number: {claim.payer_claim_number or 'N/A'}
Patient: {intake.last_name}, {intake.first_name}
Member ID: {claim.member_id}
Date of Service: {claim.date_of_service.strftime('%m/%d/%Y')}

Dear Appeals Reviewer,

I am writing to formally appeal the denial of the above-referenced claim.

REASON FOR APPEAL:

The claim was denied for the following reason: "{claim.denial_reason_text or 'Not specified'}"

We respectfully disagree with this denial for the following reasons:

"""

        # Add specific appeal arguments based on denial reason
        if claim.denial_reason == DenialReason.MEDICAL_NECESSITY:
            letter += """
1. MEDICAL NECESSITY JUSTIFICATION:

The physical therapy services provided were medically necessary for the treatment of the patient's
diagnosed condition. The patient presented with {diagnosis}, which significantly impaired their
functional mobility and activities of daily living.

The evaluation revealed objective findings including:
- {objective_findings}

The treatment plan was developed based on clinical guidelines and best practices for {diagnosis}.
The interventions provided were appropriate, specific to the patient's condition, and resulted in
measurable functional improvements.

Supporting Documentation Enclosed:
- Initial evaluation with objective measurements
- Treatment plan with specific goals
- Progress notes documenting functional improvements
- Physician referral and prescription for physical therapy
- Research evidence supporting treatment approach

"""

        elif claim.denial_reason == DenialReason.INVALID_CODING:
            letter += f"""
1. CODING JUSTIFICATION:

The CPT codes billed accurately reflect the services provided:

"""
            for code in claim.cpt_codes:
                letter += f"- {code['code']}: {code['description']}\n"

            letter += """

The clinical documentation clearly supports these codes. Each intervention was:
- Medically necessary for the patient's condition
- Performed face-to-face with the patient
- Documented with time, specific techniques, and patient response
- Consistent with accepted standards of practice

"""

        elif claim.denial_reason == DenialReason.AUTH_REQUIRED:
            letter += """
1. AUTHORIZATION STATUS:

We acknowledge that authorization was required for these services. However, we respectfully request
retroactive authorization for the following reasons:

- The services were medically urgent and necessary at the time
- The patient's condition required immediate intervention
- Delay in treatment would have resulted in functional decline
- The services provided are covered benefits under the patient's plan

We are submitting a retroactive authorization request concurrently with this appeal.

"""

        # Add conclusion
        letter += f"""
REQUESTED ACTION:

We respectfully request that you:
1. Overturn the denial of this claim
2. Process payment for the services rendered in the amount of ${claim.total_charges:.2f}
3. Provide written confirmation of the appeal decision

If you require any additional information or documentation, please contact our billing department
at (555) 123-4567.

Thank you for your prompt attention to this matter. We look forward to a favorable resolution.

Sincerely,

{therapist.first_name} {therapist.last_name}, {therapist.credentials or 'PT'}
Treating Therapist

Billing Department
Your Therapy Clinic
[Contact Information]

Enclosures: Supporting clinical documentation
"""

        return letter

    async def submit_appeal(
        self,
        claim_id: int,
        appeal_letter: str,
        supporting_documents: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[DenialAppeal]]:
        """
        Submit appeal for denied claim.

        Args:
            claim_id: Claim ID
            appeal_letter: Generated appeal letter
            supporting_documents: List of document paths

        Returns:
            Tuple of (success, DenialAppeal record)
        """
        try:
            claim = self.db.query(Claim).filter(Claim.id == claim_id).first()

            if not claim:
                logger.error(f"Claim {claim_id} not found")
                return False, None

            # Determine appeal level
            appeal_level = "first"
            if claim.appeal_count > 0:
                appeal_level = "second" if claim.appeal_count == 1 else "third"

            # Generate appeal number
            appeal_number = f"APL{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Create appeal record
            appeal = DenialAppeal(
                claim_id=claim.id,
                appeal_number=appeal_number,
                appeal_level=appeal_level,
                submitted_at=datetime.utcnow(),
                submitted_by="system",
                submission_method="mail",  # or "portal", "fax"
                clinical_rationale=appeal_letter,
                supporting_documents=supporting_documents or []
            )

            self.db.add(appeal)

            # Update claim
            claim.status = ClaimStatus.APPEALED
            claim.appeal_count += 1

            self.db.commit()
            self.db.refresh(appeal)

            logger.info(f"Submitted appeal {appeal_number} for claim {claim.claim_number}")

            # TODO: Actually send appeal via mail/portal/fax
            # For now, just create the record

            return True, appeal

        except Exception as e:
            logger.error(f"Error submitting appeal: {str(e)}", exc_info=True)
            self.db.rollback()
            return False, None

    def track_appeal_success_rates(self) -> Dict:
        """
        Calculate appeal success rates by denial reason.

        Returns:
            Dict with success rates
        """
        appeals = self.db.query(DenialAppeal).filter(
            DenialAppeal.decision.isnot(None)
        ).all()

        stats = {}

        for appeal in appeals:
            claim = self.db.query(Claim).filter(Claim.id == appeal.claim_id).first()

            if not claim or not claim.denial_reason:
                continue

            reason = claim.denial_reason.value

            if reason not in stats:
                stats[reason] = {
                    "total": 0,
                    "approved": 0,
                    "partially_approved": 0,
                    "denied": 0,
                    "success_rate": 0.0
                }

            stats[reason]["total"] += 1

            if appeal.decision == "approved":
                stats[reason]["approved"] += 1
            elif appeal.decision == "partially_approved":
                stats[reason]["partially_approved"] += 1
            elif appeal.decision == "denied":
                stats[reason]["denied"] += 1

        # Calculate success rates
        for reason, data in stats.items():
            if data["total"] > 0:
                data["success_rate"] = (
                    (data["approved"] + data["partially_approved"]) / data["total"]
                ) * 100

        logger.info(f"Appeal success rates calculated for {len(stats)} denial reasons")

        return stats

    def identify_prevention_opportunities(self) -> List[Dict]:
        """
        Identify patterns in denials to prevent future occurrences.

        Returns:
            List of prevention recommendations
        """
        # Get recent denials (last 90 days)
        cutoff_date = date.today() - timedelta(days=90)

        recent_denials = self.db.query(Claim).filter(
            and_(
                Claim.is_denied == True,
                Claim.adjudication_date >= cutoff_date
            )
        ).all()

        # Group by denial reason
        denial_counts = {}
        for claim in recent_denials:
            reason = claim.denial_reason.value if claim.denial_reason else "unknown"
            denial_counts[reason] = denial_counts.get(reason, 0) + 1

        # Generate recommendations
        recommendations = []

        for reason, count in sorted(denial_counts.items(), key=lambda x: x[1], reverse=True):
            if count >= 5:  # Significant pattern
                rec = {
                    "denial_reason": reason,
                    "occurrence_count": count,
                    "recommendation": self._get_prevention_recommendation(reason),
                    "priority": "high" if count >= 10 else "medium"
                }
                recommendations.append(rec)

        logger.info(f"Identified {len(recommendations)} prevention opportunities")

        return recommendations

    def _get_prevention_recommendation(self, denial_reason: str) -> str:
        """Get specific recommendation for denial reason."""
        recommendations = {
            "missing_info": "Implement pre-submission checklist to ensure all required documentation is attached",
            "invalid_coding": "Provide additional coding training for therapists; implement automated code validation",
            "not_covered": "Verify coverage before service delivery; implement pre-authorization workflow",
            "auth_required": "Implement authorization tracking system; automated reminders for expiring authorizations",
            "duplicate_claim": "Enhance claim tracking to prevent duplicate submissions",
            "timely_filing": "Implement automated claim submission workflow to ensure timely filing",
            "medical_necessity": "Enhance documentation templates to better capture medical necessity; provide training on documentation requirements",
            "credentialing": "Ensure all providers are credentialed before seeing patients; track credentialing expiration dates"
        }

        return recommendations.get(denial_reason, "Review denial patterns and implement targeted training")

    def get_denial_trends(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Analyze denial trends over time period.

        Returns:
            Dict with trend analysis
        """
        denials = self.db.query(Claim).filter(
            and_(
                Claim.is_denied == True,
                Claim.adjudication_date >= start_date,
                Claim.adjudication_date <= end_date
            )
        ).all()

        total_claims = self.db.query(Claim).filter(
            and_(
                Claim.adjudication_date >= start_date,
                Claim.adjudication_date <= end_date
            )
        ).count()

        denied_count = len(denials)
        denial_rate = (denied_count / total_claims * 100) if total_claims > 0 else 0

        # Group by reason
        by_reason = {}
        for denial in denials:
            reason = denial.denial_reason.value if denial.denial_reason else "unknown"
            by_reason[reason] = by_reason.get(reason, 0) + 1

        # Calculate denied amounts
        total_denied_amount = sum(d.total_charges for d in denials)

        trends = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_claims": total_claims,
            "denied_claims": denied_count,
            "denial_rate": round(denial_rate, 2),
            "total_denied_amount": round(total_denied_amount, 2),
            "denials_by_reason": by_reason,
            "top_denial_reason": max(by_reason.items(), key=lambda x: x[1])[0] if by_reason else None
        }

        return trends
