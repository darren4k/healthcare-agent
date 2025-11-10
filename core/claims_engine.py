"""Automated claims submission and management engine."""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
import httpx
import json

from database.revenue_models import (
    Claim, ClaimLine, ClaimStatus, ClaimAdjustment,
    Payment, Authorization, BillingCode
)
from database.scheduling_models import Appointment, PatientIntake, Therapist, AppointmentStatus
from database.models import NoteDraft

logger = logging.getLogger(__name__)


class ClaimsAutomationEngine:
    """
    Automated claims creation and submission.

    Features:
    - Auto-generate claims from completed appointments
    - CPT/ICD-10 code intelligence
    - EDI 837 submission
    - Claim status tracking
    - Denial detection and alerting
    """

    def __init__(
        self,
        db: Session,
        clearinghouse: str = "change_healthcare",
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.db = db
        self.clearinghouse = clearinghouse
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.timeout = 60.0

    async def auto_generate_claim(
        self,
        appointment_id: int
    ) -> Optional[Claim]:
        """
        Automatically generate claim from completed appointment.

        Args:
            appointment_id: Appointment ID

        Returns:
            Created Claim or None if error
        """
        try:
            # Get appointment
            appointment = self.db.query(Appointment).filter(
                Appointment.id == appointment_id
            ).first()

            if not appointment:
                logger.error(f"Appointment {appointment_id} not found")
                return None

            if appointment.status != AppointmentStatus.COMPLETED:
                logger.warning(f"Appointment {appointment_id} not completed, skipping claim generation")
                return None

            # Get patient intake
            intake = self.db.query(PatientIntake).filter(
                PatientIntake.id == appointment.patient_intake_id
            ).first()

            if not intake:
                logger.error(f"Patient intake {appointment.patient_intake_id} not found")
                return None

            # Check if insurance verification exists
            if not intake.primary_insurance_id:
                logger.info(f"No insurance for appointment {appointment_id}, skipping claim")
                return None

            # Get SOAP note if available for diagnosis codes
            note_draft = self.db.query(NoteDraft).filter(
                NoteDraft.id == appointment.session_notes_id
            ).first() if appointment.session_notes_id else None

            # Generate CPT and ICD-10 codes
            cpt_codes = await self._generate_cpt_codes(appointment, note_draft)
            icd10_codes = await self._generate_icd10_codes(appointment, intake, note_draft)

            # Calculate charges
            total_charges = self._calculate_total_charges(cpt_codes)

            # Generate unique claim number
            claim_number = self._generate_claim_number()

            # Create claim
            claim = Claim(
                claim_number=claim_number,
                appointment_id=appointment.id,
                patient_intake_id=intake.id,
                therapist_id=appointment.therapist_id,
                facility_id=appointment.facility_id,
                payer_name=intake.primary_insurance_name,
                payer_id=self._get_payer_id(intake.primary_insurance_name),
                member_id=intake.primary_insurance_id,
                group_number=intake.primary_insurance_group,
                date_of_service=appointment.scheduled_start.date(),
                service_from_date=appointment.scheduled_start.date(),
                service_to_date=appointment.scheduled_end.date() if appointment.scheduled_end else appointment.scheduled_start.date(),
                cpt_codes=cpt_codes,
                icd10_codes=icd10_codes,
                total_charges=total_charges,
                status=ClaimStatus.READY_TO_SUBMIT,
                created_at=datetime.utcnow()
            )

            self.db.add(claim)
            self.db.commit()
            self.db.refresh(claim)

            # Create claim lines
            for idx, cpt in enumerate(cpt_codes, start=1):
                line = ClaimLine(
                    claim_id=claim.id,
                    line_number=idx,
                    cpt_code=cpt["code"],
                    cpt_description=cpt["description"],
                    modifiers=cpt.get("modifiers", []),
                    units=cpt.get("units", 1),
                    charge_amount=cpt["charge"],
                    service_date=appointment.scheduled_start.date()
                )
                self.db.add(line)

            self.db.commit()

            logger.info(f"Auto-generated claim {claim.claim_number} for appointment {appointment_id}")

            return claim

        except Exception as e:
            logger.error(f"Error auto-generating claim for appointment {appointment_id}: {str(e)}", exc_info=True)
            self.db.rollback()
            return None

    async def _generate_cpt_codes(
        self,
        appointment: Appointment,
        note_draft: Optional[NoteDraft] = None
    ) -> List[Dict]:
        """
        Generate appropriate CPT codes based on visit type and documentation.

        Uses AI to analyze SOAP note and recommend billing codes.
        """
        cpt_codes = []

        # Get duration in minutes
        if appointment.actual_end and appointment.actual_start:
            duration = (appointment.actual_end - appointment.actual_start).total_seconds() / 60
        else:
            duration = appointment.duration_minutes

        # Base PT evaluation or treatment code
        if appointment.visit_type.value == "evaluation":
            # PT evaluation codes based on complexity
            if duration >= 60:
                cpt_codes.append({
                    "code": "97163",
                    "description": "Physical therapy evaluation - high complexity",
                    "modifiers": [],
                    "units": 1,
                    "charge": 175.00
                })
            elif duration >= 45:
                cpt_codes.append({
                    "code": "97162",
                    "description": "Physical therapy evaluation - moderate complexity",
                    "modifiers": [],
                    "units": 1,
                    "charge": 150.00
                })
            else:
                cpt_codes.append({
                    "code": "97161",
                    "description": "Physical therapy evaluation - low complexity",
                    "modifiers": [],
                    "units": 1,
                    "charge": 125.00
                })

        elif appointment.visit_type.value == "re_evaluation":
            cpt_codes.append({
                "code": "97164",
                "description": "Physical therapy re-evaluation",
                "modifiers": [],
                "units": 1,
                "charge": 100.00
            })

        else:  # Treatment
            # Therapeutic exercises
            if duration >= 15:
                cpt_codes.append({
                    "code": "97110",
                    "description": "Therapeutic exercises",
                    "modifiers": [],
                    "units": self._calculate_units(duration, 15),
                    "charge": 45.00 * self._calculate_units(duration, 15)
                })

            # Manual therapy
            if duration >= 30:
                cpt_codes.append({
                    "code": "97140",
                    "description": "Manual therapy techniques",
                    "modifiers": [],
                    "units": self._calculate_units(duration, 15),
                    "charge": 50.00 * self._calculate_units(duration, 15)
                })

            # Neuromuscular reeducation
            if duration >= 45:
                cpt_codes.append({
                    "code": "97112",
                    "description": "Neuromuscular reeducation",
                    "modifiers": [],
                    "units": 1,
                    "charge": 45.00
                })

        # If we have SOAP note, use AI to refine codes
        if note_draft:
            cpt_codes = await self._ai_refine_cpt_codes(cpt_codes, note_draft)

        return cpt_codes

    async def _generate_icd10_codes(
        self,
        appointment: Appointment,
        intake: PatientIntake,
        note_draft: Optional[NoteDraft] = None
    ) -> List[Dict]:
        """
        Generate ICD-10 diagnosis codes.

        Uses patient intake diagnosis and SOAP note assessment.
        """
        icd10_codes = []

        # Parse diagnosis from intake
        if intake.diagnosis:
            # Common PT diagnoses mapping
            diagnosis_map = {
                "low back pain": {"code": "M54.5", "description": "Low back pain"},
                "shoulder pain": {"code": "M25.511", "description": "Pain in right shoulder"},
                "knee pain": {"code": "M25.561", "description": "Pain in right knee"},
                "neck pain": {"code": "M54.2", "description": "Cervicalgia"},
                "hip pain": {"code": "M25.551", "description": "Pain in right hip"},
            }

            diagnosis_lower = intake.diagnosis.lower()
            for key, icd_info in diagnosis_map.items():
                if key in diagnosis_lower:
                    icd10_codes.append(icd_info)
                    break

        # If no match, use generic pain code
        if not icd10_codes:
            icd10_codes.append({
                "code": "M79.1",
                "description": "Myalgia"
            })

        # If we have SOAP note assessment, use AI to refine
        if note_draft and note_draft.assessment:
            icd10_codes = await self._ai_refine_icd10_codes(icd10_codes, note_draft.assessment)

        return icd10_codes

    async def _ai_refine_cpt_codes(
        self,
        initial_codes: List[Dict],
        note_draft: NoteDraft
    ) -> List[Dict]:
        """
        Use AI to refine CPT codes based on SOAP note documentation.

        Analyzes objective and plan sections to ensure codes match documented interventions.
        """
        # TODO: Integrate with LLM to analyze SOAP note and recommend codes
        # For now, return initial codes
        return initial_codes

    async def _ai_refine_icd10_codes(
        self,
        initial_codes: List[Dict],
        assessment: str
    ) -> List[Dict]:
        """
        Use AI to refine ICD-10 codes based on assessment.
        """
        # TODO: Integrate with LLM to analyze assessment and recommend codes
        return initial_codes

    def _calculate_units(self, duration_minutes: float, unit_minutes: int = 15) -> int:
        """
        Calculate billing units based on 8-minute rule.

        Args:
            duration_minutes: Total treatment time
            unit_minutes: Minutes per unit (typically 15)

        Returns:
            Number of billable units
        """
        # 8-minute rule: need at least 8 minutes to bill 1 unit
        if duration_minutes < 8:
            return 0

        # For each 15-minute unit, need at least 8 minutes
        # 8-22 min = 1 unit, 23-37 min = 2 units, etc.
        units = int((duration_minutes + 7) / 15)
        return max(1, units)

    def _calculate_total_charges(self, cpt_codes: List[Dict]) -> float:
        """Calculate total charges from CPT codes."""
        return sum(code["charge"] for code in cpt_codes)

    def _generate_claim_number(self) -> str:
        """Generate unique claim number."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"CLM{timestamp}"

    def _get_payer_id(self, payer_name: str) -> str:
        """Get payer ID for clearinghouse routing."""
        payer_map = {
            "blue cross blue shield": "BCBS",
            "aetna": "AETNA",
            "united healthcare": "UHCSR",
            "cigna": "CIGNA",
            "humana": "HUMANA",
        }

        payer_lower = payer_name.lower()
        for key, value in payer_map.items():
            if key in payer_lower:
                return value

        return payer_name.upper().replace(" ", "_")

    async def submit_claim(
        self,
        claim_id: int,
        submission_method: str = "EDI"
    ) -> Tuple[bool, Optional[str]]:
        """
        Submit claim to clearinghouse.

        Args:
            claim_id: Claim ID
            submission_method: EDI, paper, or portal

        Returns:
            Tuple of (success, submission_reference)
        """
        try:
            claim = self.db.query(Claim).filter(Claim.id == claim_id).first()

            if not claim:
                logger.error(f"Claim {claim_id} not found")
                return False, None

            if claim.status not in [ClaimStatus.DRAFT, ClaimStatus.READY_TO_SUBMIT]:
                logger.warning(f"Claim {claim_id} already submitted (status: {claim.status.value})")
                return False, None

            if submission_method == "EDI":
                success, reference = await self._submit_via_edi(claim)
            else:
                logger.error(f"Unsupported submission method: {submission_method}")
                return False, None

            if success:
                # Update claim status
                claim.status = ClaimStatus.SUBMITTED
                claim.submitted_at = datetime.utcnow()
                claim.submission_method = submission_method
                claim.submission_reference = reference
                self.db.commit()

                logger.info(f"Claim {claim.claim_number} submitted successfully: {reference}")

            return success, reference

        except Exception as e:
            logger.error(f"Error submitting claim {claim_id}: {str(e)}", exc_info=True)
            self.db.rollback()
            return False, None

    async def _submit_via_edi(self, claim: Claim) -> Tuple[bool, Optional[str]]:
        """
        Submit claim via EDI 837 transaction.

        Uses clearinghouse API to submit X12 837P (professional) claim.
        """
        endpoint = self.api_endpoint or "https://api.changehealthcare.com/medicalnetwork/professionalclaims/v3"

        # Get claim lines
        claim_lines = self.db.query(ClaimLine).filter(
            ClaimLine.claim_id == claim.id
        ).all()

        # Build EDI 837 payload
        payload = {
            "controlNumber": f"CTRL{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "tradingPartnerServiceId": claim.payer_id,
            "submitter": {
                "organizationName": "Your Therapy Clinic",
                "contactInformation": {
                    "name": "Billing Department",
                    "phoneNumber": "5551234567"
                }
            },
            "receiver": {
                "organizationName": claim.payer_name
            },
            "subscriber": {
                "memberId": claim.member_id,
                "paymentResponsibilityLevelCode": "P",  # Primary
                "groupNumber": claim.group_number
            },
            "claim": {
                "claimInformation": {
                    "claimFilingCode": "CI",  # Commercial insurance
                    "patientControlNumber": claim.claim_number,
                    "claimChargeAmount": str(claim.total_charges),
                    "placeOfServiceCode": "11",  # Office
                    "claimFrequencyCode": "1",  # Original
                    "providerSignatureIndicator": "Y",
                    "assignmentOfBenefitsIndicator": "Y"
                },
                "serviceLines": [
                    {
                        "lineItemControlNumber": str(line.line_number),
                        "professionalService": {
                            "procedureIdentifier": line.cpt_code,
                            "lineItemChargeAmount": str(line.charge_amount),
                            "measurementUnit": "UN",
                            "serviceUnitCount": str(line.units)
                        },
                        "serviceDateInformation": {
                            "date": line.service_date.strftime("%Y%m%d")
                        }
                    }
                    for line in claim_lines
                ],
                "diagnosisCodes": [
                    {
                        "diagnosisCodeQualifier": "ABK",  # ICD-10
                        "diagnosisCode": code["code"]
                    }
                    for code in claim.icd10_codes
                ]
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code not in [200, 201]:
                    logger.error(f"EDI submission failed: {response.status_code} - {response.text}")
                    return False, None

                result = response.json()
                submission_reference = result.get("controlNumber") or result.get("submissionId")

                return True, submission_reference

        except httpx.TimeoutException:
            logger.error("EDI submission timeout")
            return False, None
        except Exception as e:
            logger.error(f"EDI submission error: {str(e)}")
            return False, None

    async def check_claim_status(
        self,
        claim_id: int
    ) -> Optional[Dict]:
        """
        Check claim status with payer.

        Uses EDI 276/277 transaction for claim status inquiry.
        """
        try:
            claim = self.db.query(Claim).filter(Claim.id == claim_id).first()

            if not claim:
                return None

            endpoint = self.api_endpoint or "https://api.changehealthcare.com/medicalnetwork/claimstatus/v3"

            payload = {
                "controlNumber": f"CTRL{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "tradingPartnerServiceId": claim.payer_id,
                "provider": {
                    "organizationName": "Your Therapy Clinic",
                    "npi": "1234567890"
                },
                "subscriber": {
                    "memberId": claim.member_id
                },
                "claimStatusTracking": {
                    "claimControlNumber": claim.payer_claim_number or claim.claim_number,
                    "serviceDate": claim.date_of_service.strftime("%Y%m%d")
                }
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Claim status check failed: {response.status_code}")
                    return None

                result = response.json()
                return self._parse_claim_status(result, claim)

        except Exception as e:
            logger.error(f"Error checking claim status: {str(e)}")
            return None

    def _parse_claim_status(self, response: Dict, claim: Claim) -> Dict:
        """Parse EDI 277 claim status response."""
        try:
            status_info = response.get("claimStatusTracking", {})
            status_code = status_info.get("statusCode")

            status_map = {
                "1": "processed_primary",
                "2": "processed_secondary",
                "3": "processed_tertiary",
                "4": "denied",
                "19": "in_review",
                "20": "pending"
            }

            status = status_map.get(status_code, "unknown")

            # Update claim if status changed
            if status == "denied":
                claim.status = ClaimStatus.DENIED
                claim.is_denied = True
                claim.denial_reason_text = status_info.get("statusDescription")
                self.db.commit()
            elif status.startswith("processed"):
                claim.status = ClaimStatus.APPROVED
                self.db.commit()

            return {
                "status": status,
                "status_code": status_code,
                "status_description": status_info.get("statusDescription"),
                "check_number": status_info.get("checkNumber"),
                "payment_date": status_info.get("paymentDate"),
                "paid_amount": status_info.get("paidAmount")
            }

        except Exception as e:
            logger.error(f"Error parsing claim status: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def batch_submit_claims(
        self,
        claim_ids: List[int]
    ) -> Dict[str, int]:
        """
        Submit multiple claims in batch.

        Returns:
            Dict with counts: {submitted, failed}
        """
        stats = {"submitted": 0, "failed": 0}

        for claim_id in claim_ids:
            success, _ = await self.submit_claim(claim_id)
            if success:
                stats["submitted"] += 1
            else:
                stats["failed"] += 1

        logger.info(f"Batch submission complete: {stats['submitted']} submitted, {stats['failed']} failed")

        return stats
