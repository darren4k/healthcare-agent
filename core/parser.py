"""LLM-powered SOAP note structuring engine."""
import json
import httpx
import logging
from typing import Dict, Optional
from core.config import settings
from core.schema import SOAPComponents

logger = logging.getLogger(__name__)


class SOAPParser:
    """Converts raw clinical notes into structured SOAP format using LLM."""

    def __init__(self, llm_endpoint: Optional[str] = None):
        """
        Initialize SOAP parser.

        Args:
            llm_endpoint: Override default LLM endpoint from settings
        """
        self.llm_endpoint = llm_endpoint or settings.LLM_ENDPOINT
        self.timeout = settings.LLM_TIMEOUT
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    def _build_prompt(self, raw_text: str, visit_type: str, patient_context: Optional[str] = None) -> str:
        """
        Build the prompt for LLM to structure clinical notes.

        Args:
            raw_text: Raw clinical note text
            visit_type: Type of visit (PT, OT, etc.)
            patient_context: Optional patient history/context

        Returns:
            Formatted prompt string
        """
        context_section = f"\n\nPatient Context:\n{patient_context}" if patient_context else ""

        prompt = f"""You are a clinical documentation AI assistant. Convert the following raw clinical note into a properly structured SOAP (Subjective, Objective, Assessment, Plan) format.

Visit Type: {visit_type}
{context_section}

Raw Clinical Note:
{raw_text}

Instructions:
1. Extract and organize information into SOAP format
2. Subjective: Patient's reported symptoms, complaints, and feelings
3. Objective: Measurable observations, tests, vitals, therapist observations
4. Assessment: Clinical interpretation and progress evaluation
5. Plan: Treatment plan, interventions, goals, and next steps
6. Use professional medical terminology
7. Be concise but comprehensive
8. If information is missing for a section, write "Not documented" rather than leaving blank
9. Rate your confidence in this structuring from 0-100

Respond ONLY with valid JSON in this exact format:
{{
  "subjective": "string",
  "objective": "string",
  "assessment": "string",
  "plan": "string",
  "confidence_score": integer
}}

JSON Response:"""

        return prompt

    async def parse_to_soap(
        self,
        raw_text: str,
        visit_type: str = "PT",
        patient_context: Optional[str] = None
    ) -> SOAPComponents:
        """
        Parse raw clinical text into structured SOAP components.

        Args:
            raw_text: Raw clinical note text
            visit_type: Type of visit (default: PT)
            patient_context: Optional patient history

        Returns:
            SOAPComponents with structured note

        Raises:
            ValueError: If LLM response cannot be parsed
            httpx.HTTPError: If LLM endpoint fails
        """
        prompt = self._build_prompt(raw_text, visit_type, patient_context)

        try:
            # Call DGX LLM endpoint
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.llm_endpoint,
                    json={
                        "prompt": prompt,
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                        "stop": ["```", "---"]
                    }
                )
                response.raise_for_status()

                llm_output = response.json()
                logger.info(f"LLM raw response: {llm_output}")

                # Extract text from response (adjust based on your LLM server format)
                # Common formats: {"text": "..."} or {"choices": [{"text": "..."}]}
                if "text" in llm_output:
                    generated_text = llm_output["text"]
                elif "choices" in llm_output and len(llm_output["choices"]) > 0:
                    generated_text = llm_output["choices"][0].get("text", "")
                else:
                    raise ValueError(f"Unexpected LLM response format: {llm_output}")

                # Parse JSON from generated text
                soap_data = self._extract_json(generated_text)

                # Validate and create SOAPComponents
                return SOAPComponents(**soap_data)

        except httpx.HTTPError as e:
            logger.error(f"LLM endpoint error: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            raise ValueError(f"Invalid JSON from LLM: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in SOAP parsing: {e}")
            raise

    def _extract_json(self, text: str) -> Dict:
        """
        Extract JSON object from LLM response text.

        Args:
            text: LLM generated text that may contain JSON

        Returns:
            Parsed JSON as dictionary

        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        # Try to find JSON block in the text
        text = text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Find first { and last }
        start_idx = text.find("{")
        end_idx = text.rfind("}")

        if start_idx == -1 or end_idx == -1:
            raise json.JSONDecodeError(f"No JSON object found in text", text, 0)

        json_str = text[start_idx:end_idx + 1]
        return json.loads(json_str)

    def parse_to_soap_sync(
        self,
        raw_text: str,
        visit_type: str = "PT",
        patient_context: Optional[str] = None
    ) -> SOAPComponents:
        """
        Synchronous version of parse_to_soap for non-async contexts.

        Args:
            raw_text: Raw clinical note text
            visit_type: Type of visit
            patient_context: Optional patient history

        Returns:
            SOAPComponents with structured note
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.parse_to_soap(raw_text, visit_type, patient_context)
        )


# Global parser instance
soap_parser = SOAPParser()
