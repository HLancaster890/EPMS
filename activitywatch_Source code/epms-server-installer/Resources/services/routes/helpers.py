import os
import json
import hashlib
import hmac
import base64
import secrets
import time
import asyncio
import smtplib
import csv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

import asyncpg
from fastapi import HTTPException, Depends, Header, Request, status
from fastapi.responses import FileResponse

try:
    import jwt as pyjwt
except ImportError:
    print("WARNING: PyJWT not installed. Install: pip install pyjwt")
    pyjwt = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

from epms_server import config as _config
from epms_server.config import (
    JWT_SECRET, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS, PASSWORD_HASH_ITERATIONS,
    TOKEN_BLACKLIST_PREFIX, ENROLLMENT_MODE,
    AGENT_RATELIMIT_PREFIX, AGENT_RATELIMIT_PER_MINUTE,
)
from epms_server.rbac import AuthContext, get_current_user, decode_token, require_role, filter_by_role, Role, ROLE_MAP
from epms_server.aggregation import _aggregate_productivity_scores as _agg_scores
import routes.state as app_state

import logging
_log = logging.getLogger("epms.server")


def _parse_ts(ts: str) -> datetime:
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc)


async def get_db():
    if app_state.db_pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
    async with app_state.db_pool.acquire() as conn:
        yield conn


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii").rstrip("=")
    hash_b64 = base64.b64encode(dk).decode("ascii").rstrip("=")
    return f"$pbkdf2-sha256${PASSWORD_HASH_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        parts = password_hash.split("$")
        if len(parts) != 5 or parts[1] != "pbkdf2-sha256":
            _log.warning(f"Unknown hash format: {parts[1] if len(parts) > 1 else 'invalid'}")
            return False
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3] + "==")
        stored_hash = base64.b64decode(parts[4] + "==")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, stored_hash)
    except (ValueError, IndexError, base64.binascii.Error) as e:
        _log.error(f"Password verification error: {e}")
        return False


def hash_api_key(api_key: str) -> str:
    if not app_state._API_KEY_PEPPER:
        app_state._API_KEY_PEPPER = os.environ.get("EPMS_API_KEY_PEPPER", "")
        if not app_state._API_KEY_PEPPER:
            _log.warning("EPMS_API_KEY_PEPPER not set — using weak default. Set a strong random secret!")
            app_state._API_KEY_PEPPER = "epms-api-key-fallback-do-not-use-in-production"
    return hashlib.sha256(f"{app_state._API_KEY_PEPPER}:{api_key}".encode()).hexdigest()


def create_access_token(user_id: str, email: str, role: str, org_id: str = "") -> Tuple[str, int]:
    now = int(time.time())
    expires = now + JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    jti = secrets.token_hex(16)
    payload = {
        "sub": user_id, "email": email, "org_id": org_id, "role": role,
        "iat": now, "exp": expires, "jti": jti, "type": "access",
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires


def create_refresh_token(user_id: str) -> Tuple[str, int]:
    now = int(time.time())
    expires = now + JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    jti = secrets.token_hex(16)
    payload = {
        "sub": user_id, "iat": now, "exp": expires, "jti": jti, "type": "refresh",
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires


async def verify_api_key(
    x_api_key: str = Header(None),
    authorization: str = Header(None),
    request: Request = None,
) -> Dict[str, Any]:
    api_key = x_api_key or ""
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if not app_state.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    key_hash = hash_api_key(api_key)
    async with app_state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT agent_id, display_name, organization_id, is_active "
            "FROM agents WHERE api_key_hash = $1 AND is_active = true",
            key_hash,
        )
        if not row:
            key_hash2 = hashlib.sha256(api_key.encode()).hexdigest()
            row = await conn.fetchrow(
                "SELECT c.organization_id, 'enrollment' as agent_id, 'Enrollment Token' as display_name "
                "FROM configuration c "
                "WHERE c.key = 'enrollment_token' "
                "AND c.value #>> '{}' = $1 "
                "AND c.scope = 'organization' "
                "LIMIT 1",
                key_hash2,
            )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return {
            "agent_id": row["agent_id"],
            "display_name": row["display_name"] or "",
            "organization_id": str(row["organization_id"]),
            "is_active": row.get("is_active", True),
        }


async def validate_agent_identity(
    agent_info: Dict[str, Any] = Depends(verify_api_key),
    x_agent_id: Optional[str] = Header(None),
) -> Dict[str, Any]:
    api_key_agent_id = agent_info.get("agent_id", "")
    if api_key_agent_id == ENROLLMENT_MODE:
        resolved_agent_id = x_agent_id or str(__import__("uuid").uuid4())
        return {**agent_info, "agent_id": resolved_agent_id}
    if x_agent_id and x_agent_id != api_key_agent_id:
        _log.warning(
            f"Agent ID spoofing attempt: header={x_agent_id}, api_key_agent={api_key_agent_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Agent ID mismatch: the provided agent_id is not bound to this API key",
        )
    return agent_info


async def check_agent_rate_limit(agent_identity: Dict[str, Any] = Depends(validate_agent_identity)):
    if app_state.redis_client:
        aid = agent_identity["agent_id"]
        key = f"{AGENT_RATELIMIT_PREFIX}{aid}"
        count = await app_state.redis_client.incr(key)
        if count == 1:
            await app_state.redis_client.expire(key, 60)
        if count > AGENT_RATELIMIT_PER_MINUTE:
            _log.warning(f"Rate limit exceeded for agent {aid}: {count} requests/min")
            raise HTTPException(status_code=429, detail="Rate limit exceeded (60 req/min)")
    return agent_identity


async def _aggregation_worker():
    _log.info("Background aggregation worker started")
    while True:
        try:
            await asyncio.sleep(300)
            if app_state.db_pool:
                await _aggregate_productivity_scores(app_state.db_pool)
                await _aggregate_app_sessions(app_state.db_pool)
                await _purge_process_data(app_state.db_pool)
        except asyncio.CancelledError:
            break
        except Exception as e:
            _log.warning("Aggregation cycle failed: %s", e)


async def _aggregate_productivity_scores(pool):
    try:
        async with pool.acquire() as conn:
            agents = await conn.fetch(
                "SELECT agent_id, organization_id FROM agents WHERE is_online = true"
            )
        for row in agents:
            try:
                from epms_server.aggregation import _score_agent_interval
                await _score_agent_interval(pool, row["agent_id"], str(row["organization_id"]))
            except Exception:
                pass
    except Exception as e:
        _log.warning("Scoring cycle: %s", e)


async def _aggregate_app_sessions(pool):
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT epms_aggregate_app_sessions(5)")
            if result:
                _log.debug("Created %d app sessions", result)
    except Exception:
        pass


async def _purge_process_data(pool):
    try:
        async with pool.acquire() as conn:
            purged = await conn.fetchval("SELECT epms_purge_process_events(7)")
            if purged:
                _log.debug("Purged %d process events", purged)
    except Exception:
        pass


async def _compute_health_score(conn, agent_id: str) -> float:
    try:
        row = await conn.fetchrow(
            """SELECT cpu_percent, memory_percent, disk_usage_percent, uptime_seconds
               FROM system_metrics WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1""",
            agent_id,
        )
        if not row:
            return 50.0
        cpu_score = max(0, 100 - (row["cpu_percent"] or 0)) * 0.3
        mem_score = max(0, 100 - (row["memory_percent"] or 0)) * 0.3
        disk_score = max(0, 100 - (row["disk_usage_percent"] or 0)) * 0.2
        uptime_days = (row["uptime_seconds"] or 0) / 86400
        uptime_score = min(100, uptime_days * 5) * 0.2
        return round(min(100, cpu_score + mem_score + disk_score + uptime_score), 1)
    except Exception:
        return 50.0


def _send_email(to: str, subject: str, body: str):
    smtp_host = os.environ.get("EPMS_SMTP_HOST", "")
    smtp_port = int(os.environ.get("EPMS_SMTP_PORT", "587"))
    smtp_user = os.environ.get("EPMS_SMTP_USER", "")
    smtp_pass = os.environ.get("EPMS_SMTP_PASSWORD", "")
    smtp_from = os.environ.get("EPMS_SMTP_FROM", "noreply@epms.local")
    if not smtp_host:
        _log.warning("SMTP not configured — email not sent")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        if smtp_user:
            server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, [to], msg.as_string())


def _report_to_html(rows: List[Dict], title: str = "Report") -> str:
    if not rows:
        return f"<html><body><h1>{title}</h1><p>No data</p></body></html>"
    headers = list(rows[0].keys())
    row_html = "\n".join(
        f"<tr>{''.join(f'<td>{v}</td>' for v in r.values())}</tr>" for r in rows
    )
    return f"""<html><head><style>body{{font-family:Arial;margin:20px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
th{{background:#4f46e5;color:white}}</style></head>
<body><h1>{title}</h1><table><tr>{''.join(f'<th>{h}</th>' for h in headers)}</tr>{row_html}</table></body></html>"""


async def _build_report_file(report_id: str, req, pool, report_dir: Path):
    from routes.models import ReportRequest
    try:
        ext = req.format if req.format in ("csv", "html") else "csv"
        output_path = report_dir / f"{report_id}.{ext}"
        if req.format == "html":
            rows = await _query_report_data(pool, req)
            content = _report_to_html(rows, req.report_title)
            output_path.write_text(content, encoding="utf-8")
        elif req.type == "activity":
            await _build_activity_report(pool, req, output_path)
        elif req.type == "productivity":
            await _build_productivity_report(pool, req, output_path)
        else:
            await _build_activity_report(pool, req, output_path)
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE reports SET status = 'completed', file_path = $1 WHERE id = $2::uuid",
                    str(output_path), report_id,
                )
    except Exception as e:
        _log.error("Report build failed: %s", e)
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE reports SET status = 'failed' WHERE id = $1::uuid",
                    report_id,
                )


async def _query_report_data(pool, req):
    if not pool:
        return []
    async with pool.acquire() as conn:
        if req.type == "productivity":
            rows = await conn.fetch(
                """SELECT a.display_name, ps.date, ps.score,
                          ps.productive_time_seconds, ps.neutral_time_seconds,
                          ps.distracting_time_seconds, ps.idle_time_seconds
                    FROM productivity_scores ps
                     JOIN agents a ON ps.agent_id::text = a.agent_id
                     WHERE ps.date >= COALESCE(NULLIF($1, '')::date, CURRENT_DATE - 30)
                       AND ps.date <= COALESCE(NULLIF($2, '')::date, CURRENT_DATE)
                       AND ($3 IS NULL OR ps.organization_id = $3)
                     ORDER BY ps.date DESC LIMIT 10000""",
                req.date_from, req.date_to, req.organization_id,
            )
        else:
            rows = await conn.fetch(
                """SELECT a.display_name, h.timestamp, h.active_window_title,
                          h.active_window_process, h.is_afk, h.afk_seconds
                    FROM agent_heartbeats h
                    JOIN agents a ON h.agent_id = a.agent_id
                    WHERE h.timestamp >= COALESCE(NULLIF($1, '')::timestamptz, CURRENT_DATE)
                      AND h.timestamp <= COALESCE(NULLIF($2, '')::timestamptz, NOW())
                      AND ($3 IS NULL OR a.organization_id = $3)
                    ORDER BY h.timestamp DESC LIMIT 10000""",
                req.date_from, req.date_to, req.organization_id,
            )
        return [dict(r) for r in rows]


async def _build_activity_report(pool, req, output_path: Path):
    if not pool:
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT a.display_name, h.timestamp, h.active_window_title,
                      h.active_window_process, h.is_afk, h.afk_seconds
                FROM agent_heartbeats h
                JOIN agents a ON h.agent_id = a.agent_id
                WHERE h.timestamp >= COALESCE(NULLIF($1, '')::timestamptz, CURRENT_DATE)
                  AND h.timestamp <= COALESCE(NULLIF($2, '')::timestamptz, NOW())
                  AND ($3 IS NULL OR a.organization_id = $3)
                ORDER BY h.timestamp DESC LIMIT 10000""",
            req.date_from, req.date_to, req.organization_id,
        )
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["User", "Timestamp", "Window Title", "Process", "AFK", "AFK Seconds"])
        for row in rows:
            writer.writerow([
                row["display_name"], row["timestamp"].isoformat(),
                row["active_window_title"], row["active_window_process"],
                row["is_afk"], row["afk_seconds"],
            ])


async def _build_productivity_report(pool, req, output_path: Path):
    if not pool:
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT a.display_name, ps.date, ps.score,
                      ps.productive_time_seconds, ps.neutral_time_seconds,
                      ps.distracting_time_seconds, ps.idle_time_seconds
                FROM productivity_scores ps
                JOIN agents a ON ps.agent_id::text = a.agent_id
                WHERE ps.date >= COALESCE(NULLIF($1, '')::date, CURRENT_DATE - 30)
                  AND ps.date <= COALESCE(NULLIF($2, '')::date, CURRENT_DATE)
                  AND ($3 IS NULL OR ps.organization_id = $3)
                ORDER BY ps.date DESC LIMIT 10000""",
            req.date_from, req.date_to, req.organization_id,
        )
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["User", "Date", "Score", "Productive (s)", "Neutral (s)", "Distracting (s)", "Idle (s)"])
        for row in rows:
            writer.writerow([
                row["display_name"], row["date"].isoformat(), row["score"],
                row["productive_time_seconds"], row["neutral_time_seconds"],
                row["distracting_time_seconds"], row["idle_time_seconds"],
            ])