"""Scheduled tasks using Celery Beat for batch operations."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import and_, func
import asyncio

from tasks.celery_app import celery_app
from database.session import SessionLocal
from database.models import NoteDraft, TaskStatus, Patient
from notifications.notifier import notification_service
from core.reminder_service import ReminderService

logger = logging.getLogger(__name__)


@celery_app.task(name='tasks.scheduled.process_nightly_batch')
def process_nightly_batch():
    """
    Process all pending notes from today in a nightly batch.
    Runs at configurable time (default: 11 PM).
    """
    logger.info("Starting nightly batch processing")
    db = SessionLocal()

    try:
        # Get today's date range
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Find all notes that completed LLM processing but haven't been submitted yet
        pending_notes = db.query(NoteDraft).filter(
            and_(
                NoteDraft.status == TaskStatus.LLM_COMPLETE,
                NoteDraft.created_at >= today_start,
                NoteDraft.created_at < today_end
            )
        ).all()

        logger.info(f"Found {len(pending_notes)} pending notes for nightly batch")

        # Queue browser automation for each
        from tasks.worker import submit_note_to_emr

        processed = 0
        for note in pending_notes:
            try:
                submit_note_to_emr.delay(note.id)
                processed += 1
                logger.info(f"Queued task {note.id} for browser automation")
            except Exception as e:
                logger.error(f"Failed to queue task {note.id}: {e}")

        logger.info(f"Successfully queued {processed}/{len(pending_notes)} notes")

        return {
            "total_found": len(pending_notes),
            "queued": processed,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Nightly batch processing failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.scheduled.send_daily_summary')
def send_daily_summary():
    """
    Send daily summary of all processed notes.
    Runs every morning at configured time (default: 8 AM).
    """
    logger.info("Generating daily summary")
    db = SessionLocal()

    try:
        # Get yesterday's date range
        yesterday_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        yesterday_end = yesterday_start + timedelta(days=1)

        # Count notes by status
        total = db.query(NoteDraft).filter(
            and_(
                NoteDraft.created_at >= yesterday_start,
                NoteDraft.created_at < yesterday_end
            )
        ).count()

        successful = db.query(NoteDraft).filter(
            and_(
                NoteDraft.created_at >= yesterday_start,
                NoteDraft.created_at < yesterday_end,
                NoteDraft.status == TaskStatus.COMPLETED
            )
        ).count()

        failed = db.query(NoteDraft).filter(
            and_(
                NoteDraft.created_at >= yesterday_start,
                NoteDraft.created_at < yesterday_end,
                NoteDraft.status == TaskStatus.FAILED
            )
        ).count()

        logger.info(f"Daily summary: {successful}/{total} successful, {failed} failed")

        # Send notification
        # TODO: Get admin email/channel from config
        admin_email = None  # Set via env var
        admin_channel = None  # Set via env var

        # Uncomment when email/Slack is configured
        # asyncio.run(notification_service.notify_batch_summary(
        #     total_processed=total,
        #     successful=successful,
        #     failed=failed,
        #     recipient_email=admin_email,
        #     slack_channel=admin_channel
        # ))

        return {
            "date": yesterday_start.date().isoformat(),
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0
        }

    except Exception as e:
        logger.error(f"Daily summary failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.scheduled.generate_weekly_patient_summary')
def generate_weekly_patient_summary():
    """
    Generate weekly progress summary for each active patient.
    Runs every Sunday at configured time (default: 6 PM).
    """
    logger.info("Generating weekly patient summaries")
    db = SessionLocal()

    try:
        # Get last week's date range
        week_end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = week_end - timedelta(days=7)

        # Get patients with notes in the last week
        active_patients = db.query(Patient).join(NoteDraft).filter(
            and_(
                NoteDraft.created_at >= week_start,
                NoteDraft.created_at < week_end
            )
        ).distinct().all()

        logger.info(f"Found {len(active_patients)} active patients in last week")

        summaries = []
        for patient in active_patients:
            # Count notes for this patient
            note_count = db.query(NoteDraft).filter(
                and_(
                    NoteDraft.patient_id == patient.id,
                    NoteDraft.created_at >= week_start,
                    NoteDraft.created_at < week_end
                )
            ).count()

            # Get most recent note
            latest_note = db.query(NoteDraft).filter(
                NoteDraft.patient_id == patient.id
            ).order_by(NoteDraft.created_at.desc()).first()

            summaries.append({
                "patient_id": patient.external_patient_id,
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "note_count": note_count,
                "latest_visit": latest_note.visit_date.isoformat() if latest_note else None,
                "latest_assessment": latest_note.assessment[:100] if latest_note and latest_note.assessment else None
            })

        logger.info(f"Generated {len(summaries)} patient summaries")

        return {
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
            "patient_count": len(summaries),
            "summaries": summaries
        }

    except Exception as e:
        logger.error(f"Weekly summary failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.scheduled.cleanup_old_data')
def cleanup_old_data(days_to_keep: int = 90):
    """
    Clean up old screenshots, logs, and optionally archive old notes.
    Runs weekly.

    Args:
        days_to_keep: Number of days to keep data
    """
    logger.info(f"Starting cleanup of data older than {days_to_keep} days")

    from pathlib import Path
    from datetime import timedelta

    cleanup_results = {
        "screenshots_deleted": 0,
        "logs_deleted": 0,
        "errors": []
    }

    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        # Clean up screenshots
        screenshots_dir = Path("data/logs/screenshots")
        if screenshots_dir.exists():
            for screenshot_path in screenshots_dir.glob("*.png"):
                try:
                    if screenshot_path.stat().st_mtime < cutoff_date.timestamp():
                        screenshot_path.unlink()
                        cleanup_results["screenshots_deleted"] += 1
                except Exception as e:
                    cleanup_results["errors"].append(f"Failed to delete {screenshot_path}: {e}")

        # Clean up old log files
        logs_dir = Path("data/logs")
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log*"):
                try:
                    if log_file.stat().st_mtime < cutoff_date.timestamp():
                        log_file.unlink()
                        cleanup_results["logs_deleted"] += 1
                except Exception as e:
                    cleanup_results["errors"].append(f"Failed to delete {log_file}: {e}")

        logger.info(f"Cleanup complete: {cleanup_results}")
        return cleanup_results

    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        cleanup_results["errors"].append(str(e))
        return cleanup_results


@celery_app.task(name='tasks.scheduled.check_stuck_tasks')
def check_stuck_tasks():
    """
    Check for tasks that have been in PROCESSING/BROWSER_RUNNING for too long.
    Marks them as failed and sends alerts.
    Runs every hour.
    """
    logger.info("Checking for stuck tasks")
    db = SessionLocal()

    try:
        # Define "stuck" as tasks running for more than 30 minutes
        stuck_threshold = datetime.utcnow() - timedelta(minutes=30)

        # Find stuck tasks
        stuck_statuses = [TaskStatus.PROCESSING, TaskStatus.BROWSER_RUNNING]
        stuck_tasks = db.query(NoteDraft).filter(
            and_(
                NoteDraft.status.in_(stuck_statuses),
                NoteDraft.updated_at < stuck_threshold
            )
        ).all()

        logger.info(f"Found {len(stuck_tasks)} stuck tasks")

        marked_failed = 0
        for task in stuck_tasks:
            try:
                task.status = TaskStatus.FAILED
                task.error_message = f"Task stuck in {task.status.value} state for >30 minutes"
                db.commit()
                marked_failed += 1

                logger.warning(f"Marked task {task.id} as failed (was stuck in {task.status.value})")

                # TODO: Send alert notification

            except Exception as e:
                logger.error(f"Failed to mark task {task.id} as failed: {e}")
                db.rollback()

        return {
            "stuck_tasks_found": len(stuck_tasks),
            "marked_failed": marked_failed,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Stuck task check failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.scheduled.retry_failed_tasks')
def retry_failed_tasks(max_age_hours: int = 24):
    """
    Automatically retry recently failed tasks that might succeed on retry.
    Excludes tasks that have been retried too many times.
    Runs every 4 hours.

    Args:
        max_age_hours: Only retry tasks that failed within this many hours
    """
    logger.info(f"Checking for failed tasks to retry (max age: {max_age_hours}h)")
    db = SessionLocal()

    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        # Find recently failed tasks
        failed_tasks = db.query(NoteDraft).filter(
            and_(
                NoteDraft.status == TaskStatus.FAILED,
                NoteDraft.updated_at >= cutoff_time,
                # Only retry if error looks recoverable
                ~NoteDraft.error_message.contains("Max retries"),
                ~NoteDraft.error_message.contains("Human escalation")
            )
        ).all()

        logger.info(f"Found {len(failed_tasks)} failed tasks eligible for retry")

        from tasks.worker import submit_note_to_emr

        retried = 0
        for task in failed_tasks:
            try:
                # Reset status to allow retry
                task.status = TaskStatus.LLM_COMPLETE
                task.error_message = None
                db.commit()

                # Queue for retry
                submit_note_to_emr.delay(task.id)
                retried += 1
                logger.info(f"Queued task {task.id} for retry")

            except Exception as e:
                logger.error(f"Failed to retry task {task.id}: {e}")
                db.rollback()

        return {
            "eligible_tasks": len(failed_tasks),
            "retried": retried,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed task retry failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.scheduled.send_appointment_reminders')
def send_appointment_reminders():
    """
    Send pending appointment reminders.
    Runs every 5 minutes to check for reminders that are due.
    """
    logger.info("Checking for pending appointment reminders")
    db = SessionLocal()

    try:
        reminder_service = ReminderService(db)

        # Send pending reminders
        stats = asyncio.run(reminder_service.send_pending_reminders())

        logger.info(
            f"Reminder batch complete: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )

        return {
            "sent": stats['sent'],
            "failed": stats['failed'],
            "skipped": stats['skipped'],
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Appointment reminder task failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.scheduled.check_unconfirmed_appointments')
def check_unconfirmed_appointments():
    """
    Check for unconfirmed appointments and escalate to phone calls.
    Runs every hour.
    """
    logger.info("Checking for unconfirmed appointments")
    db = SessionLocal()

    try:
        reminder_service = ReminderService(db)

        # Get appointments within 2 hours without confirmation
        unconfirmed = reminder_service.get_unconfirmed_appointments(hours_before=2)

        logger.info(f"Found {len(unconfirmed)} unconfirmed appointments within 2 hours")

        # TODO: Escalate to phone calls or additional notifications

        return {
            "unconfirmed_count": len(unconfirmed),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Unconfirmed appointment check failed: {e}", exc_info=True)
        raise
    finally:
        db.close()
