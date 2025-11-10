"""Playwright-based browser automation for EMR integration."""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from database.session import SessionLocal
from database.models import NoteDraft, TaskLog, TaskStatus
from backend.utils.audit import logger as audit_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SELECTORS_PATH = Path(__file__).parent / "selectors.json"
SCREENSHOTS_DIR = Path("data/logs/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class PlaywrightRunner:
    """Browser automation runner for EMR systems."""

    def __init__(self, emr_type: str = "mock_emr", headless: bool = True):
        """
        Initialize Playwright runner.

        Args:
            emr_type: EMR system type (matches key in selectors.json)
            headless: Run browser in headless mode
        """
        self.emr_type = emr_type
        self.headless = headless
        self.selectors = self._load_selectors()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    def _load_selectors(self) -> Dict:
        """Load selectors from JSON file."""
        with open(SELECTORS_PATH, 'r') as f:
            selectors = json.load(f)

        if self.emr_type not in selectors:
            raise ValueError(f"EMR type '{self.emr_type}' not found in selectors.json")

        return selectors[self.emr_type]

    async def start_browser(self):
        """Start Playwright browser."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        logger.info(f"Browser started (headless={self.headless})")

    async def close_browser(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

    async def take_screenshot(self, name: str, task_id: int) -> Path:
        """
        Take a screenshot and save to logs.

        Args:
            name: Screenshot name
            task_id: Task ID for filename

        Returns:
            Path to screenshot
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_{name}_{timestamp}.png"
        screenshot_path = SCREENSHOTS_DIR / filename

        await self.page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved: {screenshot_path}")

        return screenshot_path

    async def login(self, username: str, password: str):
        """
        Login to EMR system.

        Args:
            username: EMR username
            password: EMR password
        """
        base_url = self.selectors['base_url']
        login_selectors = self.selectors['login']

        # Navigate to login page
        await self.page.goto(f"{base_url}/login")
        await self.page.wait_for_load_state('networkidle')

        # Fill login form
        await self.page.fill(login_selectors['username'], username)
        await self.page.fill(login_selectors['password'], password)

        # Submit
        await self.page.click(login_selectors['submit'])
        await self.page.wait_for_load_state('networkidle')

        logger.info(f"Logged in as {username}")

    async def navigate_to_new_note(self, patient_id: str):
        """
        Navigate to new SOAP note form for patient.

        Args:
            patient_id: Patient ID
        """
        base_url = self.selectors['base_url']
        new_note_url = self.selectors['navigation']['new_note'].format(patient_id=patient_id)

        await self.page.goto(f"{base_url}{new_note_url}")
        await self.page.wait_for_load_state('networkidle')

        logger.info(f"Navigated to new note form for patient {patient_id}")

    async def fill_soap_form(
        self,
        subjective: str,
        objective: str,
        assessment: str,
        plan: str,
        visit_date: str,
        visit_type: str
    ):
        """
        Fill SOAP note form.

        Args:
            subjective: Subjective section
            objective: Objective section
            assessment: Assessment section
            plan: Plan section
            visit_date: Visit date (YYYY-MM-DD format)
            visit_type: Visit type
        """
        soap_selectors = self.selectors['soap_form']

        # Fill form fields
        await self.page.fill(soap_selectors['visit_date'], visit_date)
        await self.page.select_option(soap_selectors['visit_type'], visit_type)
        await self.page.fill(soap_selectors['subjective'], subjective)
        await self.page.fill(soap_selectors['objective'], objective)
        await self.page.fill(soap_selectors['assessment'], assessment)
        await self.page.fill(soap_selectors['plan'], plan)

        logger.info("SOAP form filled successfully")

    async def submit_draft(self):
        """Submit SOAP note as draft."""
        soap_selectors = self.selectors['soap_form']

        await self.page.click(soap_selectors['save_draft'])
        await self.page.wait_for_load_state('networkidle')

        logger.info("SOAP note submitted as draft")

    async def fill_soap_note(self, task_id: int):
        """
        Complete workflow: Login → Navigate → Fill → Submit.

        Args:
            task_id: Note draft task ID

        Returns:
            dict with success status and details
        """
        db = SessionLocal()
        screenshot_paths = []

        try:
            # Fetch task from database
            note_draft = db.query(NoteDraft).filter(NoteDraft.id == task_id).first()

            if not note_draft:
                raise ValueError(f"Task {task_id} not found")

            # Update status to browser_running
            note_draft.status = TaskStatus.BROWSER_RUNNING
            db.commit()

            # Create task log
            task_log = TaskLog(
                note_draft_id=task_id,
                task_name="browser_automation",
                status=TaskStatus.BROWSER_RUNNING,
                started_at=datetime.utcnow()
            )
            db.add(task_log)
            db.commit()

            # Get patient ID
            patient_id = note_draft.patient.patient_id

            # Start browser
            await self.start_browser()

            # Take initial screenshot
            screenshot_paths.append(await self.take_screenshot("start", task_id))

            # Login (use mock credentials - in production, load from config)
            await self.login("demo_therapist", "demo123")
            screenshot_paths.append(await self.take_screenshot("login_success", task_id))

            # Navigate to new note form
            await self.navigate_to_new_note(patient_id)
            screenshot_paths.append(await self.take_screenshot("note_form", task_id))

            # Fill SOAP form
            await self.fill_soap_form(
                subjective=note_draft.subjective,
                objective=note_draft.objective,
                assessment=note_draft.assessment,
                plan=note_draft.plan,
                visit_date=note_draft.visit_date.strftime("%Y-%m-%d"),
                visit_type=note_draft.visit_type
            )
            screenshot_paths.append(await self.take_screenshot("form_filled", task_id))

            # Submit
            await self.submit_draft()
            screenshot_paths.append(await self.take_screenshot("submitted", task_id))

            # Get success URL (mock EMR shows success page)
            emr_draft_url = self.page.url

            # Update database
            note_draft.status = TaskStatus.COMPLETED
            note_draft.emr_draft_url = emr_draft_url
            note_draft.emr_submitted_at = datetime.utcnow()

            task_log.status = TaskStatus.COMPLETED
            task_log.completed_at = datetime.utcnow()
            task_log.duration_seconds = int(
                (task_log.completed_at - task_log.started_at).total_seconds()
            )
            task_log.output_data = {
                "emr_url": emr_draft_url,
                "screenshots": [str(p) for p in screenshot_paths]
            }

            db.commit()

            # Audit log
            audit_logger.log_info(
                event="browser_automation_success",
                patient_id=patient_id,
                metadata={
                    "task_id": task_id,
                    "emr_url": emr_draft_url,
                    "duration": task_log.duration_seconds
                }
            )

            logger.info(f"Task {task_id} completed successfully. EMR URL: {emr_draft_url}")

            return {
                "success": True,
                "task_id": task_id,
                "emr_url": emr_draft_url,
                "screenshots": [str(p) for p in screenshot_paths]
            }

        except Exception as e:
            logger.error(f"Browser automation failed for task {task_id}: {e}", exc_info=True)

            # Take error screenshot
            if self.page:
                try:
                    error_screenshot = await self.take_screenshot("error", task_id)
                    screenshot_paths.append(error_screenshot)
                except:
                    pass

            # Update database
            note_draft.status = TaskStatus.FAILED
            note_draft.error_message = str(e)

            task_log.status = TaskStatus.FAILED
            task_log.completed_at = datetime.utcnow()
            task_log.error_details = str(e)
            task_log.output_data = {
                "screenshots": [str(p) for p in screenshot_paths],
                "error": str(e)
            }

            db.commit()

            # Audit log
            audit_logger.log_error(
                event="browser_automation_failed",
                patient_id=note_draft.patient.patient_id if note_draft else "unknown",
                metadata={"task_id": task_id, "error": str(e)}
            )

            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
                "screenshots": [str(p) for p in screenshot_paths]
            }

        finally:
            # Always close browser
            await self.close_browser()
            db.close()


# Convenience function for Celery tasks
async def run_browser_automation(task_id: int, headless: bool = True) -> Dict:
    """
    Run browser automation for a task.

    Args:
        task_id: Note draft task ID
        headless: Run browser in headless mode

    Returns:
        dict with result
    """
    runner = PlaywrightRunner(emr_type="mock_emr", headless=headless)
    return await runner.fill_soap_note(task_id)


# For testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python playwright_runner.py <task_id>")
        sys.exit(1)

    task_id = int(sys.argv[1])
    result = asyncio.run(run_browser_automation(task_id, headless=False))

    print("\n" + "="*60)
    print("Browser Automation Result:")
    print("="*60)
    print(json.dumps(result, indent=2))
