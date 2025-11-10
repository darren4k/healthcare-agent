"""Planner agent for creating browser automation strategies."""
import asyncio
import json
import logging
from typing import Dict, List, Optional
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of browser actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    VERIFY = "verify"


class PlannerAgent:
    """Agent that creates execution plans for browser automation tasks."""

    def __init__(self, llm_endpoint: str = None):
        """Initialize planner agent."""
        import os
        self.llm_endpoint = llm_endpoint or os.getenv("LLM_ENDPOINT", "http://localhost:8000/infer")
        self.timeout = httpx.Timeout(30.0)

    async def create_plan(
        self,
        task_description: str,
        emr_type: str,
        patient_data: Dict,
        soap_data: Dict,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Create a detailed execution plan for browser automation.

        Args:
            task_description: High-level task description
            emr_type: EMR system type
            patient_data: Patient information
            soap_data: SOAP note data
            context: Additional context (screenshots, errors, etc.)

        Returns:
            Execution plan with steps and fallback strategies
        """
        logger.info(f"Creating execution plan for {emr_type}")

        try:
            # Build planning prompt
            prompt = self._build_planning_prompt(
                task_description,
                emr_type,
                patient_data,
                soap_data,
                context
            )

            # Call LLM for plan generation
            plan = await self._generate_plan_with_llm(prompt)

            # Validate and structure plan
            structured_plan = self._structure_plan(plan)

            logger.info(f"Created plan with {len(structured_plan['steps'])} steps")
            return structured_plan

        except Exception as e:
            logger.error(f"Failed to create plan: {e}", exc_info=True)
            # Return fallback plan
            return self._create_fallback_plan(emr_type, patient_data, soap_data)

    def _build_planning_prompt(
        self,
        task_description: str,
        emr_type: str,
        patient_data: Dict,
        soap_data: Dict,
        context: Optional[Dict]
    ) -> str:
        """Build prompt for LLM-based planning."""
        context_info = ""
        if context:
            if "error" in context:
                context_info += f"\nPrevious Error: {context['error']}"
            if "screenshot_analysis" in context:
                context_info += f"\nScreenshot Analysis: {context['screenshot_analysis']}"
            if "attempt_number" in context:
                context_info += f"\nAttempt Number: {context['attempt_number']}"

        prompt = f"""You are an expert browser automation planner for healthcare EMR systems.

**Task:** {task_description}
**EMR System:** {emr_type}
**Patient:** {patient_data.get('patient_id', 'Unknown')} - {patient_data.get('name', 'Unknown')}
{context_info}

**SOAP Note to Submit:**
- Subjective: {soap_data.get('subjective', '')[:200]}...
- Objective: {soap_data.get('objective', '')[:200]}...
- Assessment: {soap_data.get('assessment', '')[:200]}...
- Plan: {soap_data.get('plan', '')[:200]}...

**Your Task:**
Create a detailed step-by-step execution plan for browser automation. Consider:
1. Login to EMR system
2. Navigate to patient chart
3. Create new SOAP note
4. Fill all sections
5. Submit as draft
6. Verify submission

For each step, provide:
- Action type (navigate, click, fill, select, wait, screenshot, verify)
- Target selector or URL
- Data to input (if applicable)
- Success criteria
- Fallback strategies if step fails

**Output Format (JSON):**
{{
  "plan_id": "unique-plan-id",
  "confidence": 0-100,
  "total_steps": 10,
  "estimated_duration_seconds": 30,
  "steps": [
    {{
      "step_number": 1,
      "action": "navigate",
      "target": "https://emr.example.com/login",
      "description": "Navigate to login page",
      "success_criteria": "Login form visible",
      "fallback": {{
        "action": "reload",
        "reason": "Page failed to load"
      }},
      "screenshot_after": true
    }},
    {{
      "step_number": 2,
      "action": "fill",
      "target": "#username",
      "value": "{{username}}",
      "description": "Enter username",
      "success_criteria": "Username field populated",
      "fallback": {{
        "action": "try_alternative_selector",
        "alternatives": ["input[name='username']", "input[type='email']"]
      }}
    }}
  ],
  "recovery_strategies": [
    "If login fails, try alternative selectors",
    "If form not found, search for patient first",
    "If submission fails, retry after 5 seconds"
  ]
}}

Respond ONLY with valid JSON.
"""
        return prompt

    async def _generate_plan_with_llm(self, prompt: str) -> Dict:
        """Generate plan using LLM."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.llm_endpoint,
                    json={
                        "prompt": prompt,
                        "max_tokens": 2000,
                        "temperature": 0.3
                    }
                )
                response.raise_for_status()
                result = response.json()
                text = result.get("text", "")

                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found in LLM response")

        except Exception as e:
            logger.error(f"LLM plan generation failed: {e}")
            raise

    def _structure_plan(self, raw_plan: Dict) -> Dict:
        """Validate and structure the plan."""
        # Ensure required fields
        structured = {
            "plan_id": raw_plan.get("plan_id", f"plan_{asyncio.get_event_loop().time()}"),
            "confidence": min(max(raw_plan.get("confidence", 70), 0), 100),
            "total_steps": len(raw_plan.get("steps", [])),
            "estimated_duration_seconds": raw_plan.get("estimated_duration_seconds", 30),
            "steps": [],
            "recovery_strategies": raw_plan.get("recovery_strategies", [])
        }

        # Validate each step
        for step in raw_plan.get("steps", []):
            if not all(k in step for k in ["action", "description"]):
                continue

            structured["steps"].append({
                "step_number": step.get("step_number", len(structured["steps"]) + 1),
                "action": step.get("action"),
                "target": step.get("target"),
                "value": step.get("value"),
                "description": step.get("description"),
                "success_criteria": step.get("success_criteria", "Step completes without error"),
                "fallback": step.get("fallback", {"action": "retry"}),
                "screenshot_after": step.get("screenshot_after", False),
                "wait_after_ms": step.get("wait_after_ms", 1000)
            })

        return structured

    def _create_fallback_plan(
        self,
        emr_type: str,
        patient_data: Dict,
        soap_data: Dict
    ) -> Dict:
        """Create a simple fallback plan when LLM fails."""
        return {
            "plan_id": "fallback-plan",
            "confidence": 50,
            "total_steps": 8,
            "estimated_duration_seconds": 25,
            "steps": [
                {
                    "step_number": 1,
                    "action": "navigate",
                    "target": f"Login page for {emr_type}",
                    "description": "Navigate to EMR login",
                    "success_criteria": "Login form visible",
                    "fallback": {"action": "reload"}
                },
                {
                    "step_number": 2,
                    "action": "fill",
                    "target": "username_field",
                    "description": "Enter username",
                    "success_criteria": "Credentials accepted",
                    "fallback": {"action": "try_alternative_selector"}
                },
                {
                    "step_number": 3,
                    "action": "fill",
                    "target": "password_field",
                    "description": "Enter password",
                    "success_criteria": "Password entered",
                    "fallback": {"action": "retry"}
                },
                {
                    "step_number": 4,
                    "action": "click",
                    "target": "login_button",
                    "description": "Click login",
                    "success_criteria": "Logged in successfully",
                    "fallback": {"action": "check_for_errors"}
                },
                {
                    "step_number": 5,
                    "action": "navigate",
                    "target": f"Patient chart for {patient_data.get('patient_id')}",
                    "description": "Navigate to patient chart",
                    "success_criteria": "Patient chart loaded",
                    "fallback": {"action": "search_for_patient"}
                },
                {
                    "step_number": 6,
                    "action": "click",
                    "target": "new_note_button",
                    "description": "Click new note",
                    "success_criteria": "Note form displayed",
                    "fallback": {"action": "retry"}
                },
                {
                    "step_number": 7,
                    "action": "fill",
                    "target": "soap_form",
                    "description": "Fill SOAP sections",
                    "success_criteria": "All sections filled",
                    "fallback": {"action": "fill_one_by_one"}
                },
                {
                    "step_number": 8,
                    "action": "click",
                    "target": "save_draft_button",
                    "description": "Submit as draft",
                    "success_criteria": "Draft saved successfully",
                    "fallback": {"action": "retry_after_delay"}
                }
            ],
            "recovery_strategies": [
                "Use fallback selectors",
                "Retry with exponential backoff",
                "Escalate to human if all retries fail"
            ]
        }

    async def adapt_plan(
        self,
        original_plan: Dict,
        execution_results: List[Dict],
        error_context: Optional[Dict] = None
    ) -> Dict:
        """
        Adapt plan based on execution results.

        Args:
            original_plan: Original execution plan
            execution_results: Results from executing steps
            error_context: Error information if step failed

        Returns:
            Adapted plan
        """
        logger.info("Adapting plan based on execution results")

        # Find failed step
        failed_step_number = None
        for result in execution_results:
            if result.get("status") == "failed":
                failed_step_number = result.get("step_number")
                break

        if failed_step_number is None:
            # No failures, return original plan
            return original_plan

        # Get failed step
        failed_step = next(
            (s for s in original_plan["steps"] if s["step_number"] == failed_step_number),
            None
        )

        if not failed_step:
            return original_plan

        # Create adapted plan
        adapted_plan = original_plan.copy()

        # Apply fallback strategy for failed step
        fallback = failed_step.get("fallback", {})
        fallback_action = fallback.get("action", "retry")

        if fallback_action == "try_alternative_selector":
            # Update selector with alternative
            alternatives = fallback.get("alternatives", [])
            if alternatives:
                failed_step["target"] = alternatives[0]
                failed_step["fallback"]["alternatives"] = alternatives[1:]
                logger.info(f"Trying alternative selector: {alternatives[0]}")

        elif fallback_action == "reload":
            # Insert reload step before failed step
            reload_step = {
                "step_number": failed_step_number - 0.5,
                "action": "reload",
                "description": "Reload page before retry",
                "success_criteria": "Page reloaded",
                "wait_after_ms": 2000
            }
            adapted_plan["steps"].insert(failed_step_number - 1, reload_step)
            logger.info("Inserted reload step before retry")

        elif fallback_action == "navigate_back":
            # Insert navigate back step
            nav_back_step = {
                "step_number": failed_step_number - 0.5,
                "action": "navigate_back",
                "description": "Go back and retry",
                "success_criteria": "Previous page loaded",
                "wait_after_ms": 2000
            }
            adapted_plan["steps"].insert(failed_step_number - 1, nav_back_step)
            logger.info("Inserted navigate back step")

        else:
            # Default: just retry with increased wait time
            failed_step["wait_after_ms"] = failed_step.get("wait_after_ms", 1000) * 2
            logger.info(f"Increasing wait time to {failed_step['wait_after_ms']}ms")

        adapted_plan["confidence"] = max(adapted_plan["confidence"] - 10, 30)
        return adapted_plan
