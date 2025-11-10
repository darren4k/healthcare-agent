"""Agent coordinator for orchestrating multi-agent workflows."""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent
from agents.reviewer import ReviewerAgent
from browser_agent.error_recovery import error_recovery
from database.session import SessionLocal
from database.models import NoteDraft, TaskLog, TaskStatus

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """Coordinates multi-agent workflows for browser automation."""

    def __init__(
        self,
        llm_endpoint: str = None,
        max_retries: int = 3,
        screenshots_dir: Path = None
    ):
        """
        Initialize agent coordinator.

        Args:
            llm_endpoint: LLM endpoint for planning and review
            max_retries: Maximum retry attempts
            screenshots_dir: Directory for screenshots
        """
        self.planner = PlannerAgent(llm_endpoint)
        self.reviewer = ReviewerAgent(llm_endpoint)
        self.max_retries = max_retries
        self.screenshots_dir = screenshots_dir or Path("data/logs/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    async def execute_task(
        self,
        task_id: int,
        emr_type: str = "mock_emr",
        headless: bool = True
    ) -> Dict:
        """
        Execute complete browser automation task with agentic intelligence.

        Args:
            task_id: Note draft task ID
            emr_type: EMR system type
            headless: Run browser in headless mode

        Returns:
            Task execution results
        """
        logger.info(f"Starting agentic execution for task {task_id}")

        db = SessionLocal()
        playwright = None
        browser = None

        try:
            # Fetch task from database
            note_draft = db.query(NoteDraft).filter(NoteDraft.id == task_id).first()
            if not note_draft:
                raise ValueError(f"Task {task_id} not found")

            # Update status
            note_draft.status = TaskStatus.BROWSER_RUNNING
            db.commit()

            # Load selectors
            import json
            selectors_path = Path(__file__).parent.parent / "browser_agent" / "selectors.json"
            with open(selectors_path, 'r') as f:
                all_selectors = json.load(f)
            selectors = all_selectors.get(emr_type, {})

            # Prepare data
            patient_data = {
                "patient_id": note_draft.patient.patient_id,
                "name": f"{note_draft.patient.first_name} {note_draft.patient.last_name}"
            }

            soap_data = {
                "subjective": note_draft.subjective,
                "objective": note_draft.objective,
                "assessment": note_draft.assessment,
                "plan": note_draft.plan,
                "visit_date": note_draft.visit_date.strftime("%Y-%m-%d"),
                "visit_type": note_draft.visit_type
            }

            # Start browser
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page()

            # Main execution loop with adaptive planning
            attempt = 0
            success = False
            execution_results = None
            current_plan = None
            all_screenshots = []

            while attempt < self.max_retries and not success:
                attempt += 1
                logger.info(f"Attempt {attempt}/{self.max_retries}")

                # Step 1: Plan (or replan if retry)
                context = None
                if attempt > 1 and execution_results:
                    context = {
                        "error": execution_results.get("error"),
                        "attempt_number": attempt,
                        "previous_results": execution_results
                    }

                current_plan = await self.planner.create_plan(
                    task_description=f"Submit SOAP note to {emr_type} EMR",
                    emr_type=emr_type,
                    patient_data=patient_data,
                    soap_data=soap_data,
                    context=context
                )

                logger.info(f"Plan created with confidence {current_plan['confidence']}%")

                # Step 2: Execute
                executor = ExecutorAgent(page, self.screenshots_dir)
                execution_results = await executor.execute_plan(
                    current_plan,
                    task_id,
                    selectors
                )

                # Collect screenshots
                for step_result in execution_results["step_results"]:
                    if "screenshot" in step_result:
                        all_screenshots.append(step_result["screenshot"])
                    if "error_screenshot" in step_result:
                        all_screenshots.append(step_result["error_screenshot"])

                # Step 3: Review
                review = await self.reviewer.review_execution(
                    execution_results,
                    soap_data,
                    all_screenshots
                )

                logger.info(f"Review confidence: {review['confidence']}%")

                # Check if successful
                if execution_results["success"] and review["confidence"] >= 60:
                    success = True
                    logger.info("Task completed successfully!")

                    # Validate submission
                    emr_draft_url = page.url
                    validation = await self.reviewer.validate_submission(
                        emr_draft_url,
                        soap_data
                    )

                    # Update database
                    note_draft.status = TaskStatus.COMPLETED
                    note_draft.emr_draft_url = emr_draft_url
                    note_draft.emr_submitted_at = datetime.utcnow()
                    note_draft.confidence_score = review["confidence"]
                    db.commit()

                    # Create success log
                    task_log = TaskLog(
                        note_draft_id=task_id,
                        task_name="agentic_browser_automation",
                        status=TaskStatus.COMPLETED,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        output_data={
                            "plan": current_plan,
                            "execution": execution_results,
                            "review": review,
                            "validation": validation,
                            "attempts": attempt,
                            "screenshots": all_screenshots
                        }
                    )
                    db.add(task_log)
                    db.commit()

                    return {
                        "success": True,
                        "task_id": task_id,
                        "emr_url": emr_draft_url,
                        "confidence": review["confidence"],
                        "attempts": attempt,
                        "requires_human_review": review["requires_human_review"]
                    }

                else:
                    # Failure - get suggestions for next attempt
                    if attempt < self.max_retries:
                        suggestions = await self.reviewer.suggest_improvements(
                            review,
                            execution_results
                        )
                        logger.warning(f"Attempt {attempt} failed. Suggestions: {suggestions}")

                        # Use error recovery if available
                        if execution_results.get("error"):
                            last_error = executor.get_last_error()
                            if last_error and "error_screenshot" in last_error:
                                error_screenshot = Path(last_error["error_screenshot"])
                                should_retry, reason, recovery_data = await error_recovery.handle_error(
                                    error=Exception(last_error["error"]),
                                    page=page,
                                    current_step=last_error["action"],
                                    attempt_number=attempt,
                                    screenshots_dir=self.screenshots_dir,
                                    task_id=task_id
                                )

                                if not should_retry:
                                    logger.error(f"Error recovery suggests stopping: {reason}")
                                    break

                                # Apply recovery data to next plan
                                if recovery_data:
                                    logger.info(f"Applying recovery data: {recovery_data}")

                        # Adapt plan for next attempt
                        current_plan = await self.planner.adapt_plan(
                            current_plan,
                            execution_results["step_results"]
                        )

                        # Wait before retry
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"Max retries ({self.max_retries}) exceeded")

            # If we get here, task failed
            note_draft.status = TaskStatus.FAILED
            note_draft.error_message = f"Failed after {attempt} attempts. Last error: {execution_results.get('error')}"
            note_draft.confidence_score = review.get("confidence", 0) if 'review' in locals() else 0
            db.commit()

            # Create failure log
            task_log = TaskLog(
                note_draft_id=task_id,
                task_name="agentic_browser_automation",
                status=TaskStatus.FAILED,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                error_message=note_draft.error_message,
                output_data={
                    "plan": current_plan,
                    "execution": execution_results,
                    "attempts": attempt,
                    "screenshots": all_screenshots
                }
            )
            db.add(task_log)
            db.commit()

            return {
                "success": False,
                "task_id": task_id,
                "error": note_draft.error_message,
                "attempts": attempt,
                "screenshots": all_screenshots
            }

        except Exception as e:
            logger.error(f"Agent coordinator error: {e}", exc_info=True)

            # Update database on error
            if note_draft:
                note_draft.status = TaskStatus.FAILED
                note_draft.error_message = f"Coordinator error: {str(e)}"
                db.commit()

            return {
                "success": False,
                "task_id": task_id,
                "error": str(e)
            }

        finally:
            # Cleanup
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            db.close()

    async def execute_batch(
        self,
        task_ids: list[int],
        emr_type: str = "mock_emr"
    ) -> Dict:
        """
        Execute multiple tasks in batch.

        Args:
            task_ids: List of task IDs to process
            emr_type: EMR system type

        Returns:
            Batch execution results
        """
        logger.info(f"Starting batch execution for {len(task_ids)} tasks")

        results = {
            "total": len(task_ids),
            "successful": 0,
            "failed": 0,
            "task_results": []
        }

        for task_id in task_ids:
            try:
                result = await self.execute_task(task_id, emr_type)
                results["task_results"].append(result)

                if result["success"]:
                    results["successful"] += 1
                else:
                    results["failed"] += 1

                logger.info(f"Task {task_id}: {'SUCCESS' if result['success'] else 'FAILED'}")

            except Exception as e:
                logger.error(f"Batch task {task_id} error: {e}")
                results["failed"] += 1
                results["task_results"].append({
                    "success": False,
                    "task_id": task_id,
                    "error": str(e)
                })

        logger.info(f"Batch complete: {results['successful']}/{results['total']} successful")
        return results
