"""Reviewer agent for validating execution results and ensuring quality."""
import logging
from typing import Dict, List, Optional
import asyncio

import httpx

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """Agent that reviews execution results and validates SOAP note submissions."""

    def __init__(self, llm_endpoint: str = None):
        """Initialize reviewer agent."""
        import os
        self.llm_endpoint = llm_endpoint or os.getenv("LLM_ENDPOINT", "http://localhost:8000/infer")
        self.timeout = httpx.Timeout(30.0)

    async def review_execution(
        self,
        execution_results: Dict,
        original_soap: Dict,
        screenshots: List[str]
    ) -> Dict:
        """
        Review execution results to determine if task was truly successful.

        Args:
            execution_results: Results from ExecutorAgent
            original_soap: Original SOAP note data
            screenshots: Paths to screenshots taken during execution

        Returns:
            Review results with confidence score and recommendations
        """
        logger.info(f"Reviewing execution for task {execution_results['task_id']}")

        review = {
            "task_id": execution_results["task_id"],
            "success": execution_results["success"],
            "confidence": 0,
            "issues": [],
            "recommendations": [],
            "requires_human_review": False
        }

        # Basic checks
        if not execution_results["success"]:
            review["confidence"] = 0
            review["issues"].append("Execution failed before completion")
            review["requires_human_review"] = True
            return review

        # Check if all critical steps completed
        critical_steps = ["login", "navigate", "fill", "submit"]
        completed_actions = [
            step["action"]
            for step in execution_results["step_results"]
            if step["status"] == "success"
        ]

        missing_critical = [s for s in critical_steps if s not in completed_actions]
        if missing_critical:
            review["issues"].append(f"Missing critical steps: {missing_critical}")
            review["confidence"] = 30
            review["requires_human_review"] = True
            return review

        # Analyze screenshots to verify success
        if screenshots:
            screenshot_analysis = await self._analyze_screenshots(screenshots)
            review["screenshot_analysis"] = screenshot_analysis

            if "error" in screenshot_analysis.get("indicators", []):
                review["issues"].append("Error indicators found in screenshots")
                review["confidence"] = 40
                review["requires_human_review"] = True
                return review

            if "success" in screenshot_analysis.get("indicators", []):
                review["confidence"] = min(review["confidence"] + 30, 100)
                logger.info("Success indicators found in screenshots")

        # Verify SOAP data completeness
        completeness_score = self._check_soap_completeness(original_soap)
        review["soap_completeness"] = completeness_score

        if completeness_score < 70:
            review["issues"].append(f"SOAP note incomplete ({completeness_score}% complete)")
            review["recommendations"].append("Review and complete missing sections")
            review["requires_human_review"] = True

        # Calculate overall confidence
        base_confidence = 70  # Starting point for successful execution

        # Adjust based on completeness
        base_confidence += (completeness_score - 70) * 0.3

        # Adjust based on step efficiency
        if execution_results["steps_failed"] == 0:
            base_confidence += 10

        review["confidence"] = min(max(int(base_confidence), 0), 100)

        # Determine if human review needed
        if review["confidence"] < 60:
            review["requires_human_review"] = True
            review["recommendations"].append("Low confidence - recommend human verification")

        if len(review["issues"]) > 2:
            review["requires_human_review"] = True

        logger.info(f"Review complete: confidence={review['confidence']}%, human_review={review['requires_human_review']}")
        return review

    async def _analyze_screenshots(self, screenshot_paths: List[str]) -> Dict:
        """
        Analyze screenshots to identify success/error indicators.

        Args:
            screenshot_paths: Paths to screenshot files

        Returns:
            Analysis results
        """
        # For now, return simple heuristic analysis
        # TODO: Integrate vision LLM for actual screenshot analysis

        analysis = {
            "total_screenshots": len(screenshot_paths),
            "indicators": [],
            "observations": []
        }

        # Check filenames for error indicators
        for path in screenshot_paths:
            if "error" in path.lower():
                analysis["indicators"].append("error")
                analysis["observations"].append(f"Error screenshot detected: {path}")
            elif "success" in path.lower() or "submitted" in path.lower():
                analysis["indicators"].append("success")
                analysis["observations"].append(f"Success screenshot detected: {path}")

        return analysis

    def _check_soap_completeness(self, soap_data: Dict) -> int:
        """
        Check completeness of SOAP note.

        Args:
            soap_data: SOAP note data

        Returns:
            Completeness score (0-100)
        """
        required_sections = ["subjective", "objective", "assessment", "plan"]
        scores = []

        for section in required_sections:
            content = soap_data.get(section, "")

            if not content or len(content.strip()) < 10:
                scores.append(0)
            elif len(content.strip()) < 50:
                scores.append(50)
            elif len(content.strip()) < 100:
                scores.append(75)
            else:
                scores.append(100)

        return int(sum(scores) / len(scores))

    async def suggest_improvements(
        self,
        review: Dict,
        execution_results: Dict
    ) -> List[str]:
        """
        Suggest improvements based on review.

        Args:
            review: Review results
            execution_results: Execution results

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Analyze failure patterns
        if execution_results["steps_failed"] > 0:
            failed_steps = [
                step for step in execution_results["step_results"]
                if step["status"] == "failed"
            ]

            for step in failed_steps:
                error = step.get("error", "")

                if "timeout" in error.lower():
                    suggestions.append(f"Increase timeout for step {step['step_number']}: {step['action']}")

                if "selector" in error.lower() or "element" in error.lower():
                    suggestions.append(f"Update selector for step {step['step_number']}: {step['action']}")

                if "navigation" in error.lower():
                    suggestions.append(f"Add pre-navigation wait for step {step['step_number']}")

        # Review-based suggestions
        if review["confidence"] < 60:
            suggestions.append("Consider using alternative automation strategy")

        if review.get("soap_completeness", 100) < 80:
            suggestions.append("Improve SOAP note completeness before submission")

        if len(review.get("issues", [])) > 0:
            suggestions.append("Address identified issues before retry")

        return suggestions

    async def validate_submission(
        self,
        emr_draft_url: str,
        expected_data: Dict
    ) -> Dict:
        """
        Validate that submission was successful by checking EMR.

        Args:
            emr_draft_url: URL of submitted draft in EMR
            expected_data: Expected SOAP data

        Returns:
            Validation results
        """
        validation = {
            "url_valid": bool(emr_draft_url),
            "url": emr_draft_url,
            "accessible": False,
            "data_matches": False,
            "confidence": 0
        }

        if not emr_draft_url:
            return validation

        # Check if URL is accessible (basic check)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(emr_draft_url)
                validation["accessible"] = response.status_code == 200
                validation["confidence"] = 70 if validation["accessible"] else 20
        except Exception as e:
            logger.warning(f"Failed to validate EMR URL: {e}")
            validation["confidence"] = 30

        return validation
