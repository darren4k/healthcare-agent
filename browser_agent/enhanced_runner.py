"""Enhanced Playwright runner with video recording, slow motion, and tracing."""
import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from database.session import SessionLocal
from database.models import NoteDraft, TaskLog, TaskStatus
from backend.utils.audit import logger as audit_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SELECTORS_PATH = Path(__file__).parent / "selectors.json"
SCREENSHOTS_DIR = Path("data/logs/screenshots")
VIDEOS_DIR = Path("data/logs/videos")
TRACES_DIR = Path("data/logs/traces")

# Create directories
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
TRACES_DIR.mkdir(parents=True, exist_ok=True)


class EnhancedPlaywrightRunner:
    """Enhanced browser automation runner with visibility features."""

    def __init__(
        self,
        emr_type: str = "mock_emr",
        headless: bool = True,
        record_video: bool = False,
        slow_mo: int = 0,
        enable_tracing: bool = False
    ):
        """
        Initialize enhanced Playwright runner.

        Args:
            emr_type: EMR system type (matches key in selectors.json)
            headless: Run browser in headless mode
            record_video: Record video of automation
            slow_mo: Slow down actions by specified milliseconds (for demos)
            enable_tracing: Enable Playwright tracing for debugging
        """
        self.emr_type = emr_type
        self.headless = headless
        self.record_video = record_video
        self.slow_mo = slow_mo
        self.enable_tracing = enable_tracing
        self.selectors = self._load_selectors()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    def _load_selectors(self) -> Dict:
        """Load selectors from JSON file."""
        with open(SELECTORS_PATH, 'r') as f:
            selectors = json.load(f)

        if self.emr_type not in selectors:
            raise ValueError(f"EMR type '{self.emr_type}' not found in selectors.json")

        return selectors[self.emr_type]

    async def start_browser(self, task_id: int):
        """
        Start Playwright browser with enhanced features.

        Args:
            task_id: Task ID for video/trace naming
        """
        self.playwright = await async_playwright().start()

        # Launch browser with slow motion if enabled
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo  # Slow down actions for visibility
        )

        # Create context with video recording if enabled
        context_options = {}

        if self.record_video:
            context_options["record_video_dir"] = str(VIDEOS_DIR)
            context_options["record_video_size"] = {"width": 1280, "height": 720}

        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()

        # Start tracing if enabled
        if self.enable_tracing:
            await self.context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True
            )

        logger.info(f"Browser started (headless={self.headless}, video={self.record_video}, slow_mo={self.slow_mo}ms, tracing={self.enable_tracing})")

    async def close_browser(self, task_id: int) -> Dict[str, Optional[str]]:
        """
        Close browser and save artifacts.

        Args:
            task_id: Task ID for naming artifacts

        Returns:
            Dict with paths to video and trace files
        """
        artifacts = {
            "video_path": None,
            "trace_path": None
        }

        # Stop tracing and save
        if self.enable_tracing and self.context:
            trace_path = TRACES_DIR / f"task_{task_id}_trace.zip"
            await self.context.tracing.stop(path=str(trace_path))
            artifacts["trace_path"] = str(trace_path)
            logger.info(f"Trace saved: {trace_path}")

        # Save video
        if self.record_video and self.page:
            try:
                # Wait a bit for video to finish encoding
                await asyncio.sleep(1)

                # Get video path
                video_path = await self.page.video.path()

                # Rename to task-specific name
                final_video_path = VIDEOS_DIR / f"task_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"

                # Close page to finalize video
                await self.page.close()

                # Move video to final name
                import shutil
                shutil.move(video_path, final_video_path)

                artifacts["video_path"] = str(final_video_path)
                logger.info(f"Video saved: {final_video_path}")
            except Exception as e:
                logger.error(f"Failed to save video: {e}")

        # Close context and browser
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("Browser closed")
        return artifacts

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

    async def fill_soap_note(self, task_id: int) -> Dict:
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
                task_name="enhanced_browser_automation",
                status=TaskStatus.BROWSER_RUNNING,
                started_at=datetime.utcnow()
            )
            db.add(task_log)
            db.commit()

            # Get patient ID
            patient_id = note_draft.patient.patient_id

            # Start browser with enhanced features
            await self.start_browser(task_id)

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

            # Get success URL
            emr_draft_url = self.page.url

            # Close browser and get artifacts
            artifacts = await self.close_browser(task_id)

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
                "screenshots": [str(p) for p in screenshot_paths],
                "video_path": artifacts["video_path"],
                "trace_path": artifacts["trace_path"]
            }

            db.commit()

            audit_logger.info(
                "Browser automation completed",
                extra={
                    "task_id": task_id,
                    "patient_id": patient_id,
                    "emr_url": emr_draft_url,
                    "video_recorded": artifacts["video_path"] is not None,
                    "trace_recorded": artifacts["trace_path"] is not None
                }
            )

            return {
                "success": True,
                "task_id": task_id,
                "emr_url": emr_draft_url,
                "screenshots": [str(p) for p in screenshot_paths],
                "video_path": artifacts["video_path"],
                "trace_path": artifacts["trace_path"]
            }

        except Exception as e:
            logger.error(f"Browser automation failed: {e}", exc_info=True)

            # Close browser on error
            try:
                artifacts = await self.close_browser(task_id)
            except:
                artifacts = {"video_path": None, "trace_path": None}

            # Update database
            note_draft.status = TaskStatus.FAILED
            note_draft.error_message = str(e)

            task_log.status = TaskStatus.FAILED
            task_log.completed_at = datetime.utcnow()
            task_log.error_message = str(e)
            task_log.output_data = {
                "error": str(e),
                "screenshots": [str(p) for p in screenshot_paths],
                "video_path": artifacts["video_path"],
                "trace_path": artifacts["trace_path"]
            }

            db.commit()

            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
                "screenshots": [str(p) for p in screenshot_paths],
                "video_path": artifacts["video_path"],
                "trace_path": artifacts["trace_path"]
            }

        finally:
            db.close()
