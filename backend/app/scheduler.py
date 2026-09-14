"""
APScheduler-based background scheduler for continuous research monitoring.

Parses cron expressions from config and schedules:
- Full discovery sync (weekly Sunday 2am)
- Citation refresh (Wednesday 3am)
- Metrics computation (Wednesday 4am)
- Alert generation (daily 5am)
- Report generation (monthly 1st 6am)

Runs in-process alongside the FastAPI event loop — no external broker required.
"""

import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import async_session_factory

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def _parse_cron(expr: str) -> dict:
    """Parse a 5-field cron expression into APScheduler CronTrigger kwargs."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: '{expr}' (expected 5 fields)")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


async def _run_full_discovery():
    """Scheduled job: Run the complete multi-agent pipeline."""
    logger.info("SCHEDULER: Starting scheduled full discovery sync")
    try:
        from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator
        async with async_session_factory() as session:
            orchestrator = PipelineOrchestrator(session)
            stats = await orchestrator.run_full_pipeline(trigger="scheduled")
            logger.info(f"SCHEDULER: Full discovery completed — {stats.get('total_errors', 0)} errors")
    except Exception as e:
        logger.error(f"SCHEDULER: Full discovery failed — {e}", exc_info=True)


async def _run_citation_refresh():
    """Scheduled job: Refresh citation counts from external APIs."""
    logger.info("SCHEDULER: Starting scheduled citation refresh")
    try:
        from app.agents.metrics_agent import MetricsAgent
        from app.models.agent import SyncRun
        async with async_session_factory() as session:
            sync_run = SyncRun(
                id=uuid.uuid4(),
                run_type="citation_refresh",
                status="running",
                trigger="scheduled",
                started_at=datetime.now(timezone.utc),
            )
            session.add(sync_run)
            await session.commit()

            agent = MetricsAgent(session)
            stats = await agent.run()

            sync_run.status = "completed"
            sync_run.completed_at = datetime.now(timezone.utc)
            sync_run.errors_count = stats.get("errors", 0)
            await session.commit()
            logger.info(f"SCHEDULER: Citation refresh completed — {stats}")
    except Exception as e:
        logger.error(f"SCHEDULER: Citation refresh failed — {e}", exc_info=True)


async def _run_metrics_compute():
    """Scheduled job: Recompute faculty h-index / i10 / snapshots."""
    logger.info("SCHEDULER: Starting scheduled metrics computation")
    try:
        from app.agents.metrics_agent import MetricsAgent
        async with async_session_factory() as session:
            agent = MetricsAgent(session)
            stats = await agent.run()
            logger.info(f"SCHEDULER: Metrics computation completed — {stats}")
    except Exception as e:
        logger.error(f"SCHEDULER: Metrics computation failed — {e}", exc_info=True)


async def _run_alert_generation():
    """Scheduled job: Generate notification alerts from recent events."""
    logger.info("SCHEDULER: Starting scheduled alert generation")
    try:
        from app.services.notification_service import NotificationService
        async with async_session_factory() as session:
            notif_service = NotificationService(session)
            await notif_service.create_notification(
                title="Daily Research Sync Heartbeat",
                message="Scheduled alert generation cycle completed successfully.",
                notification_type="system_heartbeat",
                severity="info",
                category="system",
                source_agent="Scheduler",
                source_event="daily_alert_cycle",
                dedup_key=f"heartbeat:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            )
            await session.commit()
            logger.info("SCHEDULER: Alert generation completed")
    except Exception as e:
        logger.error(f"SCHEDULER: Alert generation failed — {e}", exc_info=True)


async def _run_report_generation():
    """Scheduled job: Generate monthly institution-wide report."""
    logger.info("SCHEDULER: Starting scheduled report generation")
    try:
        from app.agents.reporting_agent import ReportingAgent
        async with async_session_factory() as session:
            agent = ReportingAgent(session)
            report = await agent.generate_institution_report()
            logger.info(
                f"SCHEDULER: Monthly report generated — "
                f"{report.get('kpis', {}).get('total_publications', 0)} publications, "
                f"{report.get('kpis', {}).get('total_citations', 0)} citations"
            )
    except Exception as e:
        logger.error(f"SCHEDULER: Report generation failed — {e}", exc_info=True)


def start_scheduler() -> AsyncIOScheduler:
    """Initialize and start the APScheduler with configured cron jobs."""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.info("Scheduler already running")
        return _scheduler

    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Job definitions mapping config cron expressions to handler functions
    jobs = [
        ("full_discovery_sync", settings.sync_full_discovery, _run_full_discovery),
        ("citation_refresh", settings.sync_citation_refresh, _run_citation_refresh),
        ("metrics_compute", settings.sync_metrics_compute, _run_metrics_compute),
        ("alert_generation", settings.sync_alert_generation, _run_alert_generation),
        ("report_generation", settings.sync_report_generation, _run_report_generation),
    ]

    for job_id, cron_expr, func in jobs:
        try:
            cron_kwargs = _parse_cron(cron_expr)
            trigger = CronTrigger(**cron_kwargs)
            scheduler.add_job(func, trigger, id=job_id, replace_existing=True)
            logger.info(f"SCHEDULER: Registered job '{job_id}' with cron '{cron_expr}'")
        except Exception as e:
            logger.error(f"SCHEDULER: Failed to register job '{job_id}': {e}")

    scheduler.start()
    _scheduler = scheduler
    logger.info("SCHEDULER: Background scheduler started with %d jobs", len(scheduler.get_jobs()))
    return scheduler


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("SCHEDULER: Background scheduler stopped")
        _scheduler = None


def get_scheduler_status() -> dict:
    """Get current scheduler status and job listing."""
    if not _scheduler:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": _scheduler.running,
        "jobs": jobs,
    }
