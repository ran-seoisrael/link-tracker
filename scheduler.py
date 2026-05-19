import logging

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None

IL_TZ = pytz.timezone("Asia/Jerusalem")


def _run_all_checks():
    """Check every link in the database. Runs in background thread."""
    from database import get_all_link_ids, get_link, update_link_check
    from checker import check_link

    ids = get_all_link_ids()
    logger.info("Scheduler: starting weekly check for %d links", len(ids))
    for link_id in ids:
        row = get_link(link_id)
        if not row:
            continue
        try:
            result = check_link(row["page_url"], row["expected_link_url"], row["expected_anchor"])
            update_link_check(link_id, result)
        except Exception as exc:
            logger.error("Error checking link %d: %s", link_id, exc)
    logger.info("Scheduler: weekly check complete")


def init_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler(timezone=IL_TZ)
    # Every Sunday at 10:00 Israel time
    _scheduler.add_job(
        _run_all_checks,
        trigger=CronTrigger(day_of_week="sun", hour=10, minute=0, timezone=IL_TZ),
        id="weekly_check",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — weekly check every Sunday 10:00 IL time")


def shutdown_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)
