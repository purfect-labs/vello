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


def _run_home_morning_review() -> None:
    """Fire morning_review agent turns for users whose local hour == morning_hour."""
    if not _try_acquire_lock("home_morning_review", _current_period("hour")):
        return
    log.info("scheduler: home morning reviews (leader=%s)", _PROCESS_ID)
    _fire_time_based_agent_turns("morning_review", policy_hour_key="morning_hour", default_hour=7)


def _run_home_evening_review() -> None:
    if not _try_acquire_lock("home_evening_review", _current_period("hour")):
        return
    log.info("scheduler: home evening reviews (leader=%s)", _PROCESS_ID)
    _fire_time_based_agent_turns("evening_review", policy_hour_key="evening_hour", default_hour=21)


def _run_home_weekly_planning() -> None:
    if not _try_acquire_lock("home_weekly_planning", _current_period("day")):
        return
    log.info("scheduler: weekly planning (leader=%s)", _PROCESS_ID)
    _fire_all_users_agent_turn("weekly_planning")


def _run_inventory_decay_scan() -> None:
    if not _try_acquire_lock("inventory_decay_scan", _current_period("day")):
        return
    log.info("scheduler: inventory decay scan (leader=%s)", _PROCESS_ID)
    try:
        from vello.database import get_connection, list_inventory
        conn = get_connection()
        users = conn.execute(
            "SELECT DISTINCT owner_user_id FROM households"
        ).fetchall()
        conn.close()
        from vello.agent.loop import run_agent_turn
        for row in users:
            uid = row[0]
            hh_conn = get_connection()
            hh = hh_conn.execute(
                "SELECT * FROM households WHERE owner_user_id=? LIMIT 1", (uid,)
            ).fetchone()
            hh_conn.close()
            if not hh:
                continue
            low_items = list_inventory(hh["id"], low_stock_only=True)
            for item in low_items:
                try:
                    run_agent_turn(
                        user_id=uid,
                        trigger_kind="restock_needed",
                        trigger_payload={"item_id": item["id"], "label": item["label"]},
                    )
                except Exception as exc:
                    log.error("restock_needed turn failed for user %s item %s: %s",
                              uid, item["id"], exc)
    except Exception as exc:
        log.error("inventory decay scan failed: %s", exc)


def _run_episodic_consolidation() -> None:
    if not _try_acquire_lock("episodic_consolidation", _current_period("day")):
        return
    log.info("scheduler: episodic consolidation (leader=%s)", _PROCESS_ID)
    try:
        from vello.database import get_connection, get_user_policy, bump_tool_stat
        from vello.agent.approval import find_promotion_candidates
        from vello.agent.tools import get_tool
        conn = get_connection()
        users = conn.execute("SELECT id FROM users").fetchall()
        conn.close()
        for row in users:
            uid = row[0]
            candidates = find_promotion_candidates(uid)
            for candidate in candidates:
                tool_name = candidate["tool"]
                tool = get_tool(tool_name)
                if not tool:
                    continue
                summary = (
                    f"You've confirmed '{tool_name}' {candidate['confirmed']} of "
                    f"{candidate['confirmed'] + candidate['dismissed']} times. "
                    "Make automatic?"
                )
                from vello.database import create_draft
                create_draft(
                    user_id=uid,
                    session_id=None,
                    tool_name="__promotion__",
                    tool_args={"tool_name": tool_name, "kind": "promotion_prompt"},
                    summary=summary,
                )
    except Exception as exc:
        log.error("episodic consolidation failed: %s", exc)


def _run_campaign_sweeper() -> None:
    if not _try_acquire_lock("campaign_sweeper", _current_period("day")):
        return
    log.info("scheduler: campaign sweeper (leader=%s)", _PROCESS_ID)
    try:
        from vello.database import expire_due_campaigns
        n = expire_due_campaigns()
        if n:
            log.info("expired %d campaigns", n)
    except Exception as exc:
        log.error("campaign sweeper failed: %s", exc)


def _fire_time_based_agent_turns(trigger_kind: str, policy_hour_key: str,
                                  default_hour: int) -> None:
    """Fire agent turns for users whose local time matches the configured hour."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        ZoneInfo = None  # type: ignore

    from vello.database import get_connection, get_user_policy
    from vello.agent.loop import run_agent_turn

    conn = get_connection()
    rows = conn.execute("SELECT id, timezone FROM users").fetchall()
    conn.close()

    now_utc = datetime.now(timezone.utc)
    for row in rows:
        tz_name = (row["timezone"] if "timezone" in row.keys() else None) or "UTC"
        try:
            local_hour = now_utc.astimezone(ZoneInfo(tz_name)).hour if ZoneInfo else now_utc.hour
        except Exception:
            local_hour = now_utc.hour

        policy = get_user_policy(row["id"])
        target_hour = int(policy.get(policy_hour_key, default_hour))
        if local_hour != target_hour:
            continue
        try:
            run_agent_turn(user_id=row["id"], trigger_kind=trigger_kind, trigger_payload={})
        except Exception as exc:
            log.error("%s turn failed for user %s: %s", trigger_kind, row["id"], exc)


def _fire_all_users_agent_turn(trigger_kind: str) -> None:
    from vello.database import get_connection
    from vello.agent.loop import run_agent_turn
    conn = get_connection()
    rows = conn.execute("SELECT id FROM users").fetchall()
    conn.close()
    for row in rows:
        try:
            run_agent_turn(user_id=row["id"], trigger_kind=trigger_kind, trigger_payload={})
        except Exception as exc:
            log.error("%s turn failed for user %s: %s", trigger_kind, row["id"], exc)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_run_briefings,              CronTrigger(minute=0),               id="briefings",               replace_existing=True)
    _scheduler.add_job(_run_pattern_refresh,        CronTrigger(hour=3,  minute=0),      id="pattern_refresh",         replace_existing=True)
    _scheduler.add_job(_run_home_morning_review,    CronTrigger(minute=0),               id="home_morning_review",     replace_existing=True)
    _scheduler.add_job(_run_home_evening_review,    CronTrigger(minute=0),               id="home_evening_review",     replace_existing=True)
    _scheduler.add_job(_run_home_weekly_planning,   CronTrigger(day_of_week="sun", hour=19, minute=0), id="home_weekly_planning", replace_existing=True)
    _scheduler.add_job(_run_inventory_decay_scan,   CronTrigger(hour=2,  minute=0),      id="inventory_decay_scan",    replace_existing=True)
    _scheduler.add_job(_run_episodic_consolidation, CronTrigger(hour=4,  minute=0),      id="episodic_consolidation",  replace_existing=True)
    _scheduler.add_job(_run_campaign_sweeper,       CronTrigger(hour=1,  minute=0),      id="campaign_sweeper",        replace_existing=True)
    _scheduler.start()
    log.info("scheduler started (process %s)", _PROCESS_ID)


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler stopped")
