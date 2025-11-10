"""Insurance eligibility verification and benefits checking engine."""
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime, date, timedelta
import httpx
import json

from database.scheduling_models import InsuranceVerification, InsuranceStatus, PatientIntake
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class InsuranceEligibilityEngine:
    """
    Real-time insurance eligibility verification.

    Supports multiple clearinghouses:
    - Change Healthcare
    - Availity
    - Waystar
    - Direct payer APIs
    """

    def __init__(
        self,
        db: Session,
        provider: str = "change_healthcare",
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.db = db
        self.provider = provider
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.username = username
        self.password = password
        self.timeout = 30.0

    async def verify_eligibility(
        self,
        patient_intake: PatientIntake,
        payer_name: str,
        member_id: str,
        group_number: Optional[str] = None,
        date_of_service: Optional[date] = None,
        service_type_code: str = "30"  # 30 = Physical Therapy
    ) -> Tuple[bool, Dict]:
        """
        Verify insurance eligibility and benefits.

        Args:
            patient_intake: Patient intake record
            payer_name: Insurance payer name
            member_id: Member/subscriber ID
            group_number: Group number (if applicable)
            date_of_service: Date of service (defaults to today)
            service_type_code: Healthcare service type code

        Returns:
            Tuple of (success, verification_data)
        """
        if not date_of_service:
            date_of_service = date.today()

        try:
            # Route to appropriate provider
            if self.provider == "change_healthcare":
                return await self._verify_change_healthcare(
                    patient_intake, payer_name, member_id, group_number, date_of_service, service_type_code
                )
            elif self.provider == "availity":
                return await self._verify_availity(
                    patient_intake, payer_name, member_id, group_number, date_of_service, service_type_code
                )
            elif self.provider == "waystar":
                return await self._verify_waystar(
                    patient_intake, payer_name, member_id, group_number, date_of_service, service_type_code
                )
            else:
                logger.error(f"Unsupported insurance provider: {self.provider}")
                return False, {"error": "Unsupported provider"}

        except Exception as e:
            logger.error(f"Insurance verification failed: {str(e)}", exc_info=True)
            return False, {"error": str(e)}

    async def _verify_change_healthcare(
        self,
        patient_intake: PatientIntake,
        payer_name: str,
        member_id: str,
        group_number: Optional[str],
        date_of_service: date,
        service_type_code: str
    ) -> Tuple[bool, Dict]:
        """
        Verify via Change Healthcare (formerly Emdeon).

        Uses X12 270/271 transaction for eligibility.
        """
        endpoint = self.api_endpoint or "https://api.changehealthcare.com/medicalnetwork/eligibility/v3"

        # Build X12 270 request
        request_payload = {
            "controlNumber": f"CTRL{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "tradingPartnerServiceId": self._get_payer_id(payer_name),
            "provider": {
                "organizationName": "Your Therapy Clinic",
                "npi": "1234567890",  # TODO: Get from facility/provider config
                "taxId": "123456789"
            },
            "subscriber": {
                "memberId": member_id,
                "firstName": patient_intake.first_name,
                "lastName": patient_intake.last_name,
                "gender": "M",  # TODO: Get from patient intake
                "dateOfBirth": patient_intake.date_of_birth.strftime("%Y%m%d")
            },
            "encounter": {
                "serviceTypeCodes": [service_type_code],
                "beginningDateOfService": date_of_service.strftime("%Y%m%d")
            }
        }

        if group_number:
            request_payload["subscriber"]["groupNumber"] = group_number

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Change Healthcare API error: {response.status_code} - {response.text}")
                    return False, {"error": f"API error: {response.status_code}"}

                result = response.json()
                return await self._parse_change_healthcare_response(result)

        except httpx.TimeoutException:
            logger.error("Change Healthcare API timeout")
            return False, {"error": "API timeout"}
        except Exception as e:
            logger.error(f"Change Healthcare verification error: {str(e)}")
            return False, {"error": str(e)}

    async def _parse_change_healthcare_response(self, response: Dict) -> Tuple[bool, Dict]:
        """Parse X12 271 response from Change Healthcare."""
        try:
            # Extract eligibility status
            eligibility = response.get("eligibilityInfo", [])

            if not eligibility:
                return False, {
                    "error": "No eligibility information returned",
                    "raw_response": response
                }

            # Find active coverage for physical therapy
            active_coverage = None
            for coverage in eligibility:
                if coverage.get("serviceTypeCodes") == ["30"] and coverage.get("eligibilityStatus") == "1":
                    active_coverage = coverage
                    break

            if not active_coverage:
                return False, {
                    "error": "No active coverage for physical therapy",
                    "eligibility_status": "inactive"
                }

            # Extract benefits
            benefits = active_coverage.get("benefitsInformation", [])

            verification_data = {
                "is_active": True,
                "eligibility_status": "active",
                "effective_date": self._parse_date(active_coverage.get("planBeginDate")),
                "termination_date": self._parse_date(active_coverage.get("planEndDate")),
                "copay_amount": self._extract_copay(benefits),
                "deductible_amount": self._extract_deductible(benefits),
                "deductible_met": self._extract_deductible_met(benefits),
                "coinsurance_percentage": self._extract_coinsurance(benefits),
                "out_of_pocket_max": self._extract_oop_max(benefits),
                "requires_authorization": self._requires_authorization(benefits),
                "visits_authorized": self._extract_visit_limit(benefits),
                "payer_id": response.get("tradingPartnerServiceId"),
                "raw_response": response
            }

            return True, verification_data

        except Exception as e:
            logger.error(f"Error parsing Change Healthcare response: {str(e)}")
            return False, {"error": f"Parse error: {str(e)}", "raw_response": response}

    async def _verify_availity(
        self,
        patient_intake: PatientIntake,
        payer_name: str,
        member_id: str,
        group_number: Optional[str],
        date_of_service: date,
        service_type_code: str
    ) -> Tuple[bool, Dict]:
        """
        Verify via Availity portal API.
        """
        endpoint = self.api_endpoint or "https://api.availity.com/availity/v1/coverages"

        request_payload = {
            "customerId": member_id,
            "payerId": self._get_payer_id(payer_name),
            "serviceTypeCode": service_type_code,
            "serviceDate": date_of_service.isoformat(),
            "providerNpi": "1234567890",  # TODO: Get from config
            "subscriber": {
                "firstName": patient_intake.first_name,
                "lastName": patient_intake.last_name,
                "dateOfBirth": patient_intake.date_of_birth.isoformat()
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    return False, {"error": f"API error: {response.status_code}"}

                result = response.json()
                return await self._parse_availity_response(result)

        except Exception as e:
            logger.error(f"Availity verification error: {str(e)}")
            return False, {"error": str(e)}

    async def _parse_availity_response(self, response: Dict) -> Tuple[bool, Dict]:
        """Parse Availity API response."""
        try:
            coverage = response.get("coverage", {})

            if not coverage.get("isActive"):
                return False, {
                    "error": "Coverage is not active",
                    "eligibility_status": "inactive"
                }

            verification_data = {
                "is_active": True,
                "eligibility_status": "active",
                "effective_date": coverage.get("effectiveDate"),
                "termination_date": coverage.get("terminationDate"),
                "copay_amount": coverage.get("copay", {}).get("amount"),
                "deductible_amount": coverage.get("deductible", {}).get("amount"),
                "deductible_met": coverage.get("deductible", {}).get("amountMet"),
                "coinsurance_percentage": coverage.get("coinsurance", {}).get("percentage"),
                "out_of_pocket_max": coverage.get("outOfPocketMax", {}).get("amount"),
                "requires_authorization": coverage.get("requiresAuthorization", False),
                "visits_authorized": coverage.get("visitLimit"),
                "raw_response": response
            }

            return True, verification_data

        except Exception as e:
            logger.error(f"Error parsing Availity response: {str(e)}")
            return False, {"error": f"Parse error: {str(e)}", "raw_response": response}

    async def _verify_waystar(
        self,
        patient_intake: PatientIntake,
        payer_name: str,
        member_id: str,
        group_number: Optional[str],
        date_of_service: date,
        service_type_code: str
    ) -> Tuple[bool, Dict]:
        """
        Verify via Waystar (formerly ZirMed).
        """
        # TODO: Implement Waystar API integration
        logger.warning("Waystar integration not yet implemented")
        return False, {"error": "Waystar provider not yet supported"}

    def _get_payer_id(self, payer_name: str) -> str:
        """
        Get payer ID for clearinghouse routing.

        In production, this would look up from payer database.
        """
        # Common payer IDs (examples)
        payer_map = {
            "blue cross blue shield": "BCBS",
            "aetna": "AETNA",
            "united healthcare": "UHCSR",
            "cigna": "CIGNA",
            "humana": "HUMANA",
            "medicare": "MEDICARE",
            "medicaid": "MEDICAID"
        }

        payer_lower = payer_name.lower()
        for key, value in payer_map.items():
            if key in payer_lower:
                return value

        # Default return payer name as ID
        return payer_name.upper().replace(" ", "_")

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date from various formats."""
        if not date_str:
            return None

        try:
            # Try YYYYMMDD format
            if len(date_str) == 8:
                return datetime.strptime(date_str, "%Y%m%d").date()
            # Try ISO format
            return datetime.fromisoformat(date_str).date()
        except:
            return None

    def _extract_copay(self, benefits: List[Dict]) -> Optional[float]:
        """Extract copay amount from benefits."""
        for benefit in benefits:
            if benefit.get("code") in ["B", "30"]:  # Copay codes
                return float(benefit.get("monetaryAmount", 0))
        return None

    def _extract_deductible(self, benefits: List[Dict]) -> Optional[float]:
        """Extract deductible amount from benefits."""
        for benefit in benefits:
            if benefit.get("code") == "C":  # Deductible code
                return float(benefit.get("monetaryAmount", 0))
        return None

    def _extract_deductible_met(self, benefits: List[Dict]) -> Optional[float]:
        """Extract deductible met amount from benefits."""
        for benefit in benefits:
            if benefit.get("code") == "C" and benefit.get("qualifier") == "YTD":
                return float(benefit.get("monetaryAmount", 0))
        return None

    def _extract_coinsurance(self, benefits: List[Dict]) -> Optional[float]:
        """Extract coinsurance percentage from benefits."""
        for benefit in benefits:
            if benefit.get("code") == "A":  # Coinsurance code
                return float(benefit.get("percent", 0))
        return None

    def _extract_oop_max(self, benefits: List[Dict]) -> Optional[float]:
        """Extract out-of-pocket maximum from benefits."""
        for benefit in benefits:
            if benefit.get("code") == "G":  # OOP max code
                return float(benefit.get("monetaryAmount", 0))
        return None

    def _requires_authorization(self, benefits: List[Dict]) -> bool:
        """Check if authorization is required."""
        for benefit in benefits:
            if benefit.get("authorizationRequired") == "Y":
                return True
        return False

    def _extract_visit_limit(self, benefits: List[Dict]) -> Optional[int]:
        """Extract visit limit from benefits."""
        for benefit in benefits:
            if benefit.get("code") == "R" and "visits" in str(benefit.get("description", "")).lower():
                return int(benefit.get("quantity", 0))
        return None

    async def batch_verify(
        self,
        verifications: List[Dict]
    ) -> List[Tuple[bool, Dict]]:
        """
        Batch verify multiple patients.

        Args:
            verifications: List of dicts with patient_intake, payer_name, member_id, etc.

        Returns:
            List of (success, verification_data) tuples
        """
        results = []

        for verification in verifications:
            patient_intake = verification["patient_intake"]
            payer_name = verification["payer_name"]
            member_id = verification["member_id"]
            group_number = verification.get("group_number")
            date_of_service = verification.get("date_of_service")

            result = await self.verify_eligibility(
                patient_intake, payer_name, member_id, group_number, date_of_service
            )
            results.append(result)

        return results

    def create_verification_record(
        self,
        patient_intake_id: int,
        payer_name: str,
        member_id: str,
        verification_data: Dict
    ) -> InsuranceVerification:
        """
        Create database record for verification result.

        Args:
            patient_intake_id: Patient intake ID
            payer_name: Payer name
            member_id: Member ID
            verification_data: Verification result data

        Returns:
            InsuranceVerification record
        """
        verification = InsuranceVerification(
            patient_intake_id=patient_intake_id,
            payer_name=payer_name,
            member_id=member_id,
            verification_status=InsuranceStatus.VERIFIED if verification_data.get("is_active") else InsuranceStatus.INVALID,
            verified_at=datetime.utcnow(),
            verified_by="system",
            is_active=verification_data.get("is_active", False),
            effective_date=verification_data.get("effective_date"),
            termination_date=verification_data.get("termination_date"),
            copay_amount=verification_data.get("copay_amount"),
            deductible_amount=verification_data.get("deductible_amount"),
            deductible_met=verification_data.get("deductible_met"),
            coinsurance_percentage=verification_data.get("coinsurance_percentage"),
            out_of_pocket_max=verification_data.get("out_of_pocket_max"),
            requires_authorization=verification_data.get("requires_authorization", False),
            visits_authorized=verification_data.get("visits_authorized"),
            raw_response=verification_data.get("raw_response", {})
        )

        self.db.add(verification)
        self.db.commit()
        self.db.refresh(verification)

        logger.info(f"Created insurance verification record: {verification.id}")

        return verification
