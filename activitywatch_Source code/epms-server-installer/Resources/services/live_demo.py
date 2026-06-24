"""EPMS Live Demo - starts server, tests endpoints, then cleans up."""
import asyncio, json, os, sys, threading, time, logging, base64
from pathlib import Path

os.chdir(Path(__file__).parent)
dev_creds_b64 = base64.b64encode(
    json.dumps({"email":"admin@corp.local","password":"MyP@ss1"}).encode()
).decode()

os.environ["JWT_SECRET"] = "demo-secret-12345"
os.environ["EPMS_API_KEY_PEPPER"] = "demo-pepper-67890"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "5432"
os.environ["EPMS_DEV_MODE"] = "true"
os.environ["EPMS_DEV_CREDENTIALS"] = dev_creds_b64

import uvicorn
from epms_server_service import app
import httpx

SERVER_URL = "http://127.0.0.1:8000"

def start_server():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="critical")

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
time.sleep(5)

box = "=" * 60

try:
    with httpx.Client(base_url=SERVER_URL, timeout=10) as c:
        print(box)
        print("  EPMS ENTERPRISE - LIVE DEMO")
        print(box)

        # 1. HEALTH CHECK
        print("\n** 1. Health Check")
        r = c.get("/health")
        print(f"   GET /health -> {r.status_code}")
        health = r.json()
        for k, v in health.items():
            print(f"     {k}: {v}")

        # 2. LOGIN (dev mode)
        print("\n** 2. Dev Mode Login (no DB)")
        print("   EPMS_DEV_MODE=true, EPMS_DEV_CREDENTIALS=base64({email,password})")
        r = c.post("/api/v1/auth/login", json={
            "email": "admin@epms.local",
            "password": "Admin123!@#",
        })
        print(f"   POST /api/v1/auth/login -> {r.status_code}")
        if r.status_code == 200:
            body = r.json()
            token = body.get("access_token", "")[:50] + "..."
            print(f"   access_token: {token}")
            print(f"   user role: {body.get('user', {}).get('role', 'N/A')}")
            print(f"   user email: {body.get('user', {}).get('email', 'N/A')}")
        else:
            print(f"   {r.text[:200]}")

        # 3. WRONG CREDENTIALS REJECTED
        print("\n** 3. Wrong Credentials Rejected")
        r = c.post("/api/v1/auth/login", json={
            "email": "hacker@evil.com",
            "password": "wrongpassword",
        })
        print(f"   POST /api/v1/auth/login (wrong creds) -> {r.status_code}")
        if "detail" in r.json():
            print(f"   Reason: {r.json()['detail']}")

        # 4. DASHBOARD
        print("\n** 4. Dashboard (static files)")
        r = c.get("/dashboard/")
        print(f"   GET /dashboard/ -> {r.status_code}")
        if r.status_code == 200:
            print(f"   Content-Length: {len(r.content)} bytes")
            snippet = r.text[:250].replace("\n", " ").strip()
            print(f"   Snippet: {snippet}...")

        # 5. STATIC ASSETS
        print("\n** 5. Static Assets")
        r = c.get("/dashboard/_next/static/chunks/main.js")
        print(f"   GET /dashboard/_next/static/chunks/main.js -> {r.status_code}")

        # 6. SECURITY HEADERS (X-Frame-Options, HSTS, etc.)
        print("\n** 6. Security Headers")
        r = c.get("/health")
        for h in ["x-content-type-options", "x-frame-options",
                  "strict-transport-security", "x-xss-protection"]:
            val = r.headers.get(h, "(missing)")
            print(f"   {h}: {val}")

        # 7. CORS - localhost:3000 allowed
        print("\n** 7. CORS")
        r = c.options("/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        print(f"   OPTIONS with Origin=http://localhost:3000 -> {r.status_code}")
        print(f"   Access-Control-Allow-Origin: {r.headers.get('access-control-allow-origin', 'N/A')}")

        # 8. CORS - evil.com rejected
        r2 = c.options("/health", headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        })
        acao2 = r2.headers.get('access-control-allow-origin', '(not set)')
        print(f"   OPTIONS with Origin=http://evil.com -> CORS origin: {acao2}")

        print(f"\n{box}")
        print("  DEMO COMPLETE")
        print(box)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
