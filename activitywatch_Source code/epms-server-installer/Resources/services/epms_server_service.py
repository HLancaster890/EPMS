"""
EPMS Enterprise Server — Consolidated Service Entry Point
Thin orchestrator that creates the FastAPI app, configures middleware,
includes routers from the routes/ package, and runs the server.
"""

import os
import sys
import json
import logging
import asyncio
import contextlib
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from epms_server import config as _config
from epms_server.config import JWT_SECRET, PASSWORD_HASH_ITERATIONS
from epms_server.rbac import get_current_user, require_role

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from epms_common import setup_cors
import asyncpg
import uvicorn

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

# Import shared state as module reference (mutable — propagates to all route modules)
import routes.state as app_state
from routes import helpers as route_helpers
from routes.auth_routes import router as auth_router
from routes.agent_routes import router as agent_router
from routes.remaining_routes import router as remaining_router

# Re-export helper functions for test backward compatibility
from routes.helpers import (
    _parse_ts, get_db, hash_password, verify_password, hash_api_key,
    create_access_token, create_refresh_token, verify_api_key,
    validate_agent_identity, check_agent_rate_limit,
    _aggregation_worker, _aggregate_productivity_scores,
    _aggregate_app_sessions, _purge_process_data,
    _compute_health_score, _send_email,
    _report_to_html, _build_report_file, _query_report_data,
    _build_activity_report, _build_productivity_report,
)
from routes.models import (
    HealthResponse, AgentRegister, AgentHeartbeat, NotificationRequest,
    ReportRequest, ProductivityRuleRequest, ProductivityRuleResponse,
    BrowserEvent, EditorEvent, BatchEvents, LoginRequest, ADLoginRequest,
    TokenResponse, SystemInventoryResponse, InventorySummaryResponse,
    HealthDeviceResponse, HealthAnomalyItem, ExecutiveSummaryResponse,
    EnrollmentTokenRequest,
)

# =============================================================
# Lifespan
# =============================================================

@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    if not JWT_SECRET:
        app_state.logger.critical("JWT_SECRET not set! Authentication is DISABLED. Set a strong random secret.")
    if not os.environ.get("EPMS_API_KEY_PEPPER", ""):
        app_state.logger.critical("EPMS_API_KEY_PEPPER not set! API key hashing uses weak fallback. Set a strong random secret.")
        app_state._API_KEY_PEPPER = "epms-api-key-fallback-do-not-use-in-production"

    config = {}
    try:
        if os.path.exists(app_state.CONFIG_PATH):
            with open(app_state.CONFIG_PATH) as f:
                config = json.load(f)
    except Exception as e:
        app_state.logger.warning(f"Could not load config: {e}")

    db_config = config.get("database", {})
    redis_config = config.get("redis", {})

    try:
        pool = await asyncpg.create_pool(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            database=db_config.get("name", "epms"),
            user=db_config.get("user", "postgres"),
            password=db_config.get("password", ""),
            min_size=2,
            max_size=db_config.get("max_connections", 20),
        )
        app_state.db_pool = pool
        app_state.logger.info("Database connection pool created")
    except Exception as e:
        app_state.logger.warning(f"Database connection failed: {e}")

    try:
        rc = aioredis.Redis(
            host=redis_config.get("host", "localhost"),
            port=redis_config.get("port", 6379),
            password=redis_config.get("password", None) or None,
            db=0,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=False,
        )
        await asyncio.wait_for(rc.ping(), timeout=5)
        app_state.redis_client = rc
        app_state.logger.info("Redis connection established")
    except Exception as e:
        app_state.logger.warning(f"Redis connection failed: {e}")
        app_state.redis_client = None
    _config.redis_client = app_state.redis_client

    aggregation_task = asyncio.create_task(route_helpers._aggregation_worker())
    app_state.logger.info("Aggregation worker scheduled")

    yield

    aggregation_task.cancel()
    try:
        await aggregation_task
    except asyncio.CancelledError:
        pass
    if app_state.db_pool:
        await app_state.db_pool.close()
    if app_state.redis_client:
        await app_state.redis_client.close()
    _config.redis_client = None
    app_state.logger.info("Server shutdown complete")


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
    app_state.logger.warning("CORS_ORIGINS not set — defaulting to http://localhost:3000. Set explicit origins for production.")
    cors_origins = "http://localhost:3000"
setup_cors(app, cors_origins)

trusted_hosts_str = os.environ.get("TRUSTED_HOSTS", "")
trusted_hosts = [h.strip() for h in trusted_hosts_str.split(",") if h.strip()]
if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-XSS-Protection"] = "0"
    return response


# Include routers
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(remaining_router)


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
        app_state.logger.info(f"Web dashboard mounted at /dashboard from {_web_ui_path}")
    else:
        app_state.logger.warning(f"No index.html in {_web_ui_path} — /dashboard disabled")
else:
    app_state.logger.info("Web dashboard not found — /dashboard endpoint disabled")


# =============================================================
# Module Proxy — Backward compatibility for tests (svc.db_pool = ...)
# =============================================================

class _SvcModule(types.ModuleType):
    """Proxies attribute access to routes.state so svc.db_pool = x
    propagates to app_state.db_pool = x, keeping route modules in sync."""

    @property
    def db_pool(self):
        return app_state.db_pool

    @db_pool.setter
    def db_pool(self, value):
        app_state.db_pool = value

    @property
    def redis_client(self):
        return app_state.redis_client

    @redis_client.setter
    def redis_client(self, value):
        app_state.redis_client = value

    @property
    def start_time(self):
        return app_state.start_time

    @start_time.setter
    def start_time(self, value):
        app_state.start_time = value

    @property
    def ws_manager(self):
        return app_state.ws_manager


sys.modules[__name__].__class__ = _SvcModule


# =============================================================
# Main Entry Point
# =============================================================

if __name__ == "__main__":
    port = int(os.environ.get("EPMS_SERVER_PORT", os.environ.get("EPMS_API_PORT", "8000")))
    host = os.environ.get("EPMS_BIND_ADDRESS", "0.0.0.0")
    app_state.logger.info(f"Starting EPMS Consolidated Server on {host}:{port}")
    uvicorn.run(
        "epms_server_service:app",
        host=host,
        port=port,
        reload=False,
        workers=1,
        log_level="info",
    )