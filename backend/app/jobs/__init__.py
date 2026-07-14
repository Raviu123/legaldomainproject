"""Scheduled jobs for the Legal Knowledge Graph system.

This package implements background jobs that maintain law freshness:

  check_updates.py   — Polls official sources for amendments / new versions.
  refresh_law.py     — Re-runs the ingestion pipeline for a specific law.

Jobs are designed to be triggered by:
  - A cron scheduler (e.g. APScheduler, Celery Beat, system cron).
  - A CI/CD pipeline step (GitHub Actions scheduled workflow).
  - A future admin API endpoint (POST /api/v1/admin/refresh).

To schedule jobs with APScheduler (add to main.py startup):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.jobs.check_updates import check_all_law_updates

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all_law_updates, 'cron', hour=3)  # 3am daily
    scheduler.start()
"""
