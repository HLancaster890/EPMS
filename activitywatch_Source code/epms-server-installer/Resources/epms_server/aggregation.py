"""
Background aggregation worker for EPMS Enterprise Server.
Runs every N minutes to:
1. Compute productivity scores from heartbeats
2. Aggregate process_events into app_sessions
3. Purge old process_events data
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("epms.server.aggregation")

AGGREGATION_INTERVAL_SECONDS = int(os.environ.get("EPMS_AGG_INTERVAL_SECONDS", "300"))
PROCESS_EVENT_RETENTION_DAYS = int(os.environ.get("EPMS_PROCESS_RETENTION_DAYS", "7"))
APP_SESSION_RETENTION_DAYS = int(os.environ.get("EPMS_APP_SESSION_RETENTION_DAYS", "90"))


async def run_aggregation_worker(db_pool) -> None:
    """Background loop that periodically aggregates process data."""
    logger.info("Aggregation worker started (interval=%ds)", AGGREGATION_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.sleep(AGGREGATION_INTERVAL_SECONDS)
            if db_pool:
                await _aggregate_productivity_scores(db_pool)
                await _aggregate_app_sessions(db_pool)
                await _purge_old_data(db_pool)
        except asyncio.CancelledError:
            logger.info("Aggregation worker cancelled")
            break
        except Exception as e:
            logger.error("Aggregation worker error: %s", e)


async def _aggregate_productivity_scores(db_pool) -> None:
    """Score every agent's last interval of heartbeats."""
    try:
        async with db_pool.acquire() as conn:
            agents = await conn.fetch(
                "SELECT agent_id, organization_id FROM agents WHERE is_online = true"
            )
        for row in agents:
            try:
                await _score_agent_interval(db_pool, row["agent_id"],
                                            str(row["organization_id"]))
            except Exception as e:
                logger.debug("Score error for %s: %s", row["agent_id"], e)
        if agents:
            logger.debug("Scored %d agents", len(agents))
    except Exception as e:
        logger.warning("Productivity scoring cycle failed: %s", e)


async def _aggregate_app_sessions(db_pool) -> None:
    """Aggregate process_events into app_sessions via the DB function."""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT epms_aggregate_app_sessions($1)", 5
            )
            if result and result > 0:
                logger.info("Created %d new app sessions", result)
    except Exception as e:
        logger.warning("App session aggregation failed: %s", e)


async def _purge_old_data(db_pool) -> None:
    """Purge expired process_events and app_sessions."""
    try:
        async with db_pool.acquire() as conn:
            purged = await conn.fetchval(
                "SELECT epms_purge_process_events($1)", PROCESS_EVENT_RETENTION_DAYS
            )
            if purged and purged > 0:
                logger.info("Purged %d old process_events", purged)
    except Exception as e:
        logger.debug("Purge cycle notice: %s", e)


# =============================================================
# Productivity Score Computation (moved from epms_analytics_service)
# =============================================================

async def _score_agent_interval(db_pool, agent_id: str, org_id: str) -> None:
    """Compute a productivity score for one agent for the current day."""
    from datetime import date as date_type
    today = date_type.today()

    async with db_pool.acquire() as conn:
        # Get heartbeats from the last interval
        minutes = AGGREGATION_INTERVAL_SECONDS // 60
        rows = await conn.fetch(
            """SELECT timestamp, afk_seconds, is_afk,
                      active_window_process, browser_activity IS NOT NULL as has_browser,
                      editor_activity IS NOT NULL as has_editor
               FROM agent_heartbeats
               WHERE agent_id = $1
                 AND timestamp >= NOW() - ($2 || ' minutes')::INTERVAL
               ORDER BY timestamp""",
            agent_id, str(max(minutes, 1)),
        )

        if not rows:
            return

        total_seconds = 0
        productive_seconds = 0
        neutral_seconds = 0
        distracting_seconds = 0
        idle_seconds = 0
        category_breakdown: dict = {}

        for i in range(len(rows) - 1):
            delta = (rows[i + 1]["timestamp"] - rows[i]["timestamp"]).total_seconds()
            if delta <= 0 or delta > 300:
                continue

            r = rows[i]
            if r["is_afk"]:
                idle_seconds += delta
                continue

            total_seconds += delta

            # Classify activity
            is_productive = False
            is_distracting = False

            if r["has_editor"]:
                is_productive = True
            elif r["has_browser"]:
                cat = getattr(r, "category", "") or ""
                is_productive = cat != "social_media" and cat != "entertainment"
            elif r["active_window_process"]:
                pname = (r["active_window_process"] or "").lower()
                distracting = {"spotify", "netflix", "youtube", "game", "steam",
                               "discord", "slack", "telegram"}
                productive = {"code", "visual studio", "intellij", "pycharm",
                              "terminal", "powershell", "cmd", "outlook",
                              "excel", "word"}
                if any(d in pname for d in distracting):
                    is_distracting = True
                elif any(p in pname for p in productive):
                    is_productive = True

            if is_productive:
                productive_seconds += delta
            elif is_distracting:
                distracting_seconds += delta
            else:
                neutral_seconds += delta

            # Category breakdown
            if r["active_window_process"]:
                cat = r["active_window_process"]
                cat_key = str(cat).lower().replace(" ", "_")[:50] or "unknown"
                category_breakdown[cat_key] = category_breakdown.get(cat_key, 0) + delta

        total_classified = productive_seconds + neutral_seconds + distracting_seconds
        score = round((productive_seconds / total_classified * 100) if total_classified > 0 else 50, 1)

        await conn.execute(
            """INSERT INTO productivity_scores
               (agent_id, organization_id, date, score,
                productive_time_seconds, neutral_time_seconds,
                distracting_time_seconds, idle_time_seconds,
                category_breakdown)
               VALUES ($1, $2::uuid, $3::date, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (agent_id, date)
               DO UPDATE SET score = EXCLUDED.score,
                   productive_time_seconds = EXCLUDED.productive_time_seconds,
                   neutral_time_seconds = EXCLUDED.neutral_time_seconds,
                   distracting_time_seconds = EXCLUDED.distracting_time_seconds,
                   idle_time_seconds = EXCLUDED.idle_time_seconds,
                   category_breakdown = EXCLUDED.category_breakdown""",
            agent_id, org_id, today.isoformat(), score,
            productive_seconds, neutral_seconds,
            distracting_seconds, idle_seconds,
            json.dumps(category_breakdown),
        )
