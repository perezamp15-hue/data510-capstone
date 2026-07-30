"""Collection-run auditing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from baseball_capstone.database.models import CollectionRun


@dataclass(slots=True)
class CollectionMetrics:
    """Counts produced by one collector execution."""

    records_read: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_rejected: int = 0


def start_collection_run(
    session: Session,
    collector_name: str,
    requested_start_date: date | None = None,
    requested_end_date: date | None = None,
) -> CollectionRun:
    """Create and flush a running collection record."""
    collection_run = CollectionRun(
        collector_name=collector_name,
        status="running",
        requested_start_date=requested_start_date,
        requested_end_date=requested_end_date,
    )

    session.add(collection_run)
    session.flush()

    return collection_run


def complete_collection_run(
    collection_run: CollectionRun,
    metrics: CollectionMetrics,
) -> None:
    """Mark a collection run as successful."""
    collection_run.status = "completed"
    collection_run.completed_at = datetime.now(timezone.utc)
    collection_run.records_read = metrics.records_read
    collection_run.records_inserted = metrics.records_inserted
    collection_run.records_updated = metrics.records_updated
    collection_run.records_rejected = metrics.records_rejected
    collection_run.error_message = None


def fail_collection_run(
    collection_run: CollectionRun,
    error: Exception,
    metrics: CollectionMetrics | None = None,
) -> None:
    """Mark a collection run as failed."""
    metrics = metrics or CollectionMetrics()

    collection_run.status = "failed"
    collection_run.completed_at = datetime.now(timezone.utc)
    collection_run.records_read = metrics.records_read
    collection_run.records_inserted = metrics.records_inserted
    collection_run.records_updated = metrics.records_updated
    collection_run.records_rejected = metrics.records_rejected
    collection_run.error_message = str(error)[:5000]