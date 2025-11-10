"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab
import os

# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'healthcare_agent',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks.worker', 'tasks.scheduled']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Task routes
celery_app.conf.task_routes = {
    'tasks.worker.submit_note_to_emr': {'queue': 'browser_automation'},
    'tasks.worker.process_email_batch': {'queue': 'default'},
    'tasks.scheduled.*': {'queue': 'scheduled'},
}

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Nightly batch processing at 11 PM
    'process-nightly-batch': {
        'task': 'tasks.scheduled.process_nightly_batch',
        'schedule': crontab(hour=23, minute=0),
    },
    # Daily summary at 8 AM
    'send-daily-summary': {
        'task': 'tasks.scheduled.send_daily_summary',
        'schedule': crontab(hour=8, minute=0),
    },
    # Weekly patient summary on Sundays at 6 PM
    'generate-weekly-summary': {
        'task': 'tasks.scheduled.generate_weekly_patient_summary',
        'schedule': crontab(hour=18, minute=0, day_of_week=0),
    },
    # Cleanup old data weekly on Sundays at 2 AM
    'cleanup-old-data': {
        'task': 'tasks.scheduled.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),
    },
    # Check for stuck tasks every hour
    'check-stuck-tasks': {
        'task': 'tasks.scheduled.check_stuck_tasks',
        'schedule': crontab(minute=0),  # Every hour
    },
    # Retry failed tasks every 4 hours
    'retry-failed-tasks': {
        'task': 'tasks.scheduled.retry_failed_tasks',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    },
    # Cleanup old screenshots daily at 3 AM
    'cleanup-screenshots': {
        'task': 'tasks.worker.cleanup_old_screenshots',
        'schedule': crontab(hour=3, minute=0),
    },
}
