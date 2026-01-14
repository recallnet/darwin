"""
Celery application configuration for Darwin API.

Configures Celery for background task execution with Redis broker.
"""

import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery application
celery_app = Celery(
    "darwin",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["darwin.api.tasks.run_executor"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Result backend settings
    result_expires=3600 * 24 * 7,  # 7 days
    result_backend_transport_options={
        "master_name": "mymaster",
    },

    # Task execution settings
    task_track_started=True,
    task_time_limit=3600 * 12,  # 12 hours hard limit
    task_soft_time_limit=3600 * 10,  # 10 hours soft limit

    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (memory cleanup)

    # Task routing (can add custom queues later)
    # task_routes={
    #     "darwin.api.tasks.run_executor.*": {"queue": "runs"},
    # },

    # Retry settings
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Retry if worker crashes
)

# Optional: Beat schedule for periodic tasks (future use)
celery_app.conf.beat_schedule = {
    # Example: Clean up old task results
    # "cleanup-results": {
    #     "task": "darwin.api.tasks.cleanup.cleanup_old_results",
    #     "schedule": 3600.0,  # Every hour
    # },
}

if __name__ == "__main__":
    celery_app.start()
