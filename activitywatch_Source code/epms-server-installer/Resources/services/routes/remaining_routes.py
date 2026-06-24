"""
Temporary container for routes not yet extracted into dedicated modules.
Will be split into dashboard_routes.py, admin_routes.py, notifications_routes.py,
reports_routes.py, productivity_routes.py, websocket_routes.py in Phase 2.
"""

import os
import json
import uuid
import hashlib
import secrets
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Header, Request, status, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from starlette.websockets import WebSocketState

from routes.models import (
    NotificationRequest, ReportRequest, ProductivityRuleRequest,
    SystemInventoryResponse, InventorySummaryResponse,
    HealthDeviceResponse, HealthAnomalyItem, ExecutiveSummaryResponse,
)
from routes.helpers import (
    _parse_ts, hash_api_key, verify_api_key, validate_agent_identity,
    get_db, _compute_health_score, _send_email,
    _report_to_html, _build_report_file, _query_report_data,
    _build_activity_report, _build_productivity_report,
)
import routes.state as app_state

from epms_server.config import TOKEN_BLACKLIST_PREFIX, ENROLLMENT_MODE
from epms_server.rbac import AuthContext, get_current_user, decode_token, require_role, filter_by_role, Role, ROLE_MAP

router = APIRouter()


# ===== Dashboard Data Endpoints =====

@router.get("/api/v1/dashboard/summary")
async def get_dashboard_summary(
    current_user: AuthContext = Depends(get_current_user),
    period: str = Query(default="today"),
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
):
    from datetime import date as date_type
    today = date_type.today()
    if period == "week":
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == "month":
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == "custom" and start_date:
        date_from = datetime.fromisoformat(start_date).date() if "T" in start_date else date_type.fromisoformat(start_date)
        date_to = datetime.fromisoformat(end_date).date() if end_date and "T" in end_date else (date_type.fromisoformat(end_date) if end_date else today)
    else:
        date_from = today
        date_to = today

    org_id = current_user.org_id
    data = {
        "total_devices": 0, "online_devices": 0, "offline_devices": 0,
        "active_devices": 0, "active_today": 0,
        "avg_productivity": 0, "average_productivity": 0,
        "total_events_today": 0, "events_today": 0,
    }

    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE is_online) as online, "
                "COUNT(*) FILTER (WHERE NOT is_online) as offline "
                "FROM agents WHERE organization_id = $1::uuid", org_id,
            )
            if row:
                data["total_devices"] = row["total"]
                data["online_devices"] = row["online"]
                data["offline_devices"] = row["offline"]

            active_count = await conn.fetchval(
                "SELECT COUNT(DISTINCT h.agent_id) FROM agent_heartbeats h "
                "JOIN agents a ON h.agent_id = a.agent_id "
                "WHERE h.timestamp >= $2::date AND h.timestamp <= ($3::date + interval '1 day')::date "
                "AND a.organization_id = $1::uuid",
                org_id, date_from, date_to,
            )
            data["active_today"] = data["active_devices"] = active_count or 0

            avg_prod = await conn.fetchval(
                "SELECT AVG(score) FROM productivity_scores "
                "WHERE organization_id = $1::uuid AND date >= $2::date AND date <= $3::date",
                org_id, date_from, date_to,
            )
            data["avg_productivity"] = data["average_productivity"] = round(avg_prod or 0, 1)

            events_count = await conn.fetchval(
                "SELECT COUNT(*) FROM activity_events ev "
                "JOIN agents a ON ev.agent_id::text = a.agent_id "
                "WHERE a.organization_id = $1::uuid AND ev.timestamp >= $2::date",
                org_id, date_from,
            )
            data["total_events_today"] = data["events_today"] = events_count or 0

    return data


@router.get("/api/v1/dashboard/devices")
async def get_devices(current_user: AuthContext = Depends(get_current_user)):
    org_id = current_user.org_id
    devices = []
    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT agent_id, display_name, hostname, os, version, "
                "is_online, last_heartbeat, created_at "
                "FROM agents WHERE organization_id = $1::uuid "
                "ORDER BY last_heartbeat DESC NULLS LAST", org_id,
            )
            for row in rows:
                devices.append({
                    "id": row["agent_id"],
                    "name": row["display_name"] or row["hostname"] or row["agent_id"],
                    "hostname": row["hostname"],
                    "os": row["os"],
                    "version": row["version"],
                    "is_online": row["is_online"],
                    "last_heartbeat": row["last_heartbeat"].isoformat() if row["last_heartbeat"] else None,
                    "created_at": row["created_at"].isoformat(),
                })
    return {"devices": devices}


@router.get("/api/v1/dashboard/activity")
async def get_recent_activity(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    org_id = current_user.org_id
    events = []
    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT a.display_name, h.timestamp, h.active_window_title, "
                "h.active_window_process, h.is_afk, h.afk_seconds "
                "FROM agent_heartbeats h JOIN agents a ON h.agent_id = a.agent_id "
                "WHERE a.organization_id = $1::uuid "
                "ORDER BY h.timestamp DESC LIMIT $2", org_id, limit,
            )
            for row in rows:
                events.append({
                    "user": row["display_name"] or "Unknown",
                    "action": f"Active window: {row['active_window_title'] or 'Unknown'}",
                    "app": row["active_window_process"] or "",
                    "time": row["timestamp"].isoformat(),
                    "is_afk": row["is_afk"],
                })
    return {"events": events}


@router.get("/api/v1/analytics/productivity")
async def get_productivity_data(
    days: int = 7,
    current_user: AuthContext = Depends(get_current_user),
):
    org_id = current_user.org_id
    data = []
    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT date, AVG(score) as avg_score, "
                "SUM(productive_time_seconds) as productive, "
                "SUM(neutral_time_seconds) as neutral, "
                "SUM(distracting_time_seconds) as distracting, "
                "SUM(idle_time_seconds) as idle "
                "FROM productivity_scores WHERE organization_id = $1::uuid "
                "AND date >= CURRENT_DATE - ($2 || ' days')::INTERVAL "
                "GROUP BY date ORDER BY date", org_id, str(days),
            )
            for row in rows:
                data.append({
                    "date": row["date"].isoformat(),
                    "score": round(row["avg_score"] or 0, 1),
                    "productive_seconds": row["productive"] or 0,
                    "neutral_seconds": row["neutral"] or 0,
                    "distracting_seconds": row["distracting"] or 0,
                    "idle_seconds": row["idle"] or 0,
                })
    return {"data": data, "period_days": days}


@router.get("/api/v1/analytics/scores/{agent_id}")
async def get_agent_score(
    agent_id: str,
    date: str = Query(default=None),
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT score, productive_time_seconds, neutral_time_seconds,
                      distracting_time_seconds, category_breakdown
               FROM productivity_scores
               WHERE agent_id = $1::uuid AND date = $2::date""",
            agent_id, target,
        )
        if not row:
            raise HTTPException(status_code=404, detail="No score found for this agent/date")
        return {
            "agent_id": agent_id, "date": target,
            "score": row["score"],
            "productive_time_seconds": row["productive_time_seconds"],
            "neutral_time_seconds": row["neutral_time_seconds"],
            "distracting_time_seconds": row["distracting_time_seconds"],
            "categories": row["category_breakdown"] or {},
        }


@router.get("/api/v1/analytics/trends/{agent_id}")
async def get_agent_trends(
    agent_id: str,
    days: int = Query(default=30, le=365),
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with app_state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT date, score, productive_time_seconds,
                      neutral_time_seconds, distracting_time_seconds
               FROM productivity_scores
               WHERE agent_id = $1::uuid AND date >= CURRENT_DATE - $2::integer
               ORDER BY date""",
            agent_id, days,
        )
        return {"agent_id": agent_id, "period_days": days, "scores": [dict(r) for r in rows]}


@router.get("/api/v1/analytics/organization")
async def get_org_summary(
    days: int = Query(default=7),
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with app_state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT a.organization_id, AVG(ps.score) as avg_score,
                      SUM(ps.productive_time_seconds) as total_productive,
                      COUNT(DISTINCT a.agent_id) as active_agents
               FROM productivity_scores ps
               JOIN agents a ON ps.agent_id::text = a.agent_id
               WHERE ps.date >= CURRENT_DATE - $1::integer
               GROUP BY a.organization_id""",
            days,
        )
        return [dict(r) for r in rows]


@router.get("/api/v1/analytics/live/{agent_id}")
async def get_live_score(
    agent_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT score, productive_time_seconds, neutral_time_seconds,
                      distracting_time_seconds, idle_time_seconds, hb_count
               FROM productivity_scores
               WHERE agent_id = $1::uuid AND date = $2::date""",
            agent_id, today,
        )
        if not row:
            return {"agent_id": agent_id, "date": today, "score": 0, "heartbeats_processed": 0, "status": "no_data"}
        return {
            "agent_id": agent_id, "date": today, "score": row["score"],
            "heartbeats_processed": row.get("hb_count", 0),
            "productive_seconds": row["productive_time_seconds"],
            "neutral_seconds": row["neutral_time_seconds"],
            "distracting_seconds": row["distracting_time_seconds"],
            "idle_seconds": row.get("idle_time_seconds", 0),
            "status": "active",
        }


@router.get("/api/v1/dashboard/browser-activity")
async def get_browser_activity(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    org_id = current_user.org_id
    rows_data = []
    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT a.display_name, b.browser_name, b.domain, b.url,
                          b.page_title, b.is_productive, b.timestamp
                   FROM browser_activity b JOIN agents a ON b.agent_id::text = a.agent_id
                   WHERE a.organization_id = $1::uuid
                   ORDER BY b.timestamp DESC LIMIT $2""",
                org_id, limit,
            )
            for row in rows:
                rows_data.append({
                    "user": row["display_name"] or "Unknown",
                    "browser": row["browser_name"] or "Unknown",
                    "browser_name": row["browser_name"] or "Unknown",
                    "domain": row["domain"] or "",
                    "url": row["url"] or "",
                    "page_title": row["page_title"] or "",
                    "title": row["page_title"] or "",
                    "is_productive": row["is_productive"],
                    "duration_seconds": 0,
                    "timestamp": row["timestamp"].isoformat(),
                })
    return {"events": rows_data}


@router.get("/api/v1/dashboard/editor-activity")
async def get_editor_activity(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    org_id = current_user.org_id
    rows_data = []
    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT a.display_name, e.editor_name, e.project_name,
                          e.file_name, e.language, e.timestamp
                   FROM editor_activity e JOIN agents a ON e.agent_id::text = a.agent_id
                   WHERE a.organization_id = $1::uuid
                   ORDER BY e.timestamp DESC LIMIT $2""",
                org_id, limit,
            )
            for row in rows:
                rows_data.append({
                    "user": row["display_name"] or "Unknown",
                    "editor": row["editor_name"] or "Unknown",
                    "editor_name": row["editor_name"] or "Unknown",
                    "project": row["project_name"] or "",
                    "project_name": row["project_name"] or "",
                    "file": row["file_name"] or "",
                    "file_name": row["file_name"] or "",
                    "language": row["language"] or "",
                    "duration_seconds": 0,
                    "timestamp": row["timestamp"].isoformat(),
                })
    return {"events": rows_data}


@router.get("/api/v1/dashboard/alerts")
async def get_alerts(
    limit: int = 20,
    current_user: AuthContext = Depends(get_current_user),
):
    org_id = current_user.org_id
    rows_data = []
    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, alert_type, severity, title, message,
                          acknowledged, created_at
                   FROM alerts WHERE organization_id = $1::uuid
                   ORDER BY created_at DESC LIMIT $2""",
                org_id, limit,
            )
            for row in rows:
                created_at_str = row["created_at"].isoformat()
                rows_data.append({
                    "id": str(row["id"]),
                    "type": row["alert_type"] or "info",
                    "severity": row["severity"] or "info",
                    "title": row["title"],
                    "description": row["message"] or "",
                    "message": row["message"] or "",
                    "source": "system",
                    "agent_id": "",
                    "time": created_at_str,
                    "created_at": created_at_str,
                    "acknowledged": row["acknowledged"] or False,
                })
    return {"alerts": rows_data}


@router.post("/api/v1/dashboard/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE alerts SET acknowledged = true WHERE id = $1::uuid", alert_id,
            )
    return {"status": "ok"}


@router.get("/api/v1/dashboard/reports")
async def get_reports(
    limit: int = 20,
    current_user: AuthContext = Depends(get_current_user),
):
    org_id = current_user.org_id
    rows_data = []
    if app_state.db_pool and org_id:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, report_type, title, filters, format,
                          created_by, created_at
                   FROM reports WHERE organization_id = $1::uuid
                   ORDER BY created_at DESC LIMIT $2""",
                org_id, limit,
            )
            for row in rows:
                created_at_str = row["created_at"].isoformat()
                rows_data.append({
                    "id": str(row["id"]),
                    "title": row["title"] or f"Report {row['id']}",
                    "name": row["title"] or f"Report {row['id']}",
                    "type": row["report_type"] or "Custom",
                    "format": row["format"] or "PDF",
                    "status": "completed",
                    "created_by": str(row["created_by"]) if row["created_by"] else "",
                    "date": created_at_str,
                    "created_at": created_at_str,
                    "download_url": "",
                })
    return {"reports": rows_data}


# ===== System Inventory Endpoints =====

@router.get("/api/v1/inventory/summary")
async def get_inventory_summary(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    org_id = current_user.org_id
    result = {
        "total_devices": 0, "online_devices": 0, "offline_devices": 0, "idle_devices": 0,
        "os_breakdown": [], "total_cpu_cores": 0, "total_ram_gb": 0,
        "total_disk_gb": 0, "avg_cpu_cores": 0, "avg_ram_gb": 0, "avg_disk_gb": 0,
        "software_count": 0, "service_count": 0, "unpatched_count": 0,
    }
    if not app_state.db_pool or not org_id:
        return result
    async with app_state.db_pool.acquire() as conn:
        agents = await conn.fetch(
            "SELECT agent_id, hostname, os, is_online, metadata FROM agents WHERE organization_id = $1::uuid", org_id,
        )
        result["total_devices"] = len(agents)
        os_count: Dict[str, int] = {}
        total_cores = total_ram = total_disk = 0.0
        online = offline = idle = software_count = service_count = 0
        for a in agents:
            if a["is_online"]: online += 1
            else: offline += 1
            os_name = a["os"] or "Unknown"
            os_count[os_name] = os_count.get(os_name, 0) + 1
            meta = a["metadata"]
            if meta and isinstance(meta, dict):
                total_cores += meta.get("cpu_cores", 0) or 0
                total_ram += meta.get("total_ram_gb", 0) or 0.0
                total_disk += meta.get("total_disk_gb", 0) or 0.0
                sw = meta.get("installed_software", [])
                if sw: software_count += len(sw)
                svc = meta.get("running_services", [])
                if svc: service_count += len(svc)
        result["online_devices"] = online
        result["offline_devices"] = offline
        result["idle_devices"] = idle
        result["os_breakdown"] = [{"os": k, "count": v} for k, v in os_count.items()]
        result["total_cpu_cores"] = int(total_cores)
        result["total_ram_gb"] = round(total_ram, 1)
        result["total_disk_gb"] = round(total_disk, 1)
        if result["total_devices"] > 0:
            result["avg_cpu_cores"] = round(total_cores / result["total_devices"], 1)
            result["avg_ram_gb"] = round(total_ram / result["total_devices"], 1)
            result["avg_disk_gb"] = round(total_disk / result["total_devices"], 1)
        result["software_count"] = software_count
        result["service_count"] = service_count
    return result


@router.get("/api/v1/inventory/detail/{agent_id}")
async def get_inventory_detail(
    agent_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(503, "Database not available")
    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT agent_id, hostname, os, ip_address, metadata FROM agents WHERE agent_id = $1", agent_id,
        )
        if not row:
            raise HTTPException(404, "Agent not found")
        meta = row["metadata"] or {} if isinstance(row["metadata"], dict) else {}
        metrics_row = await conn.fetchrow(
            """SELECT cpu_percent, memory_percent, memory_available_gb,
                      disk_usage_percent, uptime_seconds
               FROM system_metrics WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1""",
            agent_id,
        )
        return {
            "agent_id": row["agent_id"], "hostname": row["hostname"] or "",
            "os": row["os"] or "", "os_version": meta.get("os_version", ""),
            "os_build": meta.get("os_build", ""), "cpu_model": meta.get("cpu_model", ""),
            "cpu_cores": meta.get("cpu_cores", 0), "cpu_threads": meta.get("cpu_threads", 0),
            "cpu_architecture": meta.get("cpu_architecture", ""),
            "total_ram_gb": meta.get("total_ram_gb", 0),
            "total_disk_gb": meta.get("total_disk_gb", 0),
            "used_disk_gb": meta.get("used_disk_gb", 0),
            "free_disk_gb": meta.get("free_disk_gb", 0),
            "ip_address": row["ip_address"] or "", "mac_address": meta.get("mac_address", ""),
            "last_boot": meta.get("last_boot", ""),
            "last_inventory_update": meta.get("last_inventory_update", ""),
            "installed_software": meta.get("installed_software", []),
            "network_interfaces": meta.get("network_interfaces", []),
            "running_services": meta.get("running_services", []),
        }


# ===== Device Health Endpoints =====

@router.get("/api/v1/health/devices")
async def get_health_devices(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    org_id = current_user.org_id
    devices = []
    if not app_state.db_pool or not org_id:
        return {"devices": devices}
    async with app_state.db_pool.acquire() as conn:
        agents = await conn.fetch(
            "SELECT agent_id, hostname, is_online FROM agents WHERE organization_id = $1::uuid", org_id,
        )
        for a in agents:
            metrics_row = await conn.fetchrow(
                """SELECT cpu_percent, memory_percent, disk_usage_percent, uptime_seconds,
                          process_count, thread_count
                   FROM system_metrics WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1""",
                a["agent_id"],
            )
            hb_row = await conn.fetchrow(
                "SELECT timestamp FROM agent_heartbeats WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1",
                a["agent_id"],
            )
            alert_count = await conn.fetchval(
                "SELECT COUNT(*) FROM alerts WHERE agent_id = $1 AND acknowledged = false",
                a["agent_id"],
            )
            cpu_pct = metrics_row["cpu_percent"] if metrics_row else 0
            mem_pct = metrics_row["memory_percent"] if metrics_row else 0
            disk_pct = metrics_row["disk_usage_percent"] if metrics_row else 0
            uptime = metrics_row["uptime_seconds"] if metrics_row else 0
            proc_count = metrics_row["process_count"] if metrics_row else 0
            health_score = await _compute_health_score(conn, a["agent_id"])
            if not a["is_online"]:
                status = "offline"; health_score = 0
            elif health_score >= 70: status = "healthy"
            elif health_score >= 40: status = "warning"
            else: status = "critical"
            devices.append({
                "agent_id": a["agent_id"], "hostname": a["hostname"] or a["agent_id"],
                "status": status, "health_score": health_score,
                "cpu_usage_percent": round(float(cpu_pct or 0), 1),
                "memory_usage_percent": round(float(mem_pct or 0), 1),
                "disk_usage_percent": round(float(disk_pct or 0), 1),
                "uptime_seconds": uptime or 0,
                "last_heartbeat": hb_row["timestamp"].isoformat() if hb_row else "",
                "active_alerts": alert_count or 0, "process_count": proc_count or 0,
                "thread_count": metrics_row["thread_count"] if metrics_row else 0,
                "handle_count": 0,
                "performance_index": round(max(0, 1 - (cpu_pct or 0) / 200), 2),
                "stability_score": round(min(1, max(0, health_score / 100)), 2),
            })
    return {"devices": devices}


@router.get("/api/v1/health/detail/{agent_id}")
async def get_health_detail(
    agent_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(503, "Database not available")
    async with app_state.db_pool.acquire() as conn:
        a = await conn.fetchrow(
            "SELECT agent_id, hostname, is_online FROM agents WHERE agent_id = $1", agent_id,
        )
        if not a:
            raise HTTPException(404, "Agent not found")
        metrics_row = await conn.fetchrow(
            """SELECT cpu_percent, memory_percent, disk_usage_percent, uptime_seconds,
                      process_count, thread_count
               FROM system_metrics WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1""",
            agent_id,
        )
        hb_row = await conn.fetchrow(
            "SELECT timestamp FROM agent_heartbeats WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1",
            agent_id,
        )
        alert_count = await conn.fetchval(
            "SELECT COUNT(*) FROM alerts WHERE agent_id = $1 AND acknowledged = false",
            agent_id,
        )
        cpu_pct = metrics_row["cpu_percent"] if metrics_row else 0
        mem_pct = metrics_row["memory_percent"] if metrics_row else 0
        disk_pct = metrics_row["disk_usage_percent"] if metrics_row else 0
        uptime = metrics_row["uptime_seconds"] if metrics_row else 0
        proc_count = metrics_row["process_count"] if metrics_row else 0
        thread_count = metrics_row["thread_count"] if metrics_row else 0
        health_score = await _compute_health_score(conn, agent_id)
        if not a["is_online"]:
            status = "offline"; health_score = 0
        elif health_score >= 70: status = "healthy"
        elif health_score >= 40: status = "warning"
        else: status = "critical"
        return {
            "agent_id": a["agent_id"], "hostname": a["hostname"] or a["agent_id"],
            "status": status, "health_score": health_score,
            "cpu_usage_percent": round(float(cpu_pct or 0), 1),
            "memory_usage_percent": round(float(mem_pct or 0), 1),
            "disk_usage_percent": round(float(disk_pct or 0), 1),
            "uptime_seconds": uptime or 0,
            "last_heartbeat": hb_row["timestamp"].isoformat() if hb_row else "",
            "active_alerts": alert_count or 0, "process_count": proc_count or 0,
            "thread_count": thread_count or 0, "handle_count": 0,
            "performance_index": round(max(0, 1 - (cpu_pct or 0) / 200), 2),
            "stability_score": round(min(1, max(0, health_score / 100)), 2),
        }


@router.get("/api/v1/health/anomalies")
async def get_health_anomalies(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    org_id = current_user.org_id
    anomalies = []
    if not app_state.db_pool or not org_id:
        return {"anomalies": anomalies}
    async with app_state.db_pool.acquire() as conn:
        agents = await conn.fetch(
            "SELECT agent_id, hostname FROM agents WHERE organization_id = $1::uuid", org_id,
        )
        for a in agents:
            metrics_row = await conn.fetchrow(
                """SELECT cpu_percent, memory_percent, disk_usage_percent
                   FROM system_metrics WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1""",
                a["agent_id"],
            )
            if not metrics_row: continue
            aid = a["agent_id"]; hname = a["hostname"] or aid
            cpu = metrics_row["cpu_percent"] or 0
            mem = metrics_row["memory_percent"] or 0
            disk = metrics_row["disk_usage_percent"] or 0
            ts = datetime.now(timezone.utc).isoformat()
            if cpu > 90:
                anomalies.append({"id": f"{aid}-cpu", "agent_id": aid, "hostname": hname,
                    "type": "cpu", "severity": "critical", "message": f"CPU usage at {cpu:.0f}%",
                    "value": cpu, "threshold": 90, "detected_at": ts, "acknowledged": False})
            elif cpu > 80:
                anomalies.append({"id": f"{aid}-cpu-warn", "agent_id": aid, "hostname": hname,
                    "type": "cpu", "severity": "warning", "message": f"CPU usage at {cpu:.0f}%",
                    "value": cpu, "threshold": 80, "detected_at": ts, "acknowledged": False})
            if mem > 90:
                anomalies.append({"id": f"{aid}-mem", "agent_id": aid, "hostname": hname,
                    "type": "memory", "severity": "critical", "message": f"Memory usage at {mem:.0f}%",
                    "value": mem, "threshold": 90, "detected_at": ts, "acknowledged": False})
            elif mem > 80:
                anomalies.append({"id": f"{aid}-mem-warn", "agent_id": aid, "hostname": hname,
                    "type": "memory", "severity": "warning", "message": f"Memory usage at {mem:.0f}%",
                    "value": mem, "threshold": 80, "detected_at": ts, "acknowledged": False})
            if disk > 90:
                anomalies.append({"id": f"{aid}-disk", "agent_id": aid, "hostname": hname,
                    "type": "disk", "severity": "critical", "message": f"Disk usage at {disk:.0f}%",
                    "value": disk, "threshold": 90, "detected_at": ts, "acknowledged": False})
    return {"anomalies": anomalies}


# ===== Executive Overview Endpoints =====

@router.get("/api/v1/executive/summary")
async def get_executive_summary(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    org_id = current_user.org_id
    result = {
        "total_devices": 0, "online_devices": 0, "offline_devices": 0, "idle_devices": 0,
        "total_users": 0, "active_users_today": 0, "total_teams": 0,
        "total_organizations": 0, "overall_health_score": 100,
        "avg_productivity": 0, "productivity_trend": "stable",
        "alerts_active": 0, "alerts_critical": 0,
        "total_uptime_hours": 0, "avg_uptime_per_device_hours": 0,
        "top_performers": [], "needs_attention": [],
        "weekly_comparison": {}, "department_breakdown": [],
    }
    if not app_state.db_pool or not org_id:
        return result
    async with app_state.db_pool.acquire() as conn:
        agents = await conn.fetch(
            "SELECT agent_id, hostname, is_online FROM agents WHERE organization_id = $1::uuid", org_id,
        )
        result["total_devices"] = len(agents)
        result["online_devices"] = sum(1 for a in agents if a["is_online"])
        result["offline_devices"] = result["total_devices"] - result["online_devices"]
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE organization_id = $1::uuid", org_id)
        result["total_users"] = user_count or 0
        team_count = await conn.fetchval("SELECT COUNT(*) FROM teams WHERE organization_id = $1::uuid", org_id)
        result["total_teams"] = team_count or 0
        active_today = await conn.fetchval(
            """SELECT COUNT(DISTINCT agent_id) FROM agent_heartbeats
               WHERE agent_id IN (SELECT agent_id FROM agents WHERE organization_id = $1::uuid)
               AND timestamp >= CURRENT_DATE""", org_id,
        )
        result["active_users_today"] = active_today or 0
        alert_active = await conn.fetchval(
            "SELECT COUNT(*) FROM alerts WHERE organization_id = $1::uuid AND acknowledged = false", org_id,
        )
        result["alerts_active"] = alert_active or 0
        alert_critical = await conn.fetchval(
            "SELECT COUNT(*) FROM alerts WHERE organization_id = $1::uuid AND severity = 'critical' AND acknowledged = false", org_id,
        )
        result["alerts_critical"] = alert_critical or 0
        prod_row = await conn.fetchrow(
            "SELECT AVG(score) as avg_score FROM productivity_scores WHERE organization_id = $1::uuid AND date >= CURRENT_DATE - 7",
            org_id,
        )
        avg_prod = prod_row["avg_score"] if prod_row and prod_row["avg_score"] else 0
        result["avg_productivity"] = round(float(avg_prod), 1)
        health_scores, total_uptime, top_perf, needs_attn = [], 0, [], []
        for a in agents:
            hs = await _compute_health_score(conn, a["agent_id"])
            health_scores.append(hs)
            metrics_row = await conn.fetchrow(
                "SELECT uptime_seconds FROM system_metrics WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1",
                a["agent_id"],
            )
            uptime = metrics_row["uptime_seconds"] if metrics_row else 0
            total_uptime += uptime
            if hs >= 80 and a["is_online"]:
                top_perf.append({"agent_id": a["agent_id"], "hostname": a["hostname"] or a["agent_id"], "score": round(hs, 1)})
            if hs < 40 or not a["is_online"]:
                issue = "Offline" if not a["is_online"] else f"Health score: {hs:.0f}%"
                severity = "critical" if (hs < 20 or not a["is_online"]) else "warning"
                needs_attn.append({"agent_id": a["agent_id"], "hostname": a["hostname"] or a["agent_id"], "issue": issue, "severity": severity})
        result["overall_health_score"] = round(sum(health_scores) / len(health_scores), 1) if health_scores else 0
        result["total_uptime_hours"] = round(total_uptime / 3600, 1)
        result["avg_uptime_per_device_hours"] = round(total_uptime / max(len(agents), 1) / 3600, 1)
        result["top_performers"] = sorted(top_perf, key=lambda x: x["score"], reverse=True)[:5]
        result["needs_attention"] = sorted(needs_attn, key=lambda x: x["severity"])[:10]
        this_week = await conn.fetchrow(
            "SELECT AVG(score) as avg_score FROM productivity_scores WHERE organization_id = $1::uuid AND date >= CURRENT_DATE - 7",
            org_id,
        )
        prev_week = await conn.fetchrow(
            "SELECT AVG(score) as avg_score FROM productivity_scores WHERE organization_id = $1::uuid AND date >= CURRENT_DATE - 14 AND date < CURRENT_DATE - 7",
            org_id,
        )
        current_prod = float(this_week["avg_score"]) if this_week and this_week["avg_score"] else 0
        previous_prod = float(prev_week["avg_score"]) if prev_week and prev_week["avg_score"] else 0
        result["weekly_comparison"] = {
            "current": {"productivity": round(current_prod, 1), "health": round(result["overall_health_score"], 1), "active_users": result["active_users_today"]},
            "previous": {"productivity": round(previous_prod, 1), "health": 0, "active_users": 0},
        }
        if current_prod > previous_prod + 2: result["productivity_trend"] = "improving"
        elif current_prod < previous_prod - 2: result["productivity_trend"] = "declining"
        else: result["productivity_trend"] = "stable"
    return result


# ===== Notifications =====

@router.post("/api/v1/notifications/send")
async def send_notification(
    req: NotificationRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    result = {"in_app": False, "email": False}
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO notifications (user_id, title, message, notification_type, priority)
                   VALUES ($1, $2, $3, $4, $5)""",
                req.user_id, req.title, req.message, req.type, req.priority,
            )
            result["in_app"] = True
    if req.type == "email" and req.email:
        try:
            _send_email(req.email, req.title, req.message)
            result["email"] = True
        except Exception as e:
            app_state.logger.warning("Email send failed: %s", e)
    return {"status": "ok", "result": result}


@router.get("/api/v1/notifications")
async def get_notifications(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    rows_data = []
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, title, message, notification_type, priority, is_read, created_at
                   FROM notifications WHERE user_id = $1::uuid
                   ORDER BY created_at DESC LIMIT $2""",
                current_user.user_id, limit,
            )
            for row in rows:
                rows_data.append({
                    "id": str(row["id"]), "title": row["title"],
                    "message": row["message"], "type": row["notification_type"],
                    "priority": row["priority"], "is_read": row["is_read"],
                    "created_at": row["created_at"].isoformat(),
                })
    return {"notifications": rows_data}


@router.put("/api/v1/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE notifications SET is_read = true WHERE id = $1::uuid AND user_id = $2::uuid",
                notification_id, current_user.user_id,
            )
    return {"status": "ok"}


# ===== Reports =====

@router.post("/api/v1/reports/generate")
async def generate_report(
    req: ReportRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    report_id = str(uuid.uuid4())
    report_dir = Path(os.environ.get("EPMS_REPORT_DIR", "reports"))
    report_dir.mkdir(exist_ok=True)
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO reports (id, organization_id, report_type, title, format,
                   filters, created_by, created_at)
                   VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, NOW())""",
                report_id, current_user.org_id, req.type, req.report_title,
                req.format, json.dumps(req.model_dump()), current_user.user_id,
            )
    background_tasks.add_task(_build_report_file, report_id, req, app_state.db_pool, report_dir)
    return {"report_id": report_id, "status": "generating", "message": f"Report '{req.report_title}' is being generated"}


@router.get("/api/v1/reports/{report_id}")
async def get_report_status(
    report_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    if not app_state.db_pool:
        raise HTTPException(503, "Database not available")
    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, report_type, title, format, created_at, status, file_path "
            "FROM reports WHERE id = $1::uuid", report_id,
        )
        if not row:
            raise HTTPException(404, "Report not found")
        return {
            "id": str(row["id"]), "title": row["title"],
            "type": row["report_type"], "format": row["format"],
            "created_at": row["created_at"].isoformat(),
            "status": row["status"] or "completed",
            "download_url": f"/api/v1/reports/{report_id}/download" if row.get("file_path") else None,
        }


@router.get("/api/v1/reports/{report_id}/download")
async def download_report(
    report_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    if not app_state.db_pool:
        raise HTTPException(503, "Database not available")
    report_dir = Path(os.environ.get("EPMS_REPORT_DIR", "reports")).resolve()
    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT format, file_path FROM reports WHERE id = $1::uuid", report_id,
        )
        if not row or not row.get("file_path"):
            raise HTTPException(404, "Report file not found")
        file_path = Path(row["file_path"]).resolve()
        if not str(file_path).startswith(str(report_dir)):
            raise HTTPException(403, "Access denied")
        if not file_path.exists():
            raise HTTPException(404, "Report file not found on disk")
        media_type = {"csv": "text/csv", "html": "text/html"}.get(row["format"], "application/octet-stream")
        return FileResponse(str(file_path), media_type=media_type, filename=file_path.name)


# ===== Teams / Users / Organizations / Productivity Rules =====

@router.get("/api/v1/teams")
async def get_teams(current_user: AuthContext = Depends(get_current_user)):
    teams = []
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            if current_user.role in ("admin", "super_admin"):
                rows = await conn.fetch("SELECT id, name, description, organization_id, created_at FROM teams ORDER BY name")
            else:
                rows = await conn.fetch(
                    "SELECT id, name, description, organization_id, created_at FROM teams WHERE organization_id = $1::uuid ORDER BY name",
                    current_user.org_id,
                )
            for row in rows:
                teams.append({
                    "id": str(row["id"]), "name": row["name"],
                    "description": row["description"] or "",
                    "organization_id": str(row["organization_id"]),
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })
    return {"teams": teams}


@router.get("/api/v1/users")
async def get_users(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    users = []
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            if current_user.role in ("admin", "super_admin"):
                rows = await conn.fetch(
                    """SELECT u.id, u.email, u.display_name, u.role, u.organization_id, u.is_active, u.last_login
                       FROM users u ORDER BY u.display_name"""
                )
            else:
                rows = await conn.fetch(
                    """SELECT u.id, u.email, u.display_name, u.role, u.organization_id, u.is_active, u.last_login
                       FROM users u WHERE u.organization_id = $1::uuid ORDER BY u.display_name""",
                    current_user.org_id,
                )
            for row in rows:
                users.append({
                    "id": str(row["id"]), "email": row["email"],
                    "display_name": row["display_name"] or row["email"].split("@")[0],
                    "role": row["role"],
                    "organization_id": str(row["organization_id"]) if row["organization_id"] else "",
                    "is_active": row["is_active"],
                    "last_login": row["last_login"].isoformat() if row["last_login"] else None,
                })
    return {"users": users}


@router.get("/api/v1/organizations")
async def get_organizations(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("admin")),
):
    orgs = []
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, display_name, created_at FROM organizations ORDER BY name")
            for row in rows:
                display_name = row["display_name"] or row["name"]
                orgs.append({
                    "id": str(row["id"]), "name": row["name"],
                    "display_name": display_name, "domain": display_name,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })
    return {"organizations": orgs}


@router.get("/api/v1/productivity-rules")
async def get_productivity_rules(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    rules = []
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            if current_user.role in ("admin", "super_admin"):
                rows = await conn.fetch(
                    "SELECT id, organization_id, pattern, category, rule_type, description, is_active, created_at "
                    "FROM productivity_rules ORDER BY category, pattern"
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, organization_id, pattern, category, rule_type, description, is_active, created_at "
                    "FROM productivity_rules WHERE organization_id = $1::uuid ORDER BY category, pattern",
                    current_user.org_id,
                )
            for row in rows:
                rules.append({
                    "id": str(row["id"]),
                    "organization_id": str(row["organization_id"]),
                    "pattern": row["pattern"], "category": row["category"],
                    "rule_type": row["rule_type"] or "glob",
                    "description": row["description"] or "",
                    "is_active": row["is_active"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })
    return {"rules": rules}


@router.post("/api/v1/productivity-rules")
async def create_productivity_rule(
    req: ProductivityRuleRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    rule_id = str(uuid.uuid4())
    async with app_state.db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO productivity_rules (id, organization_id, pattern, category, rule_type, description)
               VALUES ($1, $2::uuid, $3, $4, $5, $6)""",
            rule_id, current_user.org_id, req.pattern, req.category, req.rule_type, req.description,
        )
    return {"id": rule_id, "status": "created"}


@router.put("/api/v1/productivity-rules/{rule_id}")
async def update_productivity_rule(
    rule_id: str,
    req: ProductivityRuleRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with app_state.db_pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE productivity_rules SET pattern=$1, category=$2, rule_type=$3, description=$4
               WHERE id=$5::uuid AND organization_id=$6::uuid""",
            req.pattern, req.category, req.rule_type, req.description, rule_id, current_user.org_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "updated"}


@router.delete("/api/v1/productivity-rules/{rule_id}")
async def delete_productivity_rule(
    rule_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with app_state.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM productivity_rules WHERE id=$1::uuid AND organization_id=$2::uuid",
            rule_id, current_user.org_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}


# ===== WebSocket Endpoints =====

@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        handshake = await asyncio.wait_for(websocket.receive_text(), timeout=10)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Authentication timeout"})
        await websocket.close(code=1008)
        return
    except WebSocketDisconnect:
        return

    try:
        handshake_data = json.loads(handshake)
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid auth message"})
        await websocket.close(code=1008)
        return

    api_key = handshake_data.get("api_key", "")
    agent_id = handshake_data.get("agent_id", "")
    display_name = handshake_data.get("display_name", "")

    if not api_key or not agent_id:
        await websocket.send_json({"type": "error", "message": "api_key and agent_id required"})
        await websocket.close(code=1008)
        return

    key_hash = hash_api_key(api_key)
    is_valid = False
    if app_state.db_pool:
        async with app_state.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT agent_id FROM agents WHERE api_key_hash = $1 AND is_active = true", key_hash,
            )
            if row:
                is_valid = True
                agent_id = row["agent_id"]

    if not is_valid:
        key_hash2 = hashlib.sha256(api_key.encode()).hexdigest()
        if app_state.db_pool:
            async with app_state.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM configuration WHERE key = 'enrollment_token' AND value::text = $1 LIMIT 1",
                    key_hash2,
                )
                if row:
                    is_valid = True

    if not is_valid:
        await websocket.send_json({"type": "error", "message": "Invalid API key"})
        await websocket.close(code=1008)
        return

    await app_state.ws_manager.connect_agent(agent_id, websocket, {"display_name": display_name, "agent_id": agent_id})

    try:
        await websocket.send_json({
            "type": "connected", "agent_id": agent_id,
            "heartbeat_interval_seconds": 30, "protocol_version": "1.0",
        })
        if app_state.db_pool:
            async with app_state.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agents SET is_online = true, last_heartbeat = NOW() WHERE agent_id = $1", agent_id,
                )

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")
                msg_data = msg.get("data", {})

                if msg_type == "heartbeat":
                    fg = msg_data.get("foreground_window") or msg_data.get("active_window", {})
                    if app_state.db_pool:
                        async with app_state.db_pool.acquire() as conn:
                            await conn.execute(
                                """INSERT INTO agent_heartbeats
                                   (agent_id, timestamp, afk_seconds, is_afk,
                                    active_window_title, active_window_process,
                                    cpu_percent, memory_percent, memory_available_gb, uptime_seconds)
                                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                                agent_id,
                                msg_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                                msg_data.get("afk_seconds", 0), msg_data.get("is_afk", False),
                                fg.get("title", ""), fg.get("process_name", ""),
                                msg_data.get("system", {}).get("cpu", {}).get("percent"),
                                msg_data.get("system", {}).get("memory", {}).get("percent"),
                                msg_data.get("system", {}).get("memory", {}).get("available_gb"),
                                msg_data.get("system", {}).get("uptime_seconds"),
                            )
                            processes = msg_data.get("processes", [])
                            if processes:
                                ts = msg_data.get("timestamp", datetime.now(timezone.utc).isoformat())
                                for proc in processes:
                                    try:
                                        await conn.execute(
                                            """INSERT INTO process_events
                                               (agent_id, timestamp, process_name, process_path, pid, parent_pid,
                                                cpu_percent, memory_percent, is_foreground, window_title, username)
                                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                                            agent_id, ts, proc.get("process_name", ""),
                                            proc.get("process_path", ""), proc.get("pid", 0),
                                            proc.get("ppid", 0), proc.get("cpu_percent", 0),
                                            proc.get("memory_percent", 0), proc.get("is_foreground", False),
                                            proc.get("window_title", ""), proc.get("username", ""),
                                        )
                                    except Exception:
                                        pass
                    await app_state.ws_manager.broadcast_to_dashboards("heartbeat", {
                        "agent_id": agent_id, "timestamp": msg_data.get("timestamp"),
                        "is_afk": msg_data.get("is_afk", False), "active_window": fg.get("title", ""),
                    })
                    await app_state.ws_manager.update_last_message(agent_id)
                    await websocket.send_json({"type": "heartbeat_ack", "timestamp": datetime.now(timezone.utc).isoformat()})

                elif msg_type == "browser_activity" and app_state.db_pool:
                    async with app_state.db_pool.acquire() as conn:
                        await conn.execute(
                            """INSERT INTO browser_activity
                               (agent_id, timestamp, browser_name, domain, url, page_title, category, is_active)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, true)""",
                            agent_id, msg_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                            msg_data.get("browser_name", ""), msg_data.get("domain", ""),
                            msg_data.get("url", ""), msg_data.get("page_title", ""),
                            msg_data.get("category", "uncategorized"),
                        )
                    await websocket.send_json({"type": "browser_ack"})

                elif msg_type == "editor_activity" and app_state.db_pool:
                    async with app_state.db_pool.acquire() as conn:
                        await conn.execute(
                            """INSERT INTO editor_activity
                               (agent_id, timestamp, editor_name, project_name, file_name, file_extension, language, is_focused)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, true)""",
                            agent_id, msg_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                            msg_data.get("editor_name", ""), msg_data.get("project_name", ""),
                            msg_data.get("file_name", ""), msg_data.get("file_extension", ""),
                            msg_data.get("language", ""),
                        )
                    await websocket.send_json({"type": "editor_ack"})

                elif msg_type == "pong":
                    pass
                else:
                    await websocket.send_json({"type": "ack", "original_type": msg_type})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        pass
    finally:
        await app_state.ws_manager.disconnect_agent(agent_id)
        if app_state.db_pool:
            async with app_state.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agents SET is_online = false WHERE agent_id = $1", agent_id,
                )


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket, token: str = Query("")):
    await websocket.accept()
    if not token:
        await websocket.send_json({"type": "error", "message": "Missing token"})
        await websocket.close(code=1008)
        return
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        session_id = payload.get("jti", token[:16])
    except HTTPException as e:
        await websocket.send_json({"type": "error", "message": e.detail or "Invalid token"})
        await websocket.close(code=1008)
        return
    await app_state.ws_manager.connect_dashboard(session_id, websocket)
    await websocket.send_json({"type": "connected", "session_id": session_id})
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await app_state.ws_manager.disconnect_dashboard(session_id)