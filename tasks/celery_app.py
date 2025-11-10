"""Celery application configuration."""
from celery import Celery
import os

# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'healthcare_agent',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks.worker']
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
}
