"""
Background scheduler — briefings + nightly pattern refresh.

Leader election: with multiple uvicorn workers each process starts its own
APScheduler. Without coordination, every worker would fire briefings every
hour (N times the email volume per user). We use a DB-backed advisory lock:
the first process to insert into `scheduler_locks` for a given job + UTC
hour runs the job. Other processes find the lock already taken and skip.

Lock rows are keyed by (job_id, lock_period) so old locks naturally age out.
"""
import logging
import os
import socket
import sqlite3
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
# Stable per-process identifier so the holder is observable in the DB.
_PROCESS_ID = f"{socket.gethostname()}:{os.getpid()}"


def _try_acquire_lock(job_id: str, period_key: str) -> bool:
    """
    Try to acquire the (job_id, period_key) lock. Returns True if this
    process won the race and should run the job, False otherwise.

    period_key is a coarse-grained timestamp (e.g. "2026-05-03T14") so a
    new lock is needed for each scheduled tick. UNIQUE constraint on
    (job_id, period_key) makes the insert the atomic decision point.
    """
    from vello.database import get_connection
    try:
        conn = get_connection()
        with conn:
            conn.execute(
                "INSERT INTO scheduler_locks (job_id, period_key, holder, acquired_at) "
                "VALUES (?, ?, ?, ?)",
                (job_id, period_key, _PROCESS_ID, datetime.now(timezone.utc).isoformat()),
            )
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as exc:
        log.warning("lock acquisition errored for %s: %s", job_id, exc)
        return False


def _current_period(granularity: str = "hour") -> str:
    now = datetime.now(timezone.utc)
    if granularity == "hour":
        return now.strftime("%Y-%m-%dT%H")
    if granularity == "day":
        return now.strftime("%Y-%m-%d")
    return now.isoformat()


def _run_briefings() -> None:
    if not _try_acquire_lock("briefings", _current_period("hour")):
        return  # another worker already firing this tick
    from vello.briefing import send_all_briefings
    log.info("scheduler: running briefings (leader=%s)", _PROCESS_ID)
    send_all_briefings()


def _run_pattern_refresh() -> None:
    if not _try_acquire_lock("pattern_refresh", _current_period("day")):
        return
    from vello.temporal import refresh_all_patterns
    log.info("scheduler: refreshing temporal patterns (leader=%s)", _PROCESS_ID)
    try:
        refresh_all_patterns()
    except Exception as exc:
        log.error("pattern refresh failed: %s", exc)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_run_briefings,       CronTrigger(minute=0),         id="briefings",       replace_existing=True)
    _scheduler.add_job(_run_pattern_refresh, CronTrigger(hour=3, minute=0), id="pattern_refresh", replace_existing=True)
    _scheduler.start()
    log.info("scheduler started (process %s)", _PROCESS_ID)


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler stopped")
