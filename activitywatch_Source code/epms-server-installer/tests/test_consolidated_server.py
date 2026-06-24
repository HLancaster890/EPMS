"""
Full-flow integration tests for the EPMS Consolidated Server.

Covers the complete pipeline:
  Agent heartbeat (with process data)
    → REST API ingestion
    → PostgreSQL storage (agent_heartbeats + process_events)
    → Aggregation worker (process_events → app_sessions)

Also tests auth (login, AD fallback, refresh, logout), dashboard endpoints,
notifications, reports, and WebSocket gateway handshake.
"""

import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, call, PropertyMock
import time
from datetime import datetime, timezone
from fastapi.testclient import TestClient

os.environ["JWT_SECRET"] = "test-secret-dont-use-in-prod"
os.environ["EPMS_DEV_MODE"] = "1"
os.environ["EPMS_DEV_SECRET"] = "test-dev-secret"

import epms_server_service as svc

svc.db_pool = None
svc.redis_client = None
svc.JWT_SECRET = "test-secret-dont-use-in-prod"
svc.PASSWORD_HASH_ITERATIONS = 1


# =============================================================
# Auth bypass fixtures
# =============================================================

async def _mock_auth():
    return {
        "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "display_name": "Test Agent",
        "organization_id": "00000000-0000-0000-0000-000000000000",
        "is_active": True,
    }

async def _mock_user():
    return type("AuthContext", (), {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "admin@epms.local",
        "role": "super_admin",
        "jti": "test-jti-001",
        "org_id": "00000000-0000-0000-0000-000000000000",
    })()

async def _mock_rbac():
    return None

svc.app.dependency_overrides[svc.verify_api_key] = _mock_auth
svc.app.dependency_overrides[svc.validate_agent_identity] = _mock_auth
svc.app.dependency_overrides[svc.get_current_user] = _mock_user
svc.app.dependency_overrides[svc.require_role("manager")] = _mock_rbac
svc.app.dependency_overrides[svc.require_role("employee")] = _mock_rbac

client = TestClient(svc.app)

AGENT_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
ORG_ID = "00000000-0000-0000-0000-000000000000"

# Sample heartbeat with process data
PROCESS_SAMPLE = {
    "timestamp": "2026-06-23T10:00:00Z",
    "afk_seconds": 0,
    "is_afk": False,
    "active_window": {
        "title": "test.py - Visual Studio Code",
        "process_name": "Code.exe",
        "pid": 1234,
    },
    "browser_activity": {
        "browser_name": "chrome",
        "domain": "github.com",
        "url": "https://github.com/epms/enterprise",
        "page_title": "EPMS Enterprise - GitHub",
        "category": "development",
    },
    "editor_activity": {
        "editor_name": "VS Code",
        "project_name": "epms-server",
        "file_name": "test.py",
        "file_extension": ".py",
        "language": "python",
    },
    "system": {
        "cpu": {"percent": 15, "count": 8, "frequency_mhz": 3200},
        "memory": {"total_gb": 16, "available_gb": 8, "percent": 45},
        "disk": {"total_gb": 512, "free_gb": 200, "percent": 60},
        "uptime_seconds": 7200,
    },
    "processes": [
        {
            "pid": 1234, "ppid": 4321,
            "process_name": "Code.exe",
            "process_path": "C:\\Program Files\\VS Code\\Code.exe",
            "cpu_percent": 5.2, "memory_percent": 2.1,
            "is_foreground": True,
            "window_title": "test.py - Visual Studio Code",
            "username": "developer",
        },
        {
            "pid": 5678, "ppid": 4321,
            "process_name": "chrome.exe",
            "process_path": "C:\\Program Files\\Google\\Chrome\\chrome.exe",
            "cpu_percent": 12.5, "memory_percent": 8.3,
            "is_foreground": False,
            "window_title": "",
            "username": "developer",
        },
        {
            "pid": 9012, "ppid": 1,
            "process_name": "explorer.exe",
            "process_path": "C:\\Windows\\explorer.exe",
            "cpu_percent": 1.0, "memory_percent": 3.5,
            "is_foreground": False,
            "window_title": "",
            "username": "developer",
        },
    ],
}


# =============================================================
# Phase 1: Health & Info
# =============================================================

class TestHealth:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "disconnected"

    def test_health_live(self):
        resp = client.get("/health/live")
        assert resp.status_code == 200

    def test_health_ready(self):
        resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_api_health(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_server_info_authenticated(self):
        resp = client.get("/api/v1/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "name" in data


# =============================================================
# Phase 2: Auth Flow
# =============================================================

class TestAuth:
    def test_login_dev_mode(self):
        """Dev mode login bypass with EPMS_DEV_CREDENTIALS."""
        import os, base64, json
        old_mode = os.environ.get("EPMS_DEV_MODE")
        old_creds = os.environ.get("EPMS_DEV_CREDENTIALS")
        dev_creds = {
            "email": "admin@epms.local", "password": "Admin123!@#",
            "role": "super_admin", "display_name": "Administrator",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "org_id": "00000000-0000-0000-0000-000000000000",
        }
        os.environ["EPMS_DEV_MODE"] = "true"
        os.environ["EPMS_DEV_CREDENTIALS"] = base64.b64encode(json.dumps(dev_creds).encode()).decode()
        try:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@epms.local", "password": "Admin123!@#"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["email"] == "admin@epms.local"
            assert data["user"]["role"] == "super_admin"
        finally:
            if old_mode:
                os.environ["EPMS_DEV_MODE"] = old_mode
            else:
                os.environ.pop("EPMS_DEV_MODE", None)
            if old_creds:
                os.environ["EPMS_DEV_CREDENTIALS"] = old_creds
            else:
                os.environ.pop("EPMS_DEV_CREDENTIALS", None)

    def test_login_invalid_credentials(self):
        """Without DB, invalid creds get 503 (dev mode only accepts exact match)."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@epms.local", "password": "wrong-password"},
        )
        # Without DB pool, dev mode bypass only matches exact dev creds,
        # so wrong password falls through to "Database not available"
        assert resp.status_code == 503

    def test_login_missing_email(self):
        """Missing email in request returns 422 validation error."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"password": "Admin123!@#"},
        )
        assert resp.status_code == 422

    def test_ad_login_not_configured(self):
        """AD login returns 501 when LDAP is not configured."""
        resp = client.post(
            "/api/v1/auth/ad-login",
            json={"email": "admin@epms.local", "password": "Admin123!@#"},
        )
        assert resp.status_code == 501

    def test_ad_login_invalid_email(self):
        """Invalid email format returns 422."""
        resp = client.post(
            "/api/v1/auth/ad-login",
            json={"email": "not-an-email", "password": "Admin123!@#"},
        )
        assert resp.status_code == 422

    def test_auth_required_on_dashboard(self):
        """Dashboard endpoints require valid auth.
        Remove override temporarily to test 401."""
        svc.app.dependency_overrides.pop(svc.get_current_user, None)
        try:
            resp = client.get("/api/v1/dashboard/summary")
            assert resp.status_code == 401
        finally:
            svc.app.dependency_overrides[svc.get_current_user] = _mock_user

    def test_refresh_token_missing(self):
        """Refresh token endpoint requires body."""
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 400


# =============================================================
# Phase 3: Agent Heartbeat with Process Data
# =============================================================

class TestHeartbeatWithProcesses:
    """Core full-flow test: agent sends heartbeat with process data,
    server stores it in both agent_heartbeats and process_events."""

    def test_heartbeat_accepts_process_data(self):
        """Send a heartbeat with process array, verify 200 response."""
        resp = client.post("/api/v1/agent/heartbeat", json=PROCESS_SAMPLE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["agent_id"] != ""
        assert "timestamp" in data

    def test_heartbeat_stores_process_events(self):
        """With a mock DB pool, verify process_events INSERT SQL is called
        for each process in the heartbeat."""
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        conn.fetchrow = AsyncMock(return_value=None)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)
        svc.db_pool = pool

        try:
            resp = client.post("/api/v1/agent/heartbeat", json=PROCESS_SAMPLE)
            assert resp.status_code == 200

            # Verify: agent heartbeat INSERT called
            heartbeat_calls = [
                c for c in conn.execute.call_args_list
                if "agent_heartbeats" in str(c)
            ]
            assert len(heartbeat_calls) >= 1, (
                f"Expected agent_heartbeats INSERT, got calls: {conn.execute.call_args_list}"
            )

            # Verify: process_events INSERT called for each of 3 processes
            process_calls = [
                c for c in conn.execute.call_args_list
                if "process_events" in str(c)
            ]
            assert len(process_calls) == 3, (
                f"Expected 3 process_events INSERTs, got {len(process_calls)}: "
                f"{[str(c) for c in process_calls]}"
            )

            # Verify: first process_events INSERT has foreground process data
            first_call = process_calls[0]
            first_args = first_call[0] if isinstance(first_call, tuple) else first_call.args
            sql = str(first_args[0])
            assert "INSERT INTO process_events" in sql
            assert "Code.exe" in str(first_args)

            # Verify: browser_activity INSERT called
            browser_calls = [
                c for c in conn.execute.call_args_list
                if "browser_activity" in str(c)
            ]
            assert len(browser_calls) == 1

            # Verify: editor_activity INSERT called
            editor_calls = [
                c for c in conn.execute.call_args_list
                if "editor_activity" in str(c)
            ]
            assert len(editor_calls) == 1

        finally:
            svc.db_pool = None

    def test_heartbeat_without_processes(self):
        """Heartbeat without process array should still work."""
        minimal_heartbeat = {
            "timestamp": "2026-06-23T11:00:00Z",
            "afk_seconds": 120,
            "is_afk": True,
            "active_window": {"title": "", "process_name": "", "pid": 0},
            "system": {"cpu": {"percent": 5}, "memory": {"percent": 30}},
        }
        resp = client.post("/api/v1/agent/heartbeat", json=minimal_heartbeat)
        assert resp.status_code == 200

    def test_heartbeat_with_empty_processes(self):
        """Heartbeat with empty process array should not cause process_events INSERT."""
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        conn.fetchrow = AsyncMock(return_value=None)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)
        svc.db_pool = pool

        try:
            hb = {**PROCESS_SAMPLE, "processes": []}
            resp = client.post("/api/v1/agent/heartbeat", json=hb)
            assert resp.status_code == 200

            process_calls = [
                c for c in conn.execute.call_args_list
                if "process_events" in str(c)
            ]
            assert len(process_calls) == 0, (
                f"Empty process list should generate no INSERTs, got {len(process_calls)}"
            )
        finally:
            svc.db_pool = None

    def test_heartbeat_requires_api_key(self):
        """Without auth override, heartbeat should fail."""
        svc.app.dependency_overrides.pop(svc.verify_api_key, None)
        svc.app.dependency_overrides.pop(svc.validate_agent_identity, None)
        try:
            resp = client.post("/api/v1/agent/heartbeat", json=PROCESS_SAMPLE)
            assert resp.status_code in (401, 403)
        finally:
            svc.app.dependency_overrides[svc.verify_api_key] = _mock_auth
            svc.app.dependency_overrides[svc.validate_agent_identity] = _mock_auth


# =============================================================
# Phase 4: Agent Registration
# =============================================================

class TestAgentRegistration:
    def test_register_agent_no_db_graceful(self):
        """Agent registration returns agent_id even without DB."""
        resp = client.post(
            "/api/v1/agent/register",
            json={"hostname": "test-pc", "os": "Windows"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_id" in data
        assert "api_key" in data

    def test_register_agent_with_db(self):
        """Agent registration with DB pool stores agent record."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[
            None,  # First call: no existing agent
            None,  # Second call: from registration flow
        ])
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)
        svc.db_pool = pool
        try:
            resp = client.post(
                "/api/v1/agent/register",
                json={"hostname": "test-pc", "os": "Windows"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "agent_id" in data
        finally:
            svc.db_pool = None


# =============================================================
# Phase 5: Dashboard Endpoints
# =============================================================

class TestDashboard:
    def test_summary(self):
        resp = client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_devices" in data
        assert "online_devices" in data

    def test_devices(self):
        resp = client.get("/api/v1/dashboard/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert "devices" in data

    def test_activity(self):
        resp = client.get("/api/v1/dashboard/activity?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data

    def test_browser_activity(self):
        resp = client.get("/api/v1/dashboard/browser-activity?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data

    def test_editor_activity(self):
        resp = client.get("/api/v1/dashboard/editor-activity?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data

    def test_alerts(self):
        resp = client.get("/api/v1/dashboard/alerts?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data

    def test_reports_list(self):
        resp = client.get("/api/v1/dashboard/reports?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "reports" in data


# =============================================================
# Phase 6: Analytics
# =============================================================

class TestAnalytics:
    def test_productivity_data(self):
        resp = client.get("/api/v1/analytics/productivity?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["period_days"] == 7


# =============================================================
# Phase 7: Notifications Flow
# =============================================================

class TestNotifications:
    def test_send_notification(self):
        """Send an in-app notification (requires manager role)."""
        resp = client.post(
            "/api/v1/notifications/send",
            json={
                "type": "in_app",
                "title": "Test Alert",
                "message": "This is a test notification",
                "user_id": "00000000-0000-0000-0000-000000000001",
                "priority": "normal",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_get_notifications(self):
        """Get notifications for the authenticated user."""
        resp = client.get("/api/v1/notifications?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "notifications" in data

    def test_mark_notification_read(self):
        """Mark a notification as read."""
        resp = client.put(
            "/api/v1/notifications/00000000-0000-0000-0000-000000000000/read",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_send_notification_without_auth(self):
        """Without auth, notification endpoints return 401."""
        svc.app.dependency_overrides.pop(svc.get_current_user, None)
        try:
            resp = client.post(
                "/api/v1/notifications/send",
                json={"type": "in_app", "title": "Test", "message": "Test"},
            )
            assert resp.status_code == 401
        finally:
            svc.app.dependency_overrides[svc.get_current_user] = _mock_user


# =============================================================
# Phase 8: Report Generation Flow
# =============================================================

class TestReports:
    def test_generate_report(self):
        """Generate an activity report in CSV format (requires manager role)."""
        resp = client.post(
            "/api/v1/reports/generate",
            json={
                "type": "activity",
                "format": "csv",
                "report_title": "Test Activity Report",
                "date_from": "2026-06-01",
                "date_to": "2026-06-23",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "report_id" in data
        assert data["status"] == "generating"

    def test_get_report_status(self):
        """Get report generation status."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)
        svc.db_pool = pool
        try:
            resp = client.get(
                "/api/v1/reports/00000000-0000-0000-0000-000000000000",
            )
            assert resp.status_code == 404
        finally:
            svc.db_pool = None

    def test_download_report_not_found(self):
        """Download non-existent report returns 404."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)
        svc.db_pool = pool
        try:
            resp = client.get(
                "/api/v1/reports/00000000-0000-0000-0000-000000000000/download",
            )
            assert resp.status_code == 404
        finally:
            svc.db_pool = None


# =============================================================
# Phase 9: Aggregation & Scoring
# =============================================================

class TestAggregation:
    """Test the internal aggregation functions directly."""

    @pytest.mark.asyncio
    async def test_purge_process_data(self):
        """Purge function should handle empty DB gracefully."""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(side_effect=[
            0,  # No agents returned
        ])
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)

        from epms_server.aggregation import _purge_old_data
        await _purge_old_data(pool)
        # Should not raise

    @pytest.mark.asyncio
    async def test_aggregate_productivity_with_no_agents(self):
        """Scoring with no online agents should not raise."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)

        from epms_server.aggregation import _aggregate_productivity_scores
        await _aggregate_productivity_scores(pool)
        # Should not raise

    @pytest.mark.asyncio
    async def test_score_agent_interval_no_heartbeats(self):
        """Scoring an agent with no recent heartbeats should not raise."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)

        from epms_server.aggregation import _score_agent_interval
        await _score_agent_interval(pool, AGENT_ID, ORG_ID)
        # Should not raise

    @pytest.mark.asyncio
    async def test_aggregate_app_sessions_empty(self):
        """App session aggregation with no recent process_events should not raise."""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)

        from epms_server.aggregation import _aggregate_app_sessions
        await _aggregate_app_sessions(pool)
        # Should not raise


# =============================================================
# Phase 10: RBAC Middleware
# =============================================================

class TestRBAC:
    """Test the RBAC module directly."""

    def test_role_enum_values(self):
        from epms_server.rbac import Role
        assert Role.EMPLOYEE < Role.MANAGER
        assert Role.MANAGER < Role.ADMIN
        assert Role.ADMIN < Role.SUPER_ADMIN

    def test_role_map_contains_all_roles(self):
        from epms_server.rbac import ROLE_MAP
        assert "employee" in ROLE_MAP
        assert "manager" in ROLE_MAP
        assert "admin" in ROLE_MAP
        assert "super_admin" in ROLE_MAP

    def test_require_role_unknown_raises(self):
        from epms_server.rbac import require_role
        import pytest
        with pytest.raises(ValueError, match="Unknown role"):
            require_role("nonexistent_role")

    def test_require_role_super_admin_accepts_admin(self):
        """super_admin should pass any require_role check."""
        from epms_server.rbac import require_role
        user = type("AuthContext", (), {"role": "super_admin"})()
        # Should not raise
        import asyncio
        asyncio.run(require_role("employee")(user))

    def test_filter_by_role_admin(self):
        """Admin role returns no SQL filter."""
        from epms_server.rbac import filter_by_role
        user = type("AuthContext", (), {"role": "admin", "org_id": ""})()
        result = filter_by_role(user, "a")
        assert result == ""

    def test_filter_by_role_employee(self):
        """Employee role filters by agent_id."""
        from epms_server.rbac import filter_by_role
        user = type("AuthContext", (), {
            "role": "employee",
            "user_id": "u-123",
            "org_id": "",
        })()
        result = filter_by_role(user, "a")
        assert "a.agent_id" in result
        assert "u-123" in result

    def test_can_access_agent_admin(self):
        from epms_server.rbac import can_access_agent
        user = type("AuthContext", (), {"role": "admin", "user_id": "", "org_id": ""})()
        assert can_access_agent(user, "any-org") is True

    def test_can_access_agent_employee_own(self):
        from epms_server.rbac import can_access_agent
        user = type("AuthContext", (), {"role": "employee", "user_id": "u-1", "org_id": ""})()
        assert can_access_agent(user, "u-1") is True
        assert can_access_agent(user, "u-2") is False


# =============================================================
# Phase 11: AD Login Module
# =============================================================

class TestADLogin:
    @pytest.mark.asyncio
    async def test_authenticate_ad_not_configured(self):
        """When AD is not configured, returns _disabled sentinel."""
        from epms_server.ad_login import authenticate_ad
        result = await authenticate_ad("test@example.com", "password")
        assert result is not None
        assert result.get("_disabled") is True

    @pytest.mark.asyncio
    async def test_authenticate_ad_no_ldap_library(self):
        """Without ldap3 installed, returns _disabled."""
        from epms_server.ad_login import authenticate_ad
        import sys
        if "ldap3" not in sys.modules:
            result = await authenticate_ad("test@example.com", "password")
            assert result is not None
            assert result.get("_disabled") is True

    def test_default_role_map(self):
        from epms_server.ad_login import DEFAULT_ROLE_MAP
        assert "EPMS-Admins" in DEFAULT_ROLE_MAP
        assert DEFAULT_ROLE_MAP["EPMS-Admins"] == "super_admin"
        assert DEFAULT_ROLE_MAP["Domain Users"] == "employee"


# =============================================================
# Phase 12: WebSocket Gateway Handshake
# =============================================================

class TestWebSocketGateway:
    """Test WebSocket gateway handshake through FastAPI TestClient's
    WebSocket test mode (no real sockets)."""

    def test_ws_agent_rejects_no_api_key(self):
        """WebSocket without auth handshake should be rejected."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"type": "hello"})  # not an auth message
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "api_key" in data["message"].lower()

    def test_ws_agent_with_auth(self):
        """WebSocket auth handshake then receive welcome."""
        svc.app.dependency_overrides.pop(svc.verify_api_key, None)
        svc.app.dependency_overrides.pop(svc.validate_agent_identity, None)

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={
            "agent_id": AGENT_ID,
            "display_name": "Test Agent",
            "organization_id": ORG_ID,
        })
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)
        svc.db_pool = pool

        try:
            with client.websocket_connect("/ws/agent") as ws:
                ws.send_json({
                    "type": "auth", "api_key": "test-key",
                    "agent_id": AGENT_ID, "display_name": "Test Agent",
                })
                data = ws.receive_json()
                assert data["type"] == "connected"
                assert "agent_id" in data
        finally:
            svc.db_pool = None
            svc.app.dependency_overrides[svc.verify_api_key] = _mock_auth
            svc.app.dependency_overrides[svc.validate_agent_identity] = _mock_auth

    def test_ws_agent_heartbeat_via_websocket(self):
        """Send auth handshake, then heartbeat through WebSocket."""
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        conn.fetchrow = AsyncMock(return_value={"agent_id": AGENT_ID})
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=cm)
        svc.db_pool = pool
        svc.app.dependency_overrides.pop(svc.verify_api_key, None)
        svc.app.dependency_overrides.pop(svc.validate_agent_identity, None)

        try:
            with client.websocket_connect("/ws/agent") as ws:
                ws.send_json({
                    "type": "auth", "api_key": "test-key",
                    "agent_id": AGENT_ID, "display_name": "Test",
                })
                ws.receive_json()  # welcome

                ws.send_json({"type": "heartbeat", "data": PROCESS_SAMPLE})
                ack = ws.receive_json()
                assert ack["type"] == "heartbeat_ack"

                # Verify process_events INSERT calls
                process_calls = [
                    c for c in conn.execute.call_args_list
                    if "process_events" in str(c)
                ]
                assert len(process_calls) == 3

                # Verify browser event via WS
                ws.send_json({
                    "type": "browser_activity",
                    "data": {"browser_name": "firefox", "domain": "example.com"},
                })
                browser_ack = ws.receive_json()
                assert browser_ack["type"] == "browser_ack"
        finally:
            svc.db_pool = None
            svc.app.dependency_overrides[svc.verify_api_key] = _mock_auth
            svc.app.dependency_overrides[svc.validate_agent_identity] = _mock_auth

    def test_ws_dashboard_rejects_no_token(self):
        """Dashboard WebSocket without token should be rejected."""
        with client.websocket_connect(
            "/ws/dashboard",
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "token" in data["message"].lower()

    def test_ws_dashboard_with_token(self):
        """Dashboard WebSocket with valid JWT token should connect."""
        import jwt as pyjwt
        token = pyjwt.encode({
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "admin@epms.local", "role": "super_admin",
            "org_id": "00000000-0000-0000-0000-000000000000",
            "type": "access", "jti": "test-jti",
            "iat": int(time.time()), "exp": int(time.time()) + 3600,
        }, svc.JWT_SECRET, algorithm="HS256")

        svc.app.dependency_overrides.pop(svc.get_current_user, None)
        try:
            with client.websocket_connect(
                f"/ws/dashboard?token={token}",
            ) as ws:
                data = ws.receive_json()
                assert data["type"] == "connected"
                assert "session_id" in data
        finally:
            svc.app.dependency_overrides[svc.get_current_user] = _mock_user
