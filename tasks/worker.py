"""Celery worker tasks for browser automation and background processing."""
import asyncio
import logging
from datetime import datetime
from typing import Dict

from tasks.celery_app import celery_app
from browser_agent.playwright_runner import run_browser_automation
from database.session import SessionLocal
from database.models import NoteDraft, TaskStatus

logger = logging.getLogger(__name__)


@celery_app.task(name='tasks.worker.submit_note_to_emr', bind=True, max_retries=3)
def submit_note_to_emr(self, task_id: int, headless: bool = True) -> Dict:
    """
    Submit SOAP note to EMR using browser automation.

    Args:
        task_id: Note draft ID
        headless: Run browser in headless mode

    Returns:
        dict with result
    """
    logger.info(f"Starting browser automation for task {task_id}")

    try:
        # Run async browser automation
        result = asyncio.run(run_browser_automation(task_id, headless=headless))

        if result['success']:
            logger.info(f"Task {task_id} completed successfully")
        else:
            logger.error(f"Task {task_id} failed: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Unexpected error in task {task_id}: {e}", exc_info=True)

        # Update database on unexpected failure
        db = SessionLocal()
        try:
            note_draft = db.query(NoteDraft).filter(NoteDraft.id == task_id).first()
            if note_draft:
                note_draft.status = TaskStatus.FAILED
                note_draft.error_message = f"Celery task error: {str(e)}"
                db.commit()
        finally:
            db.close()

        # Retry task
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds


@celery_app.task(name='tasks.worker.check_and_notify')
def check_and_notify(task_id: int):
    """
    Check task status and send notifications.

    Args:
        task_id: Note draft ID
    """
    db = SessionLocal()

    try:
        note_draft = db.query(NoteDraft).filter(NoteDraft.id == task_id).first()

        if not note_draft:
            logger.warning(f"Task {task_id} not found")
            return

        if note_draft.status == TaskStatus.COMPLETED:
            # TODO: Send notification (email/Slack)
            logger.info(f"Task {task_id} completed. Notification would be sent here.")
        elif note_draft.status == TaskStatus.FAILED:
            # TODO: Send failure notification
            logger.warning(f"Task {task_id} failed. Failure notification would be sent here.")

    finally:
        db.close()


@celery_app.task(name='tasks.worker.process_email_batch')
def process_email_batch():
    """
    Process batch of emails from inbox.
    This would be triggered periodically.
    """
    logger.info("Processing email batch")
    # TODO: Implement email batch processing
    pass


@celery_app.task(name='tasks.worker.cleanup_old_screenshots')
def cleanup_old_screenshots(days: int = 30):
    """
    Clean up screenshots older than specified days.

    Args:
        days: Delete screenshots older than this many days
    """
    from pathlib import Path
    from datetime import timedelta

    screenshots_dir = Path("data/logs/screenshots")
    cutoff_date = datetime.now() - timedelta(days=days)

    deleted_count = 0
    for screenshot_path in screenshots_dir.glob("*.png"):
        if screenshot_path.stat().st_mtime < cutoff_date.timestamp():
            screenshot_path.unlink()
            deleted_count += 1

    logger.info(f"Deleted {deleted_count} old screenshots")
    return deleted_count
