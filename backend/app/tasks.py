from __future__ import annotations

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.quality import QualityRunWorkflow


@celery_app.task(name="productshot.advance_quality_run")
def advance_quality_run(run_id: int, expected_state_version: int | None = None) -> None:
    """Advance one persisted quality-run state transition.

    Every transition is safe to deliver more than once: terminal and waiting
    states are no-ops, and a generation task is persisted before the provider
    call is made.
    """
    with SessionLocal() as db:
        QualityRunWorkflow(db).advance(run_id, expected_state_version)
