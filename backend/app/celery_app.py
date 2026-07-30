from celery import Celery

from app.config import settings


celery_app = Celery(
    "productshot",
    broker=settings.celery_broker_url or "memory://",
    backend=settings.celery_result_backend or None,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.celery_task_always_eager,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)
