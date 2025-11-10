"""Natural Language Interface - Conversational AI for task execution."""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
import json

logger = logging.getLogger(__name__)


class NaturalLanguageInterface:
    """
    Conversational AI interface for executing tasks via natural language.

    Examples:
    - "Schedule John Doe for PT eval next Tuesday at 10am"
    - "Show me all denied claims from last month"
    - "What's the no-show rate for Dr. Johnson this week?"
    - "Send appointment reminders for tomorrow"
    - "Generate a claim for appointment #123"
    """

    def __init__(self, db, llm_endpoint: str, api_key: str):
        self.db = db
        self.llm_endpoint = llm_endpoint
        self.api_key = api_key

    async def process_command(self, user_input: str, user_context: Dict) -> Dict:
        """
        Process natural language command and execute appropriate action.

        Args:
            user_input: Natural language command
            user_context: User context (role, permissions, facility, etc.)

        Returns:
            Dict with execution result and response
        """
        # Classify intent using LLM
        intent = await self._classify_intent(user_input)

        # Extract entities
        entities = await self._extract_entities(user_input, intent)

        # Validate permissions
        if not self._check_permissions(intent, user_context):
            return {
                "success": False,
                "error": "Insufficient permissions",
                "response": "You don't have permission to perform this action."
            }

        # Execute action based on intent
        result = await self._execute_action(intent, entities, user_context)

        # Generate natural language response
        response = await self._generate_response(intent, entities, result)

        return {
            "success": result.get("success", False),
            "intent": intent,
            "entities": entities,
            "result": result,
            "response": response
        }

    async def _classify_intent(self, user_input: str) -> str:
        """
        Classify user intent using LLM.

        Possible intents:
        - schedule_appointment
        - cancel_appointment
        - check_insurance
        - submit_claim
        - check_claim_status
        - send_reminders
        - view_analytics
        - create_hep
        - query_data
        """
        prompt = f"""
Classify the user's intent from the following command:

Command: "{user_input}"

Possible intents:
- schedule_appointment: User wants to schedule an appointment
- cancel_appointment: User wants to cancel an appointment
- reschedule_appointment: User wants to reschedule an appointment
- check_insurance: User wants to verify insurance
- submit_claim: User wants to submit a claim
- check_claim_status: User wants to check claim status
- send_reminders: User wants to send appointment reminders
- view_analytics: User wants to see metrics/analytics
- create_hep: User wants to create a home exercise program
- query_data: User wants to query/search data
- assign_therapist: User wants to assign a therapist
- create_note: User wants to create/edit a SOAP note

Respond with ONLY the intent name, nothing else.
"""

        # TODO: Call LLM endpoint
        # For now, use simple keyword matching
        user_lower = user_input.lower()

        if any(word in user_lower for word in ["schedule", "book", "appointment for"]):
            return "schedule_appointment"
        elif "cancel" in user_lower:
            return "cancel_appointment"
        elif "insurance" in user_lower or "verify" in user_lower:
            return "check_insurance"
        elif "claim" in user_lower and ("submit" in user_lower or "create" in user_lower):
            return "submit_claim"
        elif "claim" in user_lower and "status" in user_lower:
            return "check_claim_status"
        elif "reminder" in user_lower or "remind" in user_lower:
            return "send_reminders"
        elif any(word in user_lower for word in ["analytics", "metrics", "show me", "what's the"]):
            return "view_analytics"
        elif "hep" in user_lower or "exercise program" in user_lower:
            return "create_hep"
        else:
            return "query_data"

    async def _extract_entities(self, user_input: str, intent: str) -> Dict:
        """
        Extract entities from user input using LLM.

        Entities might include:
        - patient_name
        - date/time
        - therapist_name
        - claim_number
        - time_period
        - metric_type
        """
        prompt = f"""
Extract entities from this command:

Command: "{user_input}"
Intent: {intent}

Extract the following entities if present:
- patient_name: Full name of patient
- date: Date mentioned (format: YYYY-MM-DD)
- time: Time mentioned (format: HH:MM)
- therapist_name: Name of therapist
- claim_number: Claim or appointment number
- time_period: Time period (e.g., "last month", "this week", "yesterday")
- metric_type: Type of metric (e.g., "no-show rate", "revenue", "utilization")

Respond in JSON format with extracted entities. If an entity is not present, omit it.
"""

        # TODO: Call LLM endpoint
        # For now, use simple extraction
        entities = {}

        # Extract dates
        if "tomorrow" in user_input.lower():
            entities["date"] = (date.today() + timedelta(days=1)).isoformat()
        elif "next tuesday" in user_input.lower():
            # Calculate next Tuesday
            today = date.today()
            days_ahead = (1 - today.weekday()) % 7  # 1 = Tuesday
            if days_ahead == 0:
                days_ahead = 7
            entities["date"] = (today + timedelta(days=days_ahead)).isoformat()

        # Extract time
        import re
        time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)?'
        time_match = re.search(time_pattern, user_input.lower())
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)

            if period == "pm" and hour < 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            entities["time"] = f"{hour:02d}:{minute:02d}"

        # Extract patient name (simplified - would use NER in production)
        # Look for patterns like "for John Doe" or "John Doe for"
        name_pattern = r'(?:for|patient)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        name_match = re.search(name_pattern, user_input)
        if name_match:
            entities["patient_name"] = name_match.group(1)

        return entities

    def _check_permissions(self, intent: str, user_context: Dict) -> bool:
        """Check if user has permission to perform intent."""
        user_role = user_context.get("role", "user")

        # Admin can do everything
        if user_role == "admin":
            return True

        # Therapist permissions
        if user_role == "therapist":
            allowed_intents = [
                "schedule_appointment",
                "cancel_appointment",
                "reschedule_appointment",
                "create_hep",
                "create_note",
                "view_analytics",
                "query_data"
            ]
            return intent in allowed_intents

        # Billing staff permissions
        if user_role == "billing":
            allowed_intents = [
                "check_insurance",
                "submit_claim",
                "check_claim_status",
                "view_analytics",
                "query_data"
            ]
            return intent in allowed_intents

        # Front desk permissions
        if user_role == "front_desk":
            allowed_intents = [
                "schedule_appointment",
                "cancel_appointment",
                "reschedule_appointment",
                "send_reminders",
                "check_insurance"
            ]
            return intent in allowed_intents

        return False

    async def _execute_action(
        self,
        intent: str,
        entities: Dict,
        user_context: Dict
    ) -> Dict:
        """Execute the appropriate action based on intent and entities."""
        try:
            if intent == "schedule_appointment":
                return await self._execute_schedule_appointment(entities, user_context)
            elif intent == "check_insurance":
                return await self._execute_check_insurance(entities)
            elif intent == "submit_claim":
                return await self._execute_submit_claim(entities)
            elif intent == "check_claim_status":
                return await self._execute_check_claim_status(entities)
            elif intent == "send_reminders":
                return await self._execute_send_reminders(entities)
            elif intent == "view_analytics":
                return await self._execute_view_analytics(entities, user_context)
            elif intent == "create_hep":
                return await self._execute_create_hep(entities)
            else:
                return {"success": False, "error": "Intent not implemented"}

        except Exception as e:
            logger.error(f"Error executing action {intent}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _execute_schedule_appointment(
        self,
        entities: Dict,
        user_context: Dict
    ) -> Dict:
        """Execute appointment scheduling."""
        # TODO: Integrate with scheduling API
        logger.info(f"Scheduling appointment with entities: {entities}")

        return {
            "success": True,
            "appointment_id": 12345,
            "patient_name": entities.get("patient_name"),
            "scheduled_date": entities.get("date"),
            "scheduled_time": entities.get("time")
        }

    async def _execute_check_insurance(self, entities: Dict) -> Dict:
        """Execute insurance verification."""
        # TODO: Integrate with insurance engine
        logger.info(f"Checking insurance with entities: {entities}")

        return {
            "success": True,
            "verification_status": "verified",
            "copay_amount": 25.00,
            "visits_authorized": 20
        }

    async def _execute_submit_claim(self, entities: Dict) -> Dict:
        """Execute claim submission."""
        # TODO: Integrate with claims engine
        logger.info(f"Submitting claim with entities: {entities}")

        return {
            "success": True,
            "claim_number": "CLM20251110123456",
            "status": "submitted"
        }

    async def _execute_check_claim_status(self, entities: Dict) -> Dict:
        """Execute claim status check."""
        # TODO: Integrate with claims engine
        logger.info(f"Checking claim status with entities: {entities}")

        return {
            "success": True,
            "claim_number": entities.get("claim_number"),
            "status": "approved",
            "paid_amount": 150.00
        }

    async def _execute_send_reminders(self, entities: Dict) -> Dict:
        """Execute reminder sending."""
        # TODO: Integrate with reminder service
        logger.info(f"Sending reminders with entities: {entities}")

        return {
            "success": True,
            "reminders_sent": 15,
            "date": entities.get("date")
        }

    async def _execute_view_analytics(
        self,
        entities: Dict,
        user_context: Dict
    ) -> Dict:
        """Execute analytics query."""
        # TODO: Integrate with analytics engine
        logger.info(f"Viewing analytics with entities: {entities}")

        return {
            "success": True,
            "metric_type": entities.get("metric_type"),
            "value": 12.5,
            "time_period": entities.get("time_period")
        }

    async def _execute_create_hep(self, entities: Dict) -> Dict:
        """Execute HEP creation."""
        # TODO: Integrate with HEP management
        logger.info(f"Creating HEP with entities: {entities}")

        return {
            "success": True,
            "hep_id": 789,
            "patient_name": entities.get("patient_name"),
            "exercises_count": 5
        }

    async def _generate_response(
        self,
        intent: str,
        entities: Dict,
        result: Dict
    ) -> str:
        """Generate natural language response based on execution result."""
        if not result.get("success"):
            return f"I'm sorry, I couldn't complete that action. {result.get('error', '')}"

        # Generate response based on intent
        if intent == "schedule_appointment":
            return f"I've scheduled an appointment for {result['patient_name']} on {result['scheduled_date']} at {result['scheduled_time']}. The appointment ID is {result['appointment_id']}."

        elif intent == "check_insurance":
            return f"Insurance verification complete. Status: {result['verification_status']}. Copay: ${result['copay_amount']}. Visits authorized: {result['visits_authorized']}."

        elif intent == "submit_claim":
            return f"Claim {result['claim_number']} has been submitted successfully. Current status: {result['status']}."

        elif intent == "check_claim_status":
            return f"Claim {result['claim_number']} status: {result['status']}. Paid amount: ${result['paid_amount']}."

        elif intent == "send_reminders":
            return f"Successfully sent {result['reminders_sent']} appointment reminders for {result['date']}."

        elif intent == "view_analytics":
            return f"The {result['metric_type']} for {result['time_period']} is {result['value']}."

        elif intent == "create_hep":
            return f"I've created a home exercise program for {result['patient_name']} with {result['exercises_count']} exercises. HEP ID: {result['hep_id']}."

        else:
            return "Action completed successfully."
