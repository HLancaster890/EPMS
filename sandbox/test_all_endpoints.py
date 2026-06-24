"""Comprehensive EPMS API endpoint test suite."""
import httpx, sys, json
from datetime import datetime

BASE = "http://localhost:8000/api/v1"
passed = 0
failed = 0

def ok(name, status, expected=200):
    global passed, failed
    if status == expected:
        passed += 1
        print(f"  [PASS] {name}: {status}")
    else:
        failed += 1
        print(f"  [FAIL] {name}: expected {expected}, got {status}")

async def run():
    token = None

    print("\n=== AUTH ===\n")
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/auth/login", json={
            "email": "admin@corp.local", "password": "MyP@ss1"
        })
        ok("POST /auth/login", r.status_code)
        if r.status_code == 200:
            token = r.json()["access_token"]

        r = await c.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
        ok("GET /auth/me", r.status_code)
        if r.status_code == 200:
            me = r.json()
            assert me.get("email") == "admin@corp.local", f"Bad email: {me}"
            assert me.get("role"), f"Missing role: {me}"
            print(f"     User: {me['email']} ({me['role']})")

    headers = {"Authorization": f"Bearer {token}"}

    print("\n=== DASHBOARD ===\n")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/dashboard/summary?period=today", headers=headers)
        ok("GET /dashboard/summary", r.status_code)
        if r.status_code == 200:
            s = r.json()
            print(f"     Devices: {s.get('total_devices')}, Active: {s.get('active_devices')}, "
                  f"Events: {s.get('events_today')}, Avg Prod: {s.get('avg_productivity')}")
            assert "active_devices" in s, "Missing active_devices"
            assert "avg_productivity" in s, "Missing avg_productivity"
            assert "events_today" in s, "Missing events_today"

        r = await c.get(f"{BASE}/dashboard/devices", headers=headers)
        ok("GET /dashboard/devices", r.status_code)
        if r.status_code == 200:
            devices = r.json().get("devices", [])
            print(f"     {len(devices)} devices returned")
            for d in devices:
                assert "id" in d, f"Device missing id: {d}"
                assert "name" in d, f"Device missing name: {d}"

        r = await c.get(f"{BASE}/dashboard/activity?limit=10", headers=headers)
        ok("GET /dashboard/activity", r.status_code)
        if r.status_code == 200:
            events = r.json().get("events", [])
            print(f"     {len(events)} activity events")
            for e in events[:3]:
                assert "app" in e, f"Activity missing app: {e}"
                assert "time" in e, f"Activity missing time: {e}"

        r = await c.get(f"{BASE}/dashboard/browser-activity", headers=headers)
        ok("GET /dashboard/browser-activity", r.status_code)
        if r.status_code == 200:
            data = r.json()
            events = data if isinstance(data, list) else data.get("events", [])
            print(f"     {len(events)} browser events")
            if events:
                assert "browser" in events[0] or "browser_name" in events[0], \
                    f"Browser missing name: {events[0]}"

        r = await c.get(f"{BASE}/dashboard/editor-activity", headers=headers)
        ok("GET /dashboard/editor-activity", r.status_code)
        if r.status_code == 200:
            data = r.json()
            events = data if isinstance(data, list) else data.get("events", [])
            print(f"     {len(events)} editor events")
            if events:
                assert "editor" in events[0] or "editor_name" in events[0], \
                    f"Editor missing name: {events[0]}"

        r = await c.get(f"{BASE}/dashboard/alerts", headers=headers)
        ok("GET /dashboard/alerts", r.status_code)
        if r.status_code == 200:
            data = r.json()
            alerts = data if isinstance(data, list) else data.get("alerts", [])
            print(f"     {len(alerts)} alerts")
            if alerts:
                assert "message" in alerts[0], f"Alert missing message: {alerts[0]}"
                assert "acknowledged" in alerts[0], f"Alert missing acknowledged: {alerts[0]}"
                ack_id = alerts[0]["id"]
                r2 = await c.post(f"{BASE}/dashboard/alerts/{ack_id}/acknowledge", headers=headers)
                ok(f"POST /dashboard/alerts/{ack_id}/acknowledge", r2.status_code)

        r = await c.get(f"{BASE}/dashboard/reports", headers=headers)
        ok("GET /dashboard/reports", r.status_code)
        if r.status_code == 200:
            data = r.json()
            reports = data if isinstance(data, list) else data.get("reports", [])
            print(f"     {len(reports)} reports")
            if reports:
                assert "name" in reports[0], f"Report missing name: {reports[0]}"
                assert "status" in reports[0], f"Report missing status: {reports[0]}"

    print("\n=== ANALYTICS ===\n")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/analytics/productivity?days=7&period=week", headers=headers)
        ok("GET /analytics/productivity", r.status_code)
        if r.status_code == 200:
            data = r.json()
            scores = data.get("data", [])
            print(f"     {len(scores)} days of productivity data")
            for s in scores[:3]:
                assert "date" in s, f"Missing date: {s}"
                assert "score" in s, f"Missing score: {s}"
                assert "productive_seconds" in s, f"Missing productive_seconds: {s}"

    print("\n=== TEAMS / USERS / ORGS / RULES ===\n")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/teams", headers=headers)
        ok("GET /teams", r.status_code)
        teams = r.json().get("teams", []) if r.status_code == 200 else []

        r = await c.get(f"{BASE}/users", headers=headers)
        ok("GET /users", r.status_code)
        if r.status_code == 200:
            users = r.json().get("users", [])
            print(f"     {len(users)} users")
            for u in users:
                assert "display_name" in u, f"User missing display_name: {u}"
                assert "role" in u, f"User missing role: {u}"

        r = await c.get(f"{BASE}/organizations", headers=headers)
        ok("GET /organizations", r.status_code)
        if r.status_code == 200:
            orgs = r.json().get("organizations", [])
            print(f"     {len(orgs)} organizations")
            for o in orgs:
                assert "domain" in o, f"Org missing domain: {o}"

        r = await c.get(f"{BASE}/productivity-rules", headers=headers)
        ok("GET /productivity-rules", r.status_code)

    print("\n=== AGENT ENDPOINTS ===\n")
    print("  [SKIP] Agent endpoints require API key auth (not user JWT)")
    print("         Tested separately via heartbeat_simulator.py")

    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed of {passed + failed} total")
    print(f"{'='*50}")
    return failed == 0

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(run())
    sys.exit(0 if success else 1)
