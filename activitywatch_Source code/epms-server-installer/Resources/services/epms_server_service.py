"""
EPMS Enterprise Server — Consolidated Service
Single FastAPI application providing REST API, AD/LDAP authentication,
RBAC, analytics, reports, notifications, aggregation, and dashboard.
"""

import os
import sys
import json
import logging
import uuid
import hashlib
import hmac
import base64
import secrets
import time
import asyncio
import smtplib
import email
import io
import csv
import contextlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple, Set
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from epms_server import config as _config

from fastapi import FastAPI, HTTPException, Depends, Header, Request, status, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState
from pydantic import BaseModel, Field, field_validator
import uvicorn
import asyncpg
try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None
from epms_common import setup_cors
from epms_server.ad_login import authenticate_ad
from epms_server.rbac import AuthContext, get_current_user, decode_token, require_role, filter_by_role, Role, ROLE_MAP
from epms_server.aggregation import run_aggregation_worker, _aggregate_productivity_scores

try:
    import jwt as pyjwt
except ImportError:
    print("WARNING: PyJWT not installed. Install: pip install pyjwt")
    sys.exit(1)

try:
    import openpyxl
except ImportError:
    openpyxl = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("epms.server")

# =============================================================
# Configuration
# =============================================================

CONFIG_PATH = os.environ.get("APP_SETTINGS_PATH", "config/appsettings.json")
from epms_server.config import (
    JWT_SECRET, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS, PASSWORD_HASH_ITERATIONS,
    TOKEN_BLACKLIST_PREFIX, ENROLLMENT_MODE,
    AGENT_RATELIMIT_PREFIX, AGENT_RATELIMIT_PER_MINUTE,
)

# =============================================================
# Pydantic Models
# =============================================================

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "2.0.0"
    uptime_seconds: float = 0
    database: str = "connected"
    redis: str = "connected"

class AgentRegister(BaseModel):
    display_name: str = ""
    hostname: str = ""
    version: str = "1.0.0"
    os: str = "Windows"
    capabilities: Dict[str, bool] = {}

class AgentHeartbeat(BaseModel):
    timestamp: str = ""
    active_window: Dict[str, Any] = {}
    foreground_window: Optional[Dict[str, Any]] = None
    browser_activity: Optional[Dict[str, Any]] = None
    editor_activity: Optional[Dict[str, Any]] = None
    afk_seconds: float = 0
    is_afk: bool = False
    system: Dict[str, Any] = {}
    processes: Optional[List[Dict[str, Any]]] = None

class NotificationRequest(BaseModel):
    type: str = "in_app"
    title: str
    message: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    email: Optional[str] = None
    priority: str = "normal"

class ReportRequest(BaseModel):
    type: str = "activity"
    format: str = "csv"
    agent_ids: Optional[List[str]] = None
    date_from: str = ""
    date_to: str = ""
    organization_id: Optional[str] = None
    user_emails: Optional[List[str]] = None
    report_title: str = "Activity Report"


class ProductivityRuleRequest(BaseModel):
    pattern: str = Field(..., description="App/window title pattern (glob or regex)")
    category: str = Field(..., pattern="^(productive|neutral|distracting)$")
    rule_type: str = Field(default="glob", pattern="^(glob|regex|exact)$")
    description: str = ""


class ProductivityRuleResponse(BaseModel):
    id: str
    organization_id: str
    pattern: str
    category: str
    rule_type: str
    description: str
    is_active: bool
    created_at: str

class BrowserEvent(BaseModel):
    timestamp: str = ""
    browser_name: str = ""
    domain: str = ""
    url: str = ""
    page_title: str = ""
    category: str = "uncategorized"
    is_productive: bool = True
    is_active: bool = True

class EditorEvent(BaseModel):
    timestamp: str = ""
    editor_name: str = ""
    project_name: str = ""
    file_name: str = ""
    file_extension: str = ""
    language: str = ""
    is_focused: bool = True

class BatchEvents(BaseModel):
    events: List[Dict[str, Any]] = []
    timestamp: str = ""
    agent_id: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 1:
            raise ValueError("Password is required")
        return v


class ADLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 1:
            raise ValueError("Password is required")
        return v

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900
    user: Optional[Dict[str, Any]] = None


class SystemInventoryResponse(BaseModel):
    agent_id: str = ""
    hostname: str = ""
    os: str = ""
    os_version: str = ""
    os_build: str = ""
    cpu_model: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_architecture: str = ""
    total_ram_gb: float = 0
    total_disk_gb: float = 0
    used_disk_gb: float = 0
    free_disk_gb: float = 0
    ip_address: str = ""
    mac_address: str = ""
    last_boot: str = ""
    last_inventory_update: str = ""
    installed_software: List[Dict[str, Any]] = []
    network_interfaces: List[Dict[str, Any]] = []
    running_services: List[Dict[str, Any]] = []


class InventorySummaryResponse(BaseModel):
    total_devices: int = 0
    online_devices: int = 0
    offline_devices: int = 0
    idle_devices: int = 0
    os_breakdown: List[Dict[str, Any]] = []
    total_cpu_cores: int = 0
    total_ram_gb: float = 0
    total_disk_gb: float = 0
    avg_cpu_cores: float = 0
    avg_ram_gb: float = 0
    avg_disk_gb: float = 0
    software_count: int = 0
    service_count: int = 0
    unpatched_count: int = 0


class HealthDeviceResponse(BaseModel):
    agent_id: str = ""
    hostname: str = ""
    status: str = "healthy"
    health_score: float = 100
    cpu_usage_percent: float = 0
    memory_usage_percent: float = 0
    disk_usage_percent: float = 0
    uptime_seconds: int = 0
    last_heartbeat: str = ""
    active_alerts: int = 0
    process_count: int = 0
    thread_count: int = 0
    handle_count: int = 0
    performance_index: float = 1.0
    stability_score: float = 1.0


class HealthAnomalyItem(BaseModel):
    id: str = ""
    agent_id: str = ""
    hostname: str = ""
    type: str = "cpu"
    severity: str = "warning"
    message: str = ""
    value: float = 0
    threshold: float = 0
    detected_at: str = ""
    acknowledged: bool = False


class ExecutiveSummaryResponse(BaseModel):
    total_devices: int = 0
    online_devices: int = 0
    offline_devices: int = 0
    idle_devices: int = 0
    total_users: int = 0
    active_users_today: int = 0
    total_teams: int = 0
    total_organizations: int = 0
    overall_health_score: float = 100
    avg_productivity: float = 0
    productivity_trend: str = "stable"
    alerts_active: int = 0
    alerts_critical: int = 0
    total_uptime_hours: float = 0
    avg_uptime_per_device_hours: float = 0
    top_performers: List[Dict[str, Any]] = []
    needs_attention: List[Dict[str, Any]] = []
    weekly_comparison: Dict[str, Any] = {}
    department_breakdown: List[Dict[str, Any]] = []


# =============================================================
# Lifespan
# =============================================================

@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    """Initialize and clean up connections on startup, shut down on exit."""
    global db_pool, redis_client

    if not JWT_SECRET:
        logger.critical("JWT_SECRET not set! Authentication is DISABLED. Set a strong random secret.")
    if not _API_KEY_PEPPER:
        logger.critical("EPMS_API_KEY_PEPPER not set! API key hashing uses weak fallback. Set a strong random secret.")

    config = {}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                config = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load config: {e}")

    db_config = config.get("database", {})
    redis_config = config.get("redis", {})

    try:
        db_pool = await asyncpg.create_pool(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            database=db_config.get("name", "epms"),
            user=db_config.get("user", "postgres"),
            password=db_config.get("password", ""),
            min_size=2,
            max_size=db_config.get("max_connections", 20),
        )
        logger.info("Database connection pool created")
    except Exception as e:
        logger.warning(f"Database connection failed: {e}")

    try:
        redis_client = aioredis.Redis(
            host=redis_config.get("host", "localhost"),
            port=redis_config.get("port", 6379),
            password=redis_config.get("password", None) or None,
            db=0,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=False,
        )
        await asyncio.wait_for(redis_client.ping(), timeout=5)
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        redis_client = None
    _config.redis_client = redis_client

    aggregation_task = asyncio.create_task(_aggregation_worker())
    logger.info("Aggregation worker scheduled")

    yield

    aggregation_task.cancel()
    try:
        await aggregation_task
    except asyncio.CancelledError:
        pass
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    _config.redis_client = None
    logger.info("Server shutdown complete")


# =============================================================
# Application Setup
# =============================================================

app = FastAPI(
    title="EPMS Enterprise Server",
    version="1.0.0",
    description="Enterprise Productivity Management System — Consolidated Server",
    lifespan=_lifespan,
)

cors_origins = os.environ.get("CORS_ORIGINS", "")
if not cors_origins:
    logger.warning("CORS_ORIGINS not set — defaulting to http://localhost:3000. Set explicit origins for production.")
    cors_origins = "http://localhost:3000"
setup_cors(app, cors_origins)

trusted_hosts_str = os.environ.get("TRUSTED_HOSTS", "")
trusted_hosts = [h.strip() for h in trusted_hosts_str.split(",") if h.strip()]
if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

# Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-XSS-Protection"] = "0"
    return response

# =============================================================
# Static Files — Web Dashboard
# =============================================================

_web_ui_path = os.environ.get("EPMS_WEB_UI_PATH", "")
if not _web_ui_path:
    _candidate = Path(__file__).parent / "web-ui"
    if _candidate.is_dir():
        _web_ui_path = str(_candidate)

if _web_ui_path and Path(_web_ui_path).is_dir():
    if Path(_web_ui_path, "index.html").is_file():
        app.mount("/dashboard", StaticFiles(directory=_web_ui_path, html=True), name="dashboard")
        logger.info(f"Web dashboard mounted at /dashboard from {_web_ui_path}")
    else:
        logger.warning(f"No index.html in {_web_ui_path} — /dashboard disabled")
else:
    logger.info("Web dashboard not found — /dashboard endpoint disabled")

# =============================================================
# Database & Cache Connections
# =============================================================

db_pool: Optional[asyncpg.Pool] = None
redis_client = None
start_time = datetime.now(timezone.utc)


def _parse_ts(ts: str) -> datetime:
    """Convert ISO-format timestamp string to Python datetime for asyncpg."""
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc)


async def get_db():
    """Get database connection from pool."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        yield conn


# =============================================================
# Password Hashing Utilities
# =============================================================

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt.
    Format: $pbkdf2-sha256$iterations$salt$hash
    Compatible with Python's hashlib and many other libraries."""
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii").rstrip("=")
    hash_b64 = base64.b64encode(dk).decode("ascii").rstrip("=")
    return f"$pbkdf2-sha256${PASSWORD_HASH_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a PBKDF2 hash string."""
    try:
        parts = password_hash.split("$")
        if len(parts) != 5 or parts[1] != "pbkdf2-sha256":
            logger.warning(f"Unknown hash format: {parts[1] if len(parts) > 1 else 'invalid'}")
            return False
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3] + "==")
        stored_hash = base64.b64decode(parts[4] + "==")
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(dk, stored_hash)
    except (ValueError, IndexError, base64.binascii.Error) as e:
        logger.error(f"Password verification error: {e}")
        return False


_API_KEY_PEPPER = ""
def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage. Uses SHA-256 with a configurable pepper prefix."""
    global _API_KEY_PEPPER
    if not _API_KEY_PEPPER:
        _API_KEY_PEPPER = os.environ.get("EPMS_API_KEY_PEPPER", "")
        if not _API_KEY_PEPPER:
            logger.warning("EPMS_API_KEY_PEPPER not set — using weak default. Set a strong random secret!")
            _API_KEY_PEPPER = "epms-api-key-fallback-do-not-use-in-production"
    return hashlib.sha256(f"{_API_KEY_PEPPER}:{api_key}".encode()).hexdigest()


# =============================================================
# JWT Token Utilities
# =============================================================

def create_access_token(user_id: str, email: str, role: str, org_id: str = "") -> Tuple[str, int]:
    """Create a signed JWT access token with claims."""
    now = int(time.time())
    expires = now + JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    jti = secrets.token_hex(16)
    payload = {
        "sub": user_id,
        "email": email,
        "org_id": org_id,
        "role": role,
        "iat": now,
        "exp": expires,
        "jti": jti,
        "type": "access",
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires


def create_refresh_token(user_id: str) -> Tuple[str, int]:
    """Create a signed JWT refresh token."""
    now = int(time.time())
    expires = now + JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    jti = secrets.token_hex(16)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": expires,
        "jti": jti,
        "type": "refresh",
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires


# =============================================================
# Authentication Dependencies
# =============================================================

async def verify_api_key(
    x_api_key: str = Header(None),
    authorization: str = Header(None),
    request: Request = None,
) -> Dict[str, Any]:
    """Verify API key from header against stored keys in database.
    Returns agent info dict with agent_id if valid."""
    api_key = x_api_key or ""
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    # Hash the provided key
    key_hash = hash_api_key(api_key)

    # Look up in database
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT agent_id, display_name, organization_id, is_active "
            "FROM agents WHERE api_key_hash = $1 AND is_active = true",
            key_hash,
        )
        if not row:
            # Also check against enrollment tokens in configuration
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


async def _aggregation_worker():
    """Background loop: aggregate process_events, score productivity, purge old data."""
    logger.info("Background aggregation worker started")
    while True:
        try:
            await asyncio.sleep(300)
            if db_pool:
                await _aggregate_productivity_scores(db_pool)
                await _aggregate_app_sessions(db_pool)
                await _purge_process_data(db_pool)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Aggregation cycle failed: %s", e)


async def _aggregate_productivity_scores(pool):
    """Score all online agents for the current day."""
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
        logger.warning("Scoring cycle: %s", e)


async def _aggregate_app_sessions(pool):
    """Aggregate process_events into app_sessions via DB function."""
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT epms_aggregate_app_sessions(5)")
            if result:
                logger.debug("Created %d app sessions", result)
    except Exception:
        pass


async def _purge_process_data(pool):
    """Purge old process_events (7 day retention)."""
    try:
        async with pool.acquire() as conn:
            purged = await conn.fetchval("SELECT epms_purge_process_events(7)")
            if purged:
                logger.debug("Purged %d process events", purged)
    except Exception:
        pass


# =============================================================
# Health & Info Endpoints
# =============================================================

@app.get("/health", response_model=HealthResponse)
@app.get("/health/live")
@app.get("/health/ready")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        uptime_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
        database="connected" if db_pool else "disconnected",
        redis="connected" if redis_client else "disabled",
    )


@app.get("/api/v1/health")
async def api_health():
    """API health check endpoint."""
    return {"status": "healthy", "service": "epms-api", "version": "1.0.0"}


@app.get("/api/v1/info")
async def server_info(current_user: AuthContext = Depends(get_current_user)):
    """Get server information (authenticated)."""
    return {
        "name": "EPMS Enterprise Server",
        "version": "1.0.0",
        "uptime_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
    }


# =============================================================
# Agent ID Validation Dependency
# =============================================================

async def validate_agent_identity(
    agent_info: Dict[str, Any] = Depends(verify_api_key),
    x_agent_id: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Validate that the X-Agent-ID header matches the API key's agent identity.
    Prevents agent ID spoofing by ensuring the agent_id sent in headers
    is bound to the API key used for authentication."""
    api_key_agent_id = agent_info.get("agent_id", "")

    # If the API key is an enrollment token (new registration), allow any agent_id
    if api_key_agent_id == ENROLLMENT_MODE:
        resolved_agent_id = x_agent_id or str(uuid.uuid4())
        return {**agent_info, "agent_id": resolved_agent_id}

    # For registered agents: the X-Agent-ID must match the API key's bound agent
    if x_agent_id and x_agent_id != api_key_agent_id:
        logger.warning(
            f"Agent ID spoofing attempt: header={x_agent_id}, api_key_agent={api_key_agent_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Agent ID mismatch: the provided agent_id is not bound to this API key",
        )

    return agent_info


# =============================================================
# Agent Endpoints
# =============================================================

@app.post("/api/v1/agent/register")
async def register_agent(
    agent: AgentRegister,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Register a new agent (client device) with the server.
    Requires a valid enrollment token or existing API key.
    Returns an agent-specific API key for subsequent requests."""
    agent_id = agent_identity["agent_id"]
    enrollment_mode = agent_identity.get("agent_id") == ENROLLMENT_MODE

    # Generate or use provided agent_id
    if enrollment_mode:
        agent_id = str(uuid.uuid4())

    # Generate a dedicated API key for this agent
    agent_api_key = f"epms_{agent_id[:8]}_{secrets.token_hex(24)}"
    api_key_hash = hash_api_key(agent_api_key)

    if db_pool:
        org_id = agent_identity.get("organization_id", "")
        async with db_pool.acquire() as conn:
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
                # Update existing agent and rotate key
                await conn.execute(
                    """UPDATE agents SET organization_id=$2::uuid, display_name=$3, hostname=$4, os=$5,
                       version=$6, api_key_hash=$7, is_online=true,
                       is_enrolled=true, last_heartbeat=NOW()
                       WHERE agent_id=$1""",
                    agent_id, org_id, agent.display_name, agent.hostname, agent.os,
                    agent.version, api_key_hash,
                )

    # Cache in Redis
    if redis_client:
        await redis_client.set(
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


class EnrollmentTokenRequest(BaseModel):
    organization_id: Optional[str] = None
    description: str = "Enrollment token for agent registration"


@app.post("/api/v1/admin/enrollment-token")
async def create_enrollment_token(
    req: EnrollmentTokenRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("admin")),
):
    """Generate a new enrollment token for agent registration.
    The token is hashed (SHA-256) before storage; the raw token
    is returned once in the response and cannot be retrieved later.
    Requires admin role."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    org_id = req.organization_id or str(current_user.org_id)
    if not org_id:
        raise HTTPException(status_code=400, detail="organization_id is required")

    # Generate a cryptographically random token
    raw_token = f"epms_enroll_{secrets.token_hex(32)}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Store the hash in the configuration table
    async with db_pool.acquire() as conn:
        # Revoke existing tokens for this org by overwriting
        await conn.execute(
            """INSERT INTO configuration (organization_id, scope, key, value, description)
               VALUES ($1, 'organization', 'enrollment_token', $2::jsonb, $3)
               ON CONFLICT (organization_id, scope, key)
               DO UPDATE SET value = $2::jsonb, description = $3, updated_at = NOW()""",
            org_id,
            json.dumps(token_hash),
            req.description,
        )

    return {
        "enrollment_token": raw_token,
        "organization_id": org_id,
        "description": req.description,
        "warning": "This token will not be shown again. Store it securely.",
    }


@app.post("/api/v1/admin/enrollment-token/revoke")
async def revoke_enrollment_token(
    organization_id: Optional[str] = None,
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("admin")),
):
    """Revoke the enrollment token for an organization.
    Requires admin role."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    org_id = organization_id or str(current_user.org_id)
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM configuration WHERE organization_id = $1::uuid AND key = 'enrollment_token'",
            org_id,
        )

    return {"status": "revoked", "organization_id": org_id}


async def check_agent_rate_limit(agent_identity: Dict[str, Any] = Depends(validate_agent_identity)):
    """Rate limit agent endpoints per agent per minute using Redis."""
    if redis_client:
        agent_id = agent_identity["agent_id"]
        key = f"{AGENT_RATELIMIT_PREFIX}{agent_id}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 60)
        if count > AGENT_RATELIMIT_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for agent {agent_id}: {count} requests/min")
            raise HTTPException(status_code=429, detail="Rate limit exceeded (60 req/min)")
    return agent_identity


@app.post("/api/v1/agent/heartbeat")
async def receive_heartbeat(
    heartbeat: AgentHeartbeat,
    agent_identity: Dict[str, Any] = Depends(check_agent_rate_limit),
):
    """Receive a heartbeat with monitoring data from a verified agent.
    Agent identity is validated through the API key ↔ agent_id binding.
    Rate limited to 60 requests per minute per agent."""
    agent_id = agent_identity["agent_id"]

    # Store heartbeat in database
    if db_pool and agent_id != "unknown":
        async with db_pool.acquire() as conn:
            # Update agent status
            await conn.execute(
                """UPDATE agents SET is_online=true, last_heartbeat=NOW()
                   WHERE agent_id=$1""",
                agent_id,
            )

            # Insert heartbeat record
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

            # Store process events (full process snapshot)
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
                        logger.debug("Process event insert error: %s", e)

            # Store browser activity separately
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

            # Store editor activity separately
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


@app.post("/api/v1/agent/browser")
async def receive_browser_event(
    event: BrowserEvent,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Receive a browser activity event from a verified agent."""
    agent_id = agent_identity["agent_id"]

    if db_pool and agent_id != "unknown":
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO browser_activity
                       (agent_id, timestamp, browser_name, domain, url, page_title, category, is_productive, is_active)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true)""",
                    agent_id, _parse_ts(event.timestamp), event.browser_name, event.domain,
                    event.url, event.page_title, event.category, event.is_productive,
                )
        except Exception as e:
            logger.exception(f"Failed to store browser event for agent {agent_id}: {e}")

    return {"status": "ok"}


@app.post("/api/v1/agent/editor")
async def receive_editor_event(
    event: EditorEvent,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Receive an editor activity event from a verified agent."""
    agent_id = agent_identity["agent_id"]

    if db_pool and agent_id != "unknown":
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO editor_activity
                       (agent_id, timestamp, editor_name, project_name,
                        file_name, file_extension, language, is_focused)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, true)""",
                    agent_id, _parse_ts(event.timestamp), event.editor_name, event.project_name,
                    event.file_name, event.file_extension, event.language,
                )
        except Exception as e:
            logger.exception(f"Failed to store editor event for agent {agent_id}: {e}")

    return {"status": "ok"}


@app.post("/api/v1/agent/events/batch")
async def receive_batch_events(
    batch: BatchEvents,
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Receive a batch of events from a verified agent."""
    agent_id = agent_identity["agent_id"]
    logger.info(f"Received batch of {len(batch.events)} events from agent {agent_id}")
    return {"status": "ok", "count": len(batch.events), "agent_id": agent_id}


@app.get("/api/v1/agent/config")
async def get_agent_config(
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Get agent configuration from the server for the verified agent."""
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


@app.get("/api/v1/agent/policies")
async def get_agent_policies(
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Get active policies for the verified agent."""
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


@app.post("/api/v1/agent/metrics")
async def receive_metrics(
    metrics: Dict[str, Any],
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Receive detailed system metrics from a verified agent."""
    agent_id = agent_identity["agent_id"]

    if db_pool and agent_id != "unknown":
        async with db_pool.acquire() as conn:
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


@app.post("/api/v1/agent/inventory")
async def receive_inventory(
    inventory: Dict[str, Any],
    agent_identity: Dict[str, Any] = Depends(validate_agent_identity),
):
    """Receive system inventory data from a verified agent.
    Stores inventory snapshot in agents.metadata JSONB field."""
    agent_id = agent_identity["agent_id"]

    if db_pool and agent_id != "unknown":
        async with db_pool.acquire() as conn:
            # Update metadata with inventory snapshot
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

            # Get existing metadata and merge
            row = await conn.fetchrow(
                "SELECT metadata FROM agents WHERE agent_id = $1",
                agent_id,
            )
            existing_meta = row["metadata"] if row and isinstance(row["metadata"], dict) else {}

            # Merge: existing metadata keys take precedence for non-inventory fields,
            # inventory fields get overwritten with new data
            merged = dict(existing_meta)
            merged.update(meta_update)

            await conn.execute(
                "UPDATE agents SET metadata = $1::jsonb WHERE agent_id = $2",
                json.dumps(merged), agent_id,
            )

    return {"status": "ok"}


# =============================================================
# Dashboard Data Endpoints
# =============================================================

@app.get("/api/v1/dashboard/summary")
async def get_dashboard_summary(
    current_user: AuthContext = Depends(get_current_user),
    period: str = Query(default="today"),
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
):
    """Get dashboard summary statistics for the authenticated user's organization.
    Supports period filtering: today, week, month, custom.
    """
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
        "total_devices": 0,
        "online_devices": 0,
        "offline_devices": 0,
        "active_devices": 0,
        "active_today": 0,
        "avg_productivity": 0,
        "average_productivity": 0,
        "total_events_today": 0,
        "events_today": 0,
    }

    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE is_online) as online, "
                "COUNT(*) FILTER (WHERE NOT is_online) as offline "
                "FROM agents WHERE organization_id = $1::uuid",
                org_id,
            )
            if row:
                data["total_devices"] = row["total"]
                data["online_devices"] = row["online"]
                data["offline_devices"] = row["offline"]

            # Active devices in period
            active_count = await conn.fetchval(
                "SELECT COUNT(DISTINCT h.agent_id) FROM agent_heartbeats h "
                "JOIN agents a ON h.agent_id = a.agent_id "
                "WHERE h.timestamp >= $2::date AND h.timestamp <= ($3::date + interval '1 day')::date "
                "AND a.organization_id = $1::uuid",
                org_id, date_from, date_to,
            )
            data["active_today"] = data["active_devices"] = active_count or 0

            # Average productivity in period
            avg_prod = await conn.fetchval(
                "SELECT AVG(score) FROM productivity_scores "
                "WHERE organization_id = $1::uuid AND date >= $2::date AND date <= $3::date",
                org_id, date_from, date_to,
            )
            data["avg_productivity"] = data["average_productivity"] = round(avg_prod or 0, 1)

            # Events today
            events_count = await conn.fetchval(
                "SELECT COUNT(*) FROM activity_events ev "
                "JOIN agents a ON ev.agent_id::text = a.agent_id "
                "WHERE a.organization_id = $1::uuid AND ev.timestamp >= $2::date",
                org_id, date_from,
            )
            data["total_events_today"] = data["events_today"] = events_count or 0

    return data


@app.get("/api/v1/dashboard/devices")
async def get_devices(current_user: AuthContext = Depends(get_current_user)):
    """Get list of all registered devices for the authenticated user's organization."""
    org_id = current_user.org_id
    devices = []
    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT agent_id, display_name, hostname, os, version, "
                "is_online, last_heartbeat, created_at "
                "FROM agents WHERE organization_id = $1::uuid "
                "ORDER BY last_heartbeat DESC NULLS LAST",
                org_id,
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


@app.get("/api/v1/dashboard/activity")
async def get_recent_activity(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get recent activity events for the authenticated user's organization."""
    org_id = current_user.org_id
    events = []
    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT a.display_name, h.timestamp, h.active_window_title, "
                "h.active_window_process, h.is_afk, h.afk_seconds "
                "FROM agent_heartbeats h "
                "JOIN agents a ON h.agent_id = a.agent_id "
                "WHERE a.organization_id = $1::uuid "
                "ORDER BY h.timestamp DESC LIMIT $2",
                org_id, limit,
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


@app.get("/api/v1/analytics/productivity")
async def get_productivity_data(
    days: int = 7,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get productivity analytics data for the authenticated user's organization."""
    org_id = current_user.org_id
    data = []
    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT date, AVG(score) as avg_score, "
                "SUM(productive_time_seconds) as productive, "
                "SUM(neutral_time_seconds) as neutral, "
                "SUM(distracting_time_seconds) as distracting, "
                "SUM(idle_time_seconds) as idle "
                "FROM productivity_scores "
                "WHERE organization_id = $1::uuid AND date >= CURRENT_DATE - ($2 || ' days')::INTERVAL "
                "GROUP BY date ORDER BY date",
                org_id, str(days),
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


@app.get("/api/v1/analytics/scores/{agent_id}")
async def get_agent_score(
    agent_id: str,
    date: str = Query(default=None),
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    """Get a single agent's productivity score breakdown for a given date.
    Requires manager role or higher."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with db_pool.acquire() as conn:
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
            "agent_id": agent_id,
            "date": target,
            "score": row["score"],
            "productive_time_seconds": row["productive_time_seconds"],
            "neutral_time_seconds": row["neutral_time_seconds"],
            "distracting_time_seconds": row["distracting_time_seconds"],
            "categories": row["category_breakdown"] or {},
        }


@app.get("/api/v1/analytics/trends/{agent_id}")
async def get_agent_trends(
    agent_id: str,
    days: int = Query(default=30, le=365),
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    """Get trend data for a single agent over N days.
    Requires manager role or higher."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT date, score, productive_time_seconds,
                      neutral_time_seconds, distracting_time_seconds
               FROM productivity_scores
               WHERE agent_id = $1::uuid
               AND date >= CURRENT_DATE - $2::integer
               ORDER BY date""",
            agent_id, days,
        )
        return {"agent_id": agent_id, "period_days": days, "scores": [dict(r) for r in rows]}


@app.get("/api/v1/analytics/organization")
async def get_org_summary(
    days: int = Query(default=7),
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    """Get organization-level summary: average score, total productive time, active agents.
    Requires manager role or higher."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
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


@app.get("/api/v1/analytics/live/{agent_id}")
async def get_live_score(
    agent_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac = Depends(require_role("manager")),
):
    """Get the current live productivity score for an agent.
    Returns today's most recent score from the aggregation worker.
    Requires manager role or higher."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT score, productive_time_seconds, neutral_time_seconds,
                      distracting_time_seconds, idle_time_seconds, hb_count
               FROM productivity_scores
               WHERE agent_id = $1::uuid AND date = $2::date""",
            agent_id, today,
        )
        if not row:
            return {
                "agent_id": agent_id,
                "date": today,
                "score": 0,
                "heartbeats_processed": 0,
                "status": "no_data",
            }
        return {
            "agent_id": agent_id,
            "date": today,
            "score": row["score"],
            "heartbeats_processed": row.get("hb_count", 0),
            "productive_seconds": row["productive_time_seconds"],
            "neutral_seconds": row["neutral_time_seconds"],
            "distracting_seconds": row["distracting_time_seconds"],
            "idle_seconds": row.get("idle_time_seconds", 0),
            "status": "active",
        }


@app.get("/api/v1/dashboard/browser-activity")
async def get_browser_activity(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get recent browser activity for the authenticated user's organization."""
    org_id = current_user.org_id
    rows_data = []
    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT a.display_name, b.browser_name, b.domain, b.url,
                          b.page_title, b.is_productive, b.timestamp
FROM browser_activity b
                     JOIN agents a ON b.agent_id::text = a.agent_id
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


@app.get("/api/v1/dashboard/editor-activity")
async def get_editor_activity(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get recent editor activity for the authenticated user's organization."""
    org_id = current_user.org_id
    rows_data = []
    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT a.display_name, e.editor_name, e.project_name,
                          e.file_name, e.language, e.timestamp
FROM editor_activity e
                     JOIN agents a ON e.agent_id::text = a.agent_id
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


@app.get("/api/v1/dashboard/alerts")
async def get_alerts(
    limit: int = 20,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get recent system alerts for the authenticated user's organization."""
    org_id = current_user.org_id
    rows_data = []
    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, alert_type, severity, title, message,
                          acknowledged, created_at
                   FROM alerts
                   WHERE organization_id = $1::uuid
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


@app.post("/api/v1/dashboard/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    """Mark an alert as acknowledged."""
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE alerts SET acknowledged = true WHERE id = $1::uuid",
                alert_id,
            )
    return {"status": "ok"}


@app.get("/api/v1/dashboard/reports")
async def get_reports(
    limit: int = 20,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get list of generated reports for the authenticated user's organization."""
    org_id = current_user.org_id
    rows_data = []
    if db_pool and org_id:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, report_type, title, filters, format,
                          created_by, created_at
                   FROM reports
                   WHERE organization_id = $1::uuid
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


# =============================================================
# System Inventory Endpoints
# =============================================================


@app.get("/api/v1/inventory/summary")
async def get_inventory_summary(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Get an inventory summary across the organization.
    Requires manager role or higher."""
    org_id = current_user.org_id
    result = {
        "total_devices": 0, "online_devices": 0, "offline_devices": 0, "idle_devices": 0,
        "os_breakdown": [], "total_cpu_cores": 0, "total_ram_gb": 0,
        "total_disk_gb": 0, "avg_cpu_cores": 0, "avg_ram_gb": 0, "avg_disk_gb": 0,
        "software_count": 0, "service_count": 0, "unpatched_count": 0,
    }
    if not db_pool or not org_id:
        return result

    async with db_pool.acquire() as conn:
        agents_query = "SELECT agent_id, hostname, os, is_online, metadata FROM agents WHERE organization_id = $1::uuid"
        agents = await conn.fetch(agents_query, org_id)

        result["total_devices"] = len(agents)
        os_count: Dict[str, int] = {}
        total_cores = 0
        total_ram = 0.0
        total_disk = 0.0
        online = 0
        offline = 0
        idle = 0
        software_count = 0
        service_count = 0

        for a in agents:
            if a["is_online"]:
                online += 1
            else:
                offline += 1
            os_name = a["os"] or "Unknown"
            os_count[os_name] = os_count.get(os_name, 0) + 1

            meta = a["metadata"]
            if meta and isinstance(meta, dict):
                total_cores += meta.get("cpu_cores", 0) or 0
                total_ram += meta.get("total_ram_gb", 0) or 0.0
                total_disk += meta.get("total_disk_gb", 0) or 0.0
                sw = meta.get("installed_software", [])
                if sw:
                    software_count += len(sw)
                svc = meta.get("running_services", [])
                if svc:
                    service_count += len(svc)

        result["online_devices"] = online
        result["offline_devices"] = offline
        result["idle_devices"] = idle
        result["os_breakdown"] = [{"os": k, "count": v} for k, v in os_count.items()]
        result["total_cpu_cores"] = total_cores
        result["total_ram_gb"] = round(total_ram, 1)
        result["total_disk_gb"] = round(total_disk, 1)
        if result["total_devices"] > 0:
            result["avg_cpu_cores"] = round(total_cores / result["total_devices"], 1)
            result["avg_ram_gb"] = round(total_ram / result["total_devices"], 1)
            result["avg_disk_gb"] = round(total_disk / result["total_devices"], 1)
        result["software_count"] = software_count
        result["service_count"] = service_count

    return result


@app.get("/api/v1/inventory/detail/{agent_id}")
async def get_inventory_detail(
    agent_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Get full system inventory for a specific node.
    Requires manager role or higher."""
    if not db_pool:
        raise HTTPException(503, "Database not available")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT agent_id, hostname, os, ip_address, metadata
               FROM agents WHERE agent_id = $1""",
            agent_id,
        )
        if not row:
            raise HTTPException(404, "Agent not found")

        meta = row["metadata"] or {} if isinstance(row["metadata"], dict) else {}

        # Get latest system metrics
        metrics_row = await conn.fetchrow(
            """SELECT cpu_percent, memory_percent, memory_available_gb,
                      disk_usage_percent, uptime_seconds
               FROM system_metrics WHERE agent_id = $1
               ORDER BY timestamp DESC LIMIT 1""",
            agent_id,
        )

        return {
            "agent_id": row["agent_id"],
            "hostname": row["hostname"] or "",
            "os": row["os"] or "",
            "os_version": meta.get("os_version", ""),
            "os_build": meta.get("os_build", ""),
            "cpu_model": meta.get("cpu_model", ""),
            "cpu_cores": meta.get("cpu_cores", 0),
            "cpu_threads": meta.get("cpu_threads", 0),
            "cpu_architecture": meta.get("cpu_architecture", ""),
            "total_ram_gb": meta.get("total_ram_gb", 0),
            "total_disk_gb": meta.get("total_disk_gb", 0),
            "used_disk_gb": meta.get("used_disk_gb", 0),
            "free_disk_gb": meta.get("free_disk_gb", 0),
            "ip_address": row["ip_address"] or "",
            "mac_address": meta.get("mac_address", ""),
            "last_boot": meta.get("last_boot", ""),
            "last_inventory_update": meta.get("last_inventory_update", ""),
            "installed_software": meta.get("installed_software", []),
            "network_interfaces": meta.get("network_interfaces", []),
            "running_services": meta.get("running_services", []),
        }


# =============================================================
# Device Health Endpoints
# =============================================================


async def _compute_health_score(conn, agent_id: str) -> float:
    """Compute a health score (0-100) for a device based on recent metrics."""
    try:
        row = await conn.fetchrow(
            """SELECT cpu_percent, memory_percent, disk_usage_percent, uptime_seconds
               FROM system_metrics WHERE agent_id = $1
               ORDER BY timestamp DESC LIMIT 1""",
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


@app.get("/api/v1/health/devices")
async def get_health_devices(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Get health overview for all devices in the organization.
    Requires manager role or higher."""
    org_id = current_user.org_id
    devices = []
    if not db_pool or not org_id:
        return {"devices": devices}

    async with db_pool.acquire() as conn:
        agents = await conn.fetch(
            "SELECT agent_id, hostname, is_online FROM agents WHERE organization_id = $1::uuid",
            org_id,
        )

        for a in agents:
            metrics_row = await conn.fetchrow(
                """SELECT cpu_percent, memory_percent, disk_usage_percent, uptime_seconds,
                          process_count, thread_count
                   FROM system_metrics WHERE agent_id = $1
                   ORDER BY timestamp DESC LIMIT 1""",
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
                status = "offline"
                health_score = 0
            elif health_score >= 70:
                status = "healthy"
            elif health_score >= 40:
                status = "warning"
            else:
                status = "critical"

            devices.append({
                "agent_id": a["agent_id"],
                "hostname": a["hostname"] or a["agent_id"],
                "status": status,
                "health_score": health_score,
                "cpu_usage_percent": round(float(cpu_pct or 0), 1),
                "memory_usage_percent": round(float(mem_pct or 0), 1),
                "disk_usage_percent": round(float(disk_pct or 0), 1),
                "uptime_seconds": uptime or 0,
                "last_heartbeat": hb_row["timestamp"].isoformat() if hb_row else "",
                "active_alerts": alert_count or 0,
                "process_count": proc_count or 0,
                "thread_count": metrics_row["thread_count"] if metrics_row else 0,
                "handle_count": 0,
                "performance_index": round(max(0, 1 - (cpu_pct or 0) / 200), 2),
                "stability_score": round(min(1, max(0, health_score / 100)), 2),
            })

    return {"devices": devices}


@app.get("/api/v1/health/detail/{agent_id}")
async def get_health_detail(
    agent_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Get detailed health metrics for a single device.
    Requires manager role or higher."""
    if not db_pool:
        raise HTTPException(503, "Database not available")

    async with db_pool.acquire() as conn:
        a = await conn.fetchrow(
            "SELECT agent_id, hostname, is_online FROM agents WHERE agent_id = $1",
            agent_id,
        )
        if not a:
            raise HTTPException(404, "Agent not found")

        metrics_row = await conn.fetchrow(
            """SELECT cpu_percent, memory_percent, disk_usage_percent, uptime_seconds,
                      process_count, thread_count
               FROM system_metrics WHERE agent_id = $1
               ORDER BY timestamp DESC LIMIT 1""",
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
            status = "offline"
            health_score = 0
        elif health_score >= 70:
            status = "healthy"
        elif health_score >= 40:
            status = "warning"
        else:
            status = "critical"

        return {
            "agent_id": a["agent_id"],
            "hostname": a["hostname"] or a["agent_id"],
            "status": status,
            "health_score": health_score,
            "cpu_usage_percent": round(float(cpu_pct or 0), 1),
            "memory_usage_percent": round(float(mem_pct or 0), 1),
            "disk_usage_percent": round(float(disk_pct or 0), 1),
            "uptime_seconds": uptime or 0,
            "last_heartbeat": hb_row["timestamp"].isoformat() if hb_row else "",
            "active_alerts": alert_count or 0,
            "process_count": proc_count or 0,
            "thread_count": thread_count or 0,
            "handle_count": 0,
            "performance_index": round(max(0, 1 - (cpu_pct or 0) / 200), 2),
            "stability_score": round(min(1, max(0, health_score / 100)), 2),
        }


@app.get("/api/v1/health/anomalies")
async def get_health_anomalies(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Get detected anomalies across all devices.
    Requires manager role or higher."""
    org_id = current_user.org_id
    anomalies = []
    if not db_pool or not org_id:
        return {"anomalies": anomalies}

    async with db_pool.acquire() as conn:
        agents = await conn.fetch(
            "SELECT agent_id, hostname FROM agents WHERE organization_id = $1::uuid",
            org_id,
        )

        for a in agents:
            metrics_row = await conn.fetchrow(
                """SELECT cpu_percent, memory_percent, disk_usage_percent
                   FROM system_metrics WHERE agent_id = $1
                   ORDER BY timestamp DESC LIMIT 1""",
                a["agent_id"],
            )
            if not metrics_row:
                continue

            aid = a["agent_id"]
            hname = a["hostname"] or aid

            cpu = metrics_row["cpu_percent"] or 0
            mem = metrics_row["memory_percent"] or 0
            disk = metrics_row["disk_usage_percent"] or 0

            if cpu > 90:
                anomalies.append({
                    "id": f"{aid}-cpu",
                    "agent_id": aid, "hostname": hname,
                    "type": "cpu", "severity": "critical",
                    "message": f"CPU usage at {cpu:.0f}%",
                    "value": cpu, "threshold": 90,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False,
                })
            elif cpu > 80:
                anomalies.append({
                    "id": f"{aid}-cpu-warn",
                    "agent_id": aid, "hostname": hname,
                    "type": "cpu", "severity": "warning",
                    "message": f"CPU usage at {cpu:.0f}%",
                    "value": cpu, "threshold": 80,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False,
                })

            if mem > 90:
                anomalies.append({
                    "id": f"{aid}-mem",
                    "agent_id": aid, "hostname": hname,
                    "type": "memory", "severity": "critical",
                    "message": f"Memory usage at {mem:.0f}%",
                    "value": mem, "threshold": 90,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False,
                })
            elif mem > 80:
                anomalies.append({
                    "id": f"{aid}-mem-warn",
                    "agent_id": aid, "hostname": hname,
                    "type": "memory", "severity": "warning",
                    "message": f"Memory usage at {mem:.0f}%",
                    "value": mem, "threshold": 80,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False,
                })

            if disk > 90:
                anomalies.append({
                    "id": f"{aid}-disk",
                    "agent_id": aid, "hostname": hname,
                    "type": "disk", "severity": "critical",
                    "message": f"Disk usage at {disk:.0f}%",
                    "value": disk, "threshold": 90,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "acknowledged": False,
                })

    return {"anomalies": anomalies}


# =============================================================
# Executive Overview Endpoints
# =============================================================


@app.get("/api/v1/executive/summary")
async def get_executive_summary(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Get an executive-level summary across the organization.
    Requires manager role or higher."""
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
    if not db_pool or not org_id:
        return result

    async with db_pool.acquire() as conn:
        agents = await conn.fetch(
            "SELECT agent_id, hostname, is_online FROM agents WHERE organization_id = $1::uuid",
            org_id,
        )
        result["total_devices"] = len(agents)
        result["online_devices"] = sum(1 for a in agents if a["is_online"])
        result["offline_devices"] = result["total_devices"] - result["online_devices"]

        user_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE organization_id = $1::uuid",
            org_id,
        )
        result["total_users"] = user_count or 0

        team_count = await conn.fetchval(
            "SELECT COUNT(*) FROM teams WHERE organization_id = $1::uuid",
            org_id,
        )
        result["total_teams"] = team_count or 0

        active_today = await conn.fetchval(
            """SELECT COUNT(DISTINCT agent_id) FROM agent_heartbeats
               WHERE agent_id IN (SELECT agent_id FROM agents WHERE organization_id = $1::uuid)
               AND timestamp >= CURRENT_DATE""",
            org_id,
        )
        result["active_users_today"] = active_today or 0

        alert_active = await conn.fetchval(
            """SELECT COUNT(*) FROM alerts
               WHERE organization_id = $1::uuid AND acknowledged = false""",
            org_id,
        )
        result["alerts_active"] = alert_active or 0

        alert_critical = await conn.fetchval(
            """SELECT COUNT(*) FROM alerts
               WHERE organization_id = $1::uuid AND severity = 'critical' AND acknowledged = false""",
            org_id,
        )
        result["alerts_critical"] = alert_critical or 0

        prod_row = await conn.fetchrow(
            """SELECT AVG(score) as avg_score
               FROM productivity_scores
               WHERE organization_id = $1::uuid
               AND date >= CURRENT_DATE - 7""",
            org_id,
        )
        avg_prod = prod_row["avg_score"] if prod_row and prod_row["avg_score"] else 0
        result["avg_productivity"] = round(float(avg_prod), 1)

        health_scores = []
        total_uptime = 0
        top_perf = []
        needs_attn = []
        for a in agents:
            hs = await _compute_health_score(conn, a["agent_id"])
            health_scores.append(hs)

            metrics_row = await conn.fetchrow(
                "SELECT uptime_seconds FROM system_metrics WHERE agent_id = $1 ORDER BY timestamp DESC LIMIT 1",
                a["agent_id"],
            )
            uptime = metrics_row["uptime_seconds"] if metrics_row else 0
            total_uptime += uptime

            # Top performers (high health + online)
            if hs >= 80 and a["is_online"]:
                top_perf.append({
                    "agent_id": a["agent_id"],
                    "hostname": a["hostname"] or a["agent_id"],
                    "score": round(hs, 1),
                })

            # Needs attention (low health or offline)
            if hs < 40 or not a["is_online"]:
                issue = "Offline" if not a["is_online"] else f"Health score: {hs:.0f}%"
                severity = "critical" if (hs < 20 or not a["is_online"]) else "warning"
                needs_attn.append({
                    "agent_id": a["agent_id"],
                    "hostname": a["hostname"] or a["agent_id"],
                    "issue": issue,
                    "severity": severity,
                })

        result["overall_health_score"] = round(sum(health_scores) / len(health_scores), 1) if health_scores else 0
        result["total_uptime_hours"] = round(total_uptime / 3600, 1)
        result["avg_uptime_per_device_hours"] = round(total_uptime / max(len(agents), 1) / 3600, 1)
        result["top_performers"] = sorted(top_perf, key=lambda x: x["score"], reverse=True)[:5]
        result["needs_attention"] = sorted(needs_attn, key=lambda x: x["severity"])[:10]

        # Weekly comparison
        this_week = await conn.fetchrow(
            """SELECT AVG(score) as avg_score FROM productivity_scores
               WHERE organization_id = $1::uuid AND date >= CURRENT_DATE - 7""",
            org_id,
        )
        prev_week = await conn.fetchrow(
            """SELECT AVG(score) as avg_score FROM productivity_scores
               WHERE organization_id = $1::uuid
               AND date >= CURRENT_DATE - 14 AND date < CURRENT_DATE - 7""",
            org_id,
        )
        current_prod = float(this_week["avg_score"]) if this_week and this_week["avg_score"] else 0
        previous_prod = float(prev_week["avg_score"]) if prev_week and prev_week["avg_score"] else 0

        result["weekly_comparison"] = {
            "current": {
                "productivity": round(current_prod, 1),
                "health": round(result["overall_health_score"], 1),
                "active_users": result["active_users_today"],
            },
            "previous": {
                "productivity": round(previous_prod, 1),
                "health": 0,
                "active_users": 0,
            },
        }

        if current_prod > previous_prod + 2:
            result["productivity_trend"] = "improving"
        elif current_prod < previous_prod - 2:
            result["productivity_trend"] = "declining"
        else:
            result["productivity_trend"] = "stable"

    return result


# =============================================================
# Authentication Endpoints
# =============================================================

@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """Authenticate user with email and password, return JWT tokens.
    Validates credentials against the database using PBKDF2 password hashing.
    Rate-limited: max 5 attempts per email per minute."""
    email = credentials.email.strip().lower()

    # Rate limiting check
    if redis_client:
        attempt_key = f"login:attempts:{email}"
        attempts = await redis_client.get(attempt_key)
        if attempts and int(attempts) >= 5:
            ttl = await redis_client.ttl(attempt_key)
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {ttl} seconds.",
            )
        await redis_client.incr(attempt_key)
        await redis_client.expire(attempt_key, 60)

    # Dev mode — accept admin credentials loaded from env var (bypasses DB)
    # Security: dev mode requires BOTH EPMS_DEV_MODE=true AND EPMS_DEV_CREDENTIALS=base64json
    DEV_MODE = os.environ.get("EPMS_DEV_MODE", "").lower() in ("1", "true", "yes")
    DEV_CRED_B64 = os.environ.get("EPMS_DEV_CREDENTIALS", "")
    if DEV_MODE and DEV_CRED_B64:
        try:
            dev_creds = json.loads(base64.b64decode(DEV_CRED_B64).decode())
            if email == dev_creds.get("email", "") and credentials.password == dev_creds.get("password", ""):
                dev_user_id = dev_creds.get("user_id", "00000000-0000-0000-0000-000000000001")
                dev_role = dev_creds.get("role", "super_admin")
                dev_org_id = dev_creds.get("org_id", "00000000-0000-0000-0000-000000000000")
                access_token, access_exp = create_access_token(dev_user_id, email, dev_role, dev_org_id)
                refresh_token, refresh_exp = create_refresh_token(dev_user_id)
                return TokenResponse(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    user={
                        "id": dev_user_id,
                        "email": email,
                        "display_name": dev_creds.get("display_name", "Administrator"),
                        "role": dev_role,
                        "organization_id": dev_org_id,
                        "mfa_enabled": False,
                    },
                )
        except Exception:
            pass

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        # Look up user by email
        row = await conn.fetchrow(
            """SELECT u.id, u.email, u.password_hash, u.display_name, u.role,
               u.is_active, u.organization_id, u.mfa_enabled
               FROM users u
               WHERE u.email = $1 AND u.is_active = true""",
            email,
        )

        if not row:
            # Use constant-time comparison for the timing to prevent enumeration
            hash_password("dummy" + secrets.token_hex(8))
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password against stored hash
        stored_hash = row["password_hash"]
        if not stored_hash or not verify_password(credentials.password, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Clear rate limit on successful login
        if redis_client:
            await redis_client.delete(f"login:attempts:{email}")

        # Create tokens
        user_id = str(row["id"])
        org_id = str(row["organization_id"]) if row.get("organization_id") else ""
        access_token, access_exp = create_access_token(
            user_id, row["email"], row["role"], org_id
        )
        refresh_token, refresh_exp = create_refresh_token(user_id)

        # Log the login
        await conn.execute(
            "UPDATE users SET last_login = NOW() WHERE id = $1::uuid",
            user_id,
        )

        # Store refresh token in user_sessions
        await conn.execute(
            """INSERT INTO user_sessions (user_id, refresh_token, expires_at)
               VALUES ($1, $2, to_timestamp($3))""",
            user_id,
            refresh_token,
            refresh_exp,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user_id,
                "email": row["email"],
                "display_name": row["display_name"],
                "role": row["role"],
                "organization_id": str(row["organization_id"]),
                "mfa_enabled": row["mfa_enabled"],
            },
        )


# =============================================================
# AD/LDAP Login Endpoint
# =============================================================

@app.post("/api/v1/auth/ad-login", response_model=TokenResponse)
async def ad_login(credentials: ADLoginRequest):
    """Authenticate against Active Directory via LDAP bind.
    Falls back to local DB if AD is not configured.
    Auto-provisions user in local DB on first AD login."""
    email = credentials.email.strip().lower()

    # Rate limiting check (same as /auth/login)
    if redis_client:
        attempt_key = f"login:attempts:{email}"
        attempts = await redis_client.get(attempt_key)
        if attempts and int(attempts) >= 5:
            ttl = await redis_client.ttl(attempt_key)
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {ttl} seconds.",
            )
        await redis_client.incr(attempt_key)
        await redis_client.expire(attempt_key, 60)

    # Attempt AD authentication
    ad_user = await authenticate_ad(email, credentials.password)

    if ad_user is None:
        raise HTTPException(status_code=401, detail="AD authentication failed")

    if ad_user.get("_disabled"):
        logger.info("AD login not configured, falling back to local DB")
        raise HTTPException(status_code=501, detail="AD/LDAP not configured. Use /auth/login instead.")

    # Clear rate limit on successful login
    if redis_client:
        await redis_client.delete(f"login:attempts:{email}")

    # AD auth succeeded — find or create user in local DB
    if db_pool:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, display_name, role, organization_id, mfa_enabled "
                "FROM users WHERE email = $1",
                email,
            )

            if row:
                user_id = str(row["id"])
                org_id = str(row["organization_id"]) if row["organization_id"] else ""
                role = ad_user["role"]
                display_name = ad_user["display_name"]

                # Update role and display name from AD
                await conn.execute(
                    "UPDATE users SET role = $1, display_name = $2, last_login = NOW() WHERE id = $3::uuid",
                    role, display_name, user_id,
                )
            else:
                # Auto-provision: create user from AD data
                org_id = "00000000-0000-0000-0000-000000000000"
                user_id = str(uuid.uuid4())
                pwd_hash = hash_password(secrets.token_hex(32))
                await conn.execute(
                    """INSERT INTO users (id, email, password_hash, display_name, role, organization_id,
                       is_active, auth_provider) VALUES ($1, $2, $3, $4, $5, $6::uuid, true, 'ad')""",
                    user_id, email, pwd_hash, ad_user["display_name"], ad_user["role"], org_id,
                )
                display_name = ad_user["display_name"]

            access_token, access_exp = create_access_token(user_id, email, ad_user["role"], org_id)
            refresh_token, refresh_exp = create_refresh_token(user_id)

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user={
                    "id": user_id,
                    "email": email,
                    "display_name": display_name,
                    "role": ad_user["role"],
                    "organization_id": org_id,
                    "mfa_enabled": False,
                },
            )

    raise HTTPException(status_code=503, detail="Database not available")


@app.post("/api/v1/auth/refresh")
async def refresh_access_token(refresh_token_body: Dict[str, str] = None):
    """Refresh an expiring access token using a valid refresh token.
    Validates the refresh token against the database, then issues a new
    access token and rotates the refresh token."""
    if not refresh_token_body or "refresh_token" not in refresh_token_body:
        raise HTTPException(status_code=400, detail="refresh_token is required")

    token = refresh_token_body["refresh_token"]

    # Decode and validate the refresh JWT
    try:
        payload = decode_token(token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload["sub"]
    jti = payload["jti"]

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db_pool.acquire() as conn:
        # Verify refresh token exists in DB and is not revoked
        session = await conn.fetchrow(
            """SELECT id FROM user_sessions
               WHERE user_id = $1::uuid AND refresh_token = $2
               AND is_revoked = false AND expires_at > NOW()""",
            user_id,
            token,
        )
        if not session:
            raise HTTPException(status_code=401, detail="Refresh token has been revoked")

        # Revoke old session
        await conn.execute(
            "UPDATE user_sessions SET is_revoked = true WHERE id = $1",
            session["id"],
        )

    # Blacklist old refresh JWT
    if redis_client:
        await redis_client.setex(
            f"{TOKEN_BLACKLIST_PREFIX}{jti}",
            86400 * JWT_REFRESH_TOKEN_EXPIRE_DAYS,
            "revoked",
        )

    # Fetch user info for new tokens
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email, role, organization_id FROM users WHERE id = $1::uuid AND is_active = true",
            user_id,
        )
        if not row:
            raise HTTPException(status_code=401, detail="User account disabled")

    # Issue new tokens
    org_id = str(row["organization_id"]) if row.get("organization_id") else ""
    access_token, access_exp = create_access_token(user_id, row["email"], row["role"], org_id)
    refresh_token, refresh_exp = create_refresh_token(user_id)

    # Store new refresh token
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO user_sessions (user_id, refresh_token, expires_at)
               VALUES ($1, $2, to_timestamp($3))""",
            user_id,
            refresh_token,
            refresh_exp,
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@app.post("/api/v1/auth/logout")
async def logout(current_user: AuthContext = Depends(get_current_user)):
    """Logout by blacklisting the current JWT access token and revoking all refresh tokens.
    Uses the jti (JWT ID) claim to blacklist the token in Redis so it can't be used again.
    Also revokes all active sessions for the user in the database."""
    if redis_client:
        await redis_client.setex(
            f"{TOKEN_BLACKLIST_PREFIX}{current_user.jti}",
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60,
            "logged_out",
        )

    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE user_sessions SET is_revoked = true
                   WHERE user_id = $1::uuid AND is_revoked = false""",
                current_user.user_id,
            )

    logger.info(f"User {current_user.email} logged out, sessions revoked")
    return {"status": "ok", "message": "Logged out successfully"}


# =============================================================
# Notification Endpoints
# =============================================================

@app.post("/api/v1/notifications/send")
async def send_notification(
    req: NotificationRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Send a notification (in-app, email, or alert).
    Requires manager role or higher."""
    result = {"in_app": False, "email": False}

    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO notifications (user_id, title, message, notification_type, priority)
                   VALUES ($1, $2, $3, $4, $5)""",
                req.user_id, req.title, req.message, req.type, req.priority,
            )
            result["in_app"] = True

    # Send email if requested and configured
    if req.type == "email" and req.email:
        try:
            _send_email(req.email, req.title, req.message)
            result["email"] = True
        except Exception as e:
            logger.warning("Email send failed: %s", e)

    return {"status": "ok", "result": result}


@app.get("/api/v1/notifications")
async def get_notifications(
    limit: int = 50,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get in-app notifications for the current user."""
    rows_data = []
    if db_pool:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, title, message, notification_type, priority, is_read, created_at
                   FROM notifications WHERE user_id = $1::uuid
                   ORDER BY created_at DESC LIMIT $2""",
                current_user.user_id, limit,
            )
            for row in rows:
                rows_data.append({
                    "id": str(row["id"]),
                    "title": row["title"],
                    "message": row["message"],
                    "type": row["notification_type"],
                    "priority": row["priority"],
                    "is_read": row["is_read"],
                    "created_at": row["created_at"].isoformat(),
                })
    return {"notifications": rows_data}


@app.put("/api/v1/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    """Mark a notification as read."""
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE notifications SET is_read = true WHERE id = $1::uuid AND user_id = $2::uuid",
                notification_id, current_user.user_id,
            )
    return {"status": "ok"}


def _send_email(to: str, subject: str, body: str):
    """Send an email via configured SMTP server."""
    smtp_host = os.environ.get("EPMS_SMTP_HOST", "")
    smtp_port = int(os.environ.get("EPMS_SMTP_PORT", "587"))
    smtp_user = os.environ.get("EPMS_SMTP_USER", "")
    smtp_pass = os.environ.get("EPMS_SMTP_PASSWORD", "")
    smtp_from = os.environ.get("EPMS_SMTP_FROM", "noreply@epms.local")

    if not smtp_host:
        logger.warning("SMTP not configured — email not sent")
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


# =============================================================
# Report Generation Endpoints
# =============================================================

@app.post("/api/v1/reports/generate")
async def generate_report(
    req: ReportRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Generate a report (activity, productivity, browser, editor) in CSV format.
    Runs in background for larger datasets."""
    report_id = str(uuid.uuid4())
    report_dir = Path(os.environ.get("EPMS_REPORT_DIR", "reports"))
    report_dir.mkdir(exist_ok=True)

    # Store report record
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO reports (id, organization_id, report_type, title, format,
                   filters, created_by, created_at)
                   VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, NOW())""",
                report_id, current_user.org_id, req.type, req.report_title,
                req.format, json.dumps(req.model_dump()), current_user.user_id,
            )

    background_tasks.add_task(_build_report_file, report_id, req, db_pool, report_dir)

    return {
        "report_id": report_id,
        "status": "generating",
        "message": f"Report '{req.report_title}' is being generated",
    }


@app.get("/api/v1/reports/{report_id}")
async def get_report_status(
    report_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    """Get report status and download link."""
    if not db_pool:
        raise HTTPException(503, "Database not available")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, report_type, title, format, created_at, status, file_path "
            "FROM reports WHERE id = $1::uuid",
            report_id,
        )
        if not row:
            raise HTTPException(404, "Report not found")
        return {
            "id": str(row["id"]),
            "title": row["title"],
            "type": row["report_type"],
            "format": row["format"],
            "created_at": row["created_at"].isoformat(),
            "status": row["status"] or "completed",
            "download_url": f"/api/v1/reports/{report_id}/download" if row.get("file_path") else None,
        }


@app.get("/api/v1/reports/{report_id}/download")
async def download_report(
    report_id: str,
    current_user: AuthContext = Depends(get_current_user),
):
    """Download a generated report file."""
    if not db_pool:
        raise HTTPException(503, "Database not available")
    report_dir = Path(os.environ.get("EPMS_REPORT_DIR", "reports")).resolve()
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT format, file_path FROM reports WHERE id = $1::uuid",
            report_id,
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


# =============================================================
# Auth & Admin API Endpoints
# =============================================================


@app.get("/api/v1/auth/me")
async def get_current_user_info(current_user: AuthContext = Depends(get_current_user)):
    """Get current authenticated user info from JWT token."""
    return {
        "id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
        "organization_id": str(current_user.org_id) if current_user.org_id else "",
        "display_name": current_user.email.split("@")[0].capitalize() if current_user.email else "",
    }


@app.get("/api/v1/teams")
async def get_teams(current_user: AuthContext = Depends(get_current_user)):
    """List teams. Manager sees own org, Admin sees all."""
    teams = []
    if db_pool:
        async with db_pool.acquire() as conn:
            if current_user.role in ("admin", "super_admin"):
                rows = await conn.fetch("SELECT id, name, description, organization_id, created_at FROM teams ORDER BY name")
            else:
                rows = await conn.fetch(
                    "SELECT id, name, description, organization_id, created_at FROM teams WHERE organization_id = $1::uuid ORDER BY name",
                    current_user.org_id,
                )
            for row in rows:
                teams.append({
                    "id": str(row["id"]),
                    "name": row["name"],
                    "description": row["description"] or "",
                    "organization_id": str(row["organization_id"]),
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })
    return {"teams": teams}


@app.get("/api/v1/users")
async def get_users(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """List users. Manager sees own org, Admin sees all."""
    users = []
    if db_pool:
        async with db_pool.acquire() as conn:
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
                    "id": str(row["id"]),
                    "email": row["email"],
                    "display_name": row["display_name"] or row["email"].split("@")[0],
                    "role": row["role"],
                    "organization_id": str(row["organization_id"]) if row["organization_id"] else "",
                    "is_active": row["is_active"],
                    "last_login": row["last_login"].isoformat() if row["last_login"] else None,
                })
    return {"users": users}


@app.get("/api/v1/organizations")
async def get_organizations(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("admin")),
):
    """List all organizations. Admin only."""
    orgs = []
    if db_pool:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, display_name, created_at FROM organizations ORDER BY name")
            for row in rows:
                display_name = row["display_name"] or row["name"]
                orgs.append({
                    "id": str(row["id"]),
                    "name": row["name"],
                    "display_name": display_name,
                    "domain": display_name,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })
    return {"organizations": orgs}


@app.get("/api/v1/productivity-rules")
async def get_productivity_rules(
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """List productivity categorization rules for the organization."""
    rules = []
    if db_pool:
        async with db_pool.acquire() as conn:
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
                    "pattern": row["pattern"],
                    "category": row["category"],
                    "rule_type": row["rule_type"] or "glob",
                    "description": row["description"] or "",
                    "is_active": row["is_active"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                })
    return {"rules": rules}


@app.post("/api/v1/productivity-rules")
async def create_productivity_rule(
    req: ProductivityRuleRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Create a new productivity categorization rule."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    rule_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO productivity_rules (id, organization_id, pattern, category, rule_type, description)
               VALUES ($1, $2::uuid, $3, $4, $5, $6)""",
            rule_id, current_user.org_id, req.pattern, req.category, req.rule_type, req.description,
        )
    return {"id": rule_id, "status": "created"}


@app.put("/api/v1/productivity-rules/{rule_id}")
async def update_productivity_rule(
    rule_id: str,
    req: ProductivityRuleRequest,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Update an existing productivity rule."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE productivity_rules SET pattern=$1, category=$2, rule_type=$3, description=$4
               WHERE id=$5::uuid AND organization_id=$6::uuid""",
            req.pattern, req.category, req.rule_type, req.description, rule_id, current_user.org_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "updated"}


@app.delete("/api/v1/productivity-rules/{rule_id}")
async def delete_productivity_rule(
    rule_id: str,
    current_user: AuthContext = Depends(get_current_user),
    _rbac: None = Depends(require_role("manager")),
):
    """Delete a productivity rule."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM productivity_rules WHERE id=$1::uuid AND organization_id=$2::uuid",
            rule_id, current_user.org_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}


def _report_to_html(rows: List[Dict], title: str = "Report") -> str:
    """Convert a list of dicts to an HTML table report."""
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


async def _build_report_file(report_id: str, req: ReportRequest, pool, report_dir: Path):
    """Background task to build report CSV or HTML."""
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
        logger.error("Report build failed: %s", e)
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE reports SET status = 'failed' WHERE id = $1::uuid",
                    report_id,
                )


async def _query_report_data(pool, req: ReportRequest) -> List[Dict]:
    """Query report data as a list of dicts for HTML/JSON output."""
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


async def _build_activity_report(pool, req: ReportRequest, output_path: Path):
    """Build activity report CSV from heartbeats."""
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


async def _build_productivity_report(pool, req: ReportRequest, output_path: Path):
    """Build productivity scores report CSV."""
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


# =============================================================
# WebSocket Gateway Endpoint
# =============================================================

class WSConnectionManager:
    """Manages active WebSocket connections for agents and dashboards."""

    def __init__(self):
        self.agent_connections: Dict[str, Dict[str, Any]] = {}
        self.dashboard_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    @property
    def agent_count(self) -> int:
        return len(self.agent_connections)

    @property
    def dashboard_count(self) -> int:
        return len(self.dashboard_connections)

    async def connect_agent(self, agent_id: str, websocket: WebSocket, info: Dict[str, Any]):
        async with self._lock:
            if agent_id in self.agent_connections:
                old_ws = self.agent_connections[agent_id]["websocket"]
                try:
                    await old_ws.close(code=1000, reason="Replaced")
                except Exception:
                    pass
            self.agent_connections[agent_id] = {
                "websocket": websocket, "agent_info": info,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_message": time.time(), "message_count": 0,
            }

    async def disconnect_agent(self, agent_id: str):
        async with self._lock:
            self.agent_connections.pop(agent_id, None)

    async def connect_dashboard(self, session_id: str, websocket: WebSocket):
        async with self._lock:
            self.dashboard_connections[session_id] = websocket

    async def disconnect_dashboard(self, session_id: str):
        async with self._lock:
            self.dashboard_connections.pop(session_id, None)

    async def broadcast_to_dashboards(self, event_type: str, data: Dict[str, Any]):
        payload = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
        async with self._lock:
            disconnected = []
            for sid, ws in self.dashboard_connections.items():
                try:
                    await ws.send_text(payload)
                except Exception:
                    disconnected.append(sid)
            for sid in disconnected:
                self.dashboard_connections.pop(sid, None)

    async def send_to_agent(self, agent_id: str, message: Dict[str, Any]) -> bool:
        async with self._lock:
            conn = self.agent_connections.get(agent_id)
            if conn:
                try:
                    await conn["websocket"].send_text(json.dumps(message))
                    return True
                except Exception:
                    self.agent_connections.pop(agent_id, None)
            return False

    async def update_last_message(self, agent_id: str):
        async with self._lock:
            conn = self.agent_connections.get(agent_id)
            if conn:
                conn["last_message"] = time.time()
                conn["message_count"] += 1


ws_manager = WSConnectionManager()


@app.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    """WebSocket endpoint for agent connections.
    Authentication via first message handshake (JSON with api_key and agent_id)."""
    await websocket.accept()

    # Wait for auth handshake
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

    # Validate API key
    key_hash = hash_api_key(api_key)
    is_valid = False
    if db_pool:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT agent_id FROM agents WHERE api_key_hash = $1 AND is_active = true",
                key_hash,
            )
            if row:
                is_valid = True
                agent_id = row["agent_id"]

    if not is_valid:
        # Check enrollment token
        key_hash2 = hashlib.sha256(api_key.encode()).hexdigest()
        if db_pool:
            async with db_pool.acquire() as conn:
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

    await ws_manager.connect_agent(agent_id, websocket, {"display_name": display_name, "agent_id": agent_id})

    try:
        # Send connected confirmation
        await websocket.send_json({
            "type": "connected",
            "agent_id": agent_id,
            "heartbeat_interval_seconds": 30,
            "protocol_version": "1.0",
        })

        # Update agent online status
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agents SET is_online = true, last_heartbeat = NOW() WHERE agent_id = $1",
                    agent_id,
                )

        # Message loop
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")
                msg_data = msg.get("data", {})

                if msg_type == "heartbeat":
                    # Persist heartbeat to DB directly (no NATS needed)
                    fg = msg_data.get("foreground_window") or msg_data.get("active_window", {})
                    if db_pool:
                        async with db_pool.acquire() as conn:
                            await conn.execute(
                                """INSERT INTO agent_heartbeats
                                   (agent_id, timestamp, afk_seconds, is_afk,
                                    active_window_title, active_window_process,
                                    cpu_percent, memory_percent, memory_available_gb, uptime_seconds)
                                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                                agent_id,
                                msg_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                                msg_data.get("afk_seconds", 0),
                                msg_data.get("is_afk", False),
                                fg.get("title", ""),
                                fg.get("process_name", ""),
                                msg_data.get("system", {}).get("cpu", {}).get("percent"),
                                msg_data.get("system", {}).get("memory", {}).get("percent"),
                                msg_data.get("system", {}).get("memory", {}).get("available_gb"),
                                msg_data.get("system", {}).get("uptime_seconds"),
                            )

                            # Insert process events
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
                                            agent_id, ts,
                                            proc.get("process_name", ""),
                                            proc.get("process_path", ""),
                                            proc.get("pid", 0),
                                            proc.get("ppid", 0),
                                            proc.get("cpu_percent", 0),
                                            proc.get("memory_percent", 0),
                                            proc.get("is_foreground", False),
                                            proc.get("window_title", ""),
                                            proc.get("username", ""),
                                        )
                                    except Exception:
                                        pass

                    # Broadcast to dashboards
                    await ws_manager.broadcast_to_dashboards("heartbeat", {
                        "agent_id": agent_id,
                        "timestamp": msg_data.get("timestamp"),
                        "is_afk": msg_data.get("is_afk", False),
                        "active_window": fg.get("title", ""),
                    })

                    await ws_manager.update_last_message(agent_id)
                    await websocket.send_json({"type": "heartbeat_ack", "timestamp": datetime.now(timezone.utc).isoformat()})

                elif msg_type == "browser_activity" and db_pool:
                    async with db_pool.acquire() as conn:
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

                elif msg_type == "editor_activity" and db_pool:
                    async with db_pool.acquire() as conn:
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
        await ws_manager.disconnect_agent(agent_id)
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agents SET is_online = false WHERE agent_id = $1",
                    agent_id,
                )


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket, token: str = Query("")):
    """WebSocket endpoint for dashboard real-time updates.
    Query param: token (JWT access token for auth)"""
    await websocket.accept()

    if not token:
        await websocket.send_json({"type": "error", "message": "Missing token"})
        await websocket.close(code=1008)
        return

    # Verify JWT
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        session_id = payload.get("jti", token[:16])
    except HTTPException as e:
        await websocket.send_json({"type": "error", "message": e.detail or "Invalid token"})
        await websocket.close(code=1008)
        return

    await ws_manager.connect_dashboard(session_id, websocket)
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
        await ws_manager.disconnect_dashboard(session_id)


# =============================================================
# Main Entry Point
# =============================================================

if __name__ == "__main__":
    port = int(os.environ.get("EPMS_SERVER_PORT", os.environ.get("EPMS_API_PORT", "8000")))
    host = os.environ.get("EPMS_BIND_ADDRESS", "0.0.0.0")
    logger.info(f"Starting EPMS Consolidated Server on {host}:{port}")
    uvicorn.run(
        "epms_server_service:app",
        host=host,
        port=port,
        reload=False,
        workers=1,
        log_level="info",
    )
