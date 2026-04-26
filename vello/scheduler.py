"""
Background scheduler — briefings + nightly pattern refresh.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _run_briefings() -> None:
    from vello.briefing import send_all_briefings
    log.info("scheduler: running briefings")
    send_all_briefings()


def _run_pattern_refresh() -> None:
    from vello.temporal import refresh_all_patterns
    log.info("scheduler: refreshing temporal patterns")
    try:
        refresh_all_patterns()
    except Exception as exc:
        log.error("pattern refresh failed: %s", exc)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    # Check every hour whether any user's briefing_hour matches current UTC hour
    _scheduler.add_job(_run_briefings,       CronTrigger(minute=0),         id="briefings",       replace_existing=True)
    _scheduler.add_job(_run_pattern_refresh, CronTrigger(hour=3, minute=0), id="pattern_refresh", replace_existing=True)
    _scheduler.start()
    log.info("scheduler started")


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler stopped")
