import os
import json
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, Header

from routes.models import (
    AgentRegister, AgentHeartbeat, BrowserEvent, EditorEvent, BatchEvents,
    EnrollmentTokenRequest,
)
from routes.helpers import (
    _parse_ts, hash_api_key, verify_api_key, validate_agent_identity,
    check_agent_rate_limit, get_db,
)
import routes.state as app_state

from epms_server.config import ENROLLMENT_MODE
from epms_server.rbac import AuthContext, get_current_user, require_role

router = APIRouter()


@router.post("/api/v1/agent/register")
async def register_agent(
    agent: AgentRegister,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    agent_id = agent_identity["agent_id"]
    enrollment_mode = agent_identity.get("agent_id") == ENROLLMENT_MODE

    if enrollment_mode:
        agent_id = str(uuid.uuid4())

    agent_api_key = f"epms_{agent_id[:8]}_{secrets.token_hex(24)}"
    api_key_hash = hash_api_key(agent_api_key)

    if app_state.db_pool:
        org_id = agent_identity.get("organization_id", "")
        async with app_state.db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM agents WHERE agent_id = $1", agent_id
            )
            if not existing:
                await conn.execute(
                    """INSERT INTO agents
                       (agent_id, organization_id, display_name, hostname, os, version, api_key_hash,
                        is_online, is_enrolled, enrolled_at, last_heartbeat, metadata)
                       VALUES ($1, $2::uuid, $3, $4, $5, $6, $7,
                               true, true, NOW(), NOW(), $8)""",
                    agent_id, org_id, agent.display_name, agent.hostname, agent.os,
                    agent.version, api_key_hash,
                    json.dumps({"capabilities": agent.capabilities}),
                )
            else:
                await conn.execute(
                    """UPDATE agents SET organization_id=$2::uuid, display_name=$3, hostname=$4, os=$5,
                       version=$6, api_key_hash=$7, is_online=true,
                       is_enrolled=true, last_heartbeat=NOW()
                       WHERE agent_id=$1""",
                    agent_id, org_id, agent.display_name, agent.hostname, agent.os,
                    agent.version, api_key_hash,
                )

    if app_state.redis_client:
        await app_state.redis_client.set(
            f"agent:{agent_id}",
            json.dumps({
                "display_name": agent.display_name,
                "hostname": agent.hostname,
                "os": agent.os,
                "version": agent.version,
                "capabilities": agent.capabilities,
            }),
            ex=86400,
        )

    return {
        "agent_id": agent_id,
        "api_key": agent_api_key,
        "status": "registered",
        "message": f"Agent '{agent.display_name or agent_id}' registered successfully",
        "api_endpoint": "/api/v1/agent/heartbeat",
    }


@router.post("/api/v1/admin/enrollment-token")
async def create_enrollment_token(
    req: EnrollmentTokenRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("admin")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    org_id = req.organization_id or str(current_user.org_id)
    if not org_id:
        raise HTTPException(status_code=400, detail="organization_id is required")

    raw_token = f"epms_enroll_{secrets.token_hex(32)}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    async with app_state.db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO configuration (organization_id, scope, key, value, description)
               VALUES ($1, 'organization', 'enrollment_token', $2::jsonb, $3)
               ON CONFLICT (organization_id, scope, key)
               DO UPDATE SET value = $2::jsonb, description = $3, updated_at = NOW()""",
            org_id, json.dumps(token_hash), req.description,
        )

    return {
        "enrollment_token": raw_token,
        "organization_id": org_id,
        "description": req.description,
        "warning": "This token will not be shown again. Store it securely.",
    }


@router.post("/api/v1/admin/enrollment-token/revoke")
async def revoke_enrollment_token(
    organization_id: Optional[str] = None,
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("admin")),
):
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    org_id = organization_id or str(current_user.org_id)

    async with app_state.db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM configuration WHERE organization_id = $1::uuid AND key = 'enrollment_token'",
            org_id,
        )

    return {"status": "revoked", "organization_id": org_id}


@router.post("/api/v1/agent/heartbeat")
async def receive_heartbeat(
    heartbeat: AgentHeartbeat,
    agent_identity: Dict[str, Any] = Depends(check_agent_rate_limit),
):
    agent_id = agent_identity["agent_id"]

    if app_state.db_pool and agent_id != "unknown":
        async with app_state.db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE agents SET is_online=true, last_heartbeat=NOW()
                   WHERE agent_id=$1""",
                agent_id,
            )
            await conn.execute(
                """INSERT INTO agent_heartbeats
                   (agent_id, timestamp, afk_seconds, is_afk,
                    active_window_title, active_window_process,
                    cpu_percent, memory_percent, memory_available_gb, uptime_seconds)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                agent_id,
                _parse_ts(heartbeat.timestamp),
                heartbeat.afk_seconds,
                heartbeat.is_afk,
                (heartbeat.foreground_window or heartbeat.active_window).get("title", ""),
                (heartbeat.foreground_window or heartbeat.active_window).get("process", ""),
                heartbeat.system.get("cpu", {}).get("percent"),
                heartbeat.system.get("memory", {}).get("percent"),
                heartbeat.system.get("memory", {}).get("available_gb"),
                heartbeat.system.get("uptime_seconds"),
            )

            if heartbeat.processes:
                for proc in heartbeat.processes:
                    try:
                        await conn.execute(
                            """INSERT INTO process_events
                               (agent_id, timestamp, process_name, process_path, pid, parent_pid,
                                cpu_percent, memory_percent, is_foreground, window_title, username, cmd_line)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
                            agent_id,
                            _parse_ts(heartbeat.timestamp),
                            proc.get("process_name", ""),
                            proc.get("process_path", ""),
                            proc.get("pid", 0),
                            proc.get("ppid", 0),
                            proc.get("cpu_percent", 0),
                            proc.get("memory_percent", 0),
                            proc.get("is_foreground", False),
                            proc.get("window_title", ""),
                            proc.get("username", ""),
                            proc.get("cmd_line", ""),
                        )
                    except Exception as e:
                        app_state.logger.debug("Process event insert error: %s", e)

            if heartbeat.browser_activity:
                await conn.execute(
                    """INSERT INTO browser_activity
                       (agent_id, timestamp, browser_name, domain, url, page_title, category, is_active)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, true)""",
                    agent_id,
                    _parse_ts(heartbeat.browser_activity.get("timestamp", heartbeat.timestamp)),
                    heartbeat.browser_activity.get("browser_name", ""),
                    heartbeat.browser_activity.get("domain", ""),
                    heartbeat.browser_activity.get("url", ""),
                    heartbeat.browser_activity.get("page_title", ""),
                    heartbeat.browser_activity.get("category", "uncategorized"),
                )

            if heartbeat.editor_activity:
                await conn.execute(
                    """INSERT INTO editor_activity
                       (agent_id, timestamp, editor_name, project_name,
                        file_name, file_extension, language, is_focused)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, true)""",
                    agent_id,
                    _parse_ts(heartbeat.editor_activity.get("timestamp", heartbeat.timestamp)),
                    heartbeat.editor_activity.get("editor_name", ""),
                    heartbeat.editor_activity.get("project_name", ""),
                    heartbeat.editor_activity.get("file_name", ""),
                    heartbeat.editor_activity.get("file_extension", ""),
                    heartbeat.editor_activity.get("language", ""),
                )

    return {
        "status": "ok",
        "agent_id": agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api/v1/agent/browser")
async def receive_browser_event(
    event: BrowserEvent,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    agent_id = agent_identity["agent_id"]
    if app_state.db_pool and agent_id != "unknown":
        try:
            async with app_state.db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO browser_activity
                       (agent_id, timestamp, browser_name, domain, url, page_title, category, is_productive, is_active)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true)""",
                    agent_id, _parse_ts(event.timestamp), event.browser_name, event.domain,
                    event.url, event.page_title, event.category, event.is_productive,
                )
        except Exception as e:
            app_state.logger.exception(f"Failed to store browser event for agent {agent_id}: {e}")
    return {"status": "ok"}


@router.post("/api/v1/agent/editor")
async def receive_editor_event(
    event: EditorEvent,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    agent_id = agent_identity["agent_id"]
    if app_state.db_pool and agent_id != "unknown":
        try:
            async with app_state.db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO editor_activity
                       (agent_id, timestamp, editor_name, project_name,
                        file_name, file_extension, language, is_focused)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, true)""",
                    agent_id, _parse_ts(event.timestamp), event.editor_name, event.project_name,
                    event.file_name, event.file_extension, event.language,
                )
        except Exception as e:
            app_state.logger.exception(f"Failed to store editor event for agent {agent_id}: {e}")
    return {"status": "ok"}


@router.post("/api/v1/agent/events/batch")
async def receive_batch_events(
    batch: BatchEvents,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    agent_id = agent_identity["agent_id"]
    app_state.logger.info(f"Received batch of {len(batch.events)} events from agent {agent_id}")
    return {"status": "ok", "count": len(batch.events), "agent_id": agent_id}


@router.get("/api/v1/agent/config")
async def get_agent_config(
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    return {
        "monitoring": {
            "heartbeat_interval_seconds": 30,
            "browser_monitoring_enabled": True,
            "editor_monitoring_enabled": True,
            "afk_timeout_minutes": 5,
            "offline_cache_hours": 24,
        },
        "privacy": {
            "collect_window_titles": True,
            "collect_urls": True,
            "collect_file_names": True,
        },
    }


@router.get("/api/v1/agent/policies")
async def get_agent_policies(
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    return {
        "policies": [
            {
                "id": "policy-default",
                "name": "Default Monitoring Policy",
                "rules": [
                    {"type": "monitoring", "enabled": True},
                    {"type": "browser", "enabled": True, "blacklist": []},
                    {"type": "editor", "enabled": True},
                ],
            }
        ]
    }


@router.post("/api/v1/agent/metrics")
async def receive_metrics(
    metrics: Dict[str, Any],
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    agent_id = agent_identity["agent_id"]
    if app_state.db_pool and agent_id != "unknown":
        async with app_state.db_pool.acquire() as conn:
            sys_data = metrics.get("system", {})
            cpu = sys_data.get("cpu", {})
            memory = sys_data.get("memory", {})
            disk = sys_data.get("disk", {})
            await conn.execute(
                """INSERT INTO system_metrics
                   (agent_id, timestamp, cpu_percent, cpu_frequency_mhz,
                    memory_total_gb, memory_used_gb, memory_percent,
                    disk_total_gb, disk_used_gb, disk_percent,
                    uptime_seconds, processes_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
                agent_id, datetime.now(timezone.utc).isoformat(),
                cpu.get("percent"), cpu.get("frequency_mhz"),
                memory.get("total_gb"),
                round(memory.get("total_gb", 0) * memory.get("percent", 0) / 100, 2),
                memory.get("percent"),
                disk.get("total_gb"),
                round(disk.get("total_gb", 0) * disk.get("percent", 0) / 100, 2),
                disk.get("percent"),
                sys_data.get("uptime_seconds"),
                0,
            )
    return {"status": "ok"}


@router.post("/api/v1/agent/inventory")
async def receive_inventory(
    inventory: Dict[str, Any],
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    agent_id = agent_identity["agent_id"]
    if app_state.db_pool and agent_id != "unknown":
        async with app_state.db_pool.acquire() as conn:
            meta_update = {
                "os_version": inventory.get("os_version", ""),
                "os_build": inventory.get("os_build", ""),
                "cpu_model": inventory.get("cpu_model", ""),
                "cpu_cores": inventory.get("cpu_cores", 0),
                "cpu_threads": inventory.get("cpu_threads", 0),
                "cpu_architecture": inventory.get("cpu_architecture", ""),
                "total_ram_gb": inventory.get("total_ram_gb", 0),
                "total_disk_gb": inventory.get("total_disk_gb", 0),
                "used_disk_gb": inventory.get("used_disk_gb", 0),
                "free_disk_gb": inventory.get("free_disk_gb", 0),
                "mac_address": inventory.get("mac_address", ""),
                "last_boot": inventory.get("last_boot", ""),
                "last_inventory_update": datetime.now(timezone.utc).isoformat(),
                "installed_software": inventory.get("installed_software", []),
                "network_interfaces": inventory.get("network_interfaces", []),
                "running_services": inventory.get("running_services", []),
            }
            row = await conn.fetchrow(
                "SELECT metadata FROM agents WHERE agent_id = $1", agent_id,
            )
            existing_meta = row["metadata"] if row and isinstance(row["metadata"], dict) else {}
            merged = dict(existing_meta)
            merged.update(meta_update)
            await conn.execute(
                "UPDATE agents SET metadata = $1::jsonb WHERE agent_id = $2",
                json.dumps(merged), agent_id,
            )
    return {"status": "ok"}