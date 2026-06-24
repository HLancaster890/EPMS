"""Simulate agent heartbeats to the running EPMS server."""
import httpx, json, uuid, random, time
from datetime import datetime, timezone

SERVER = "http://localhost:8000"
AGENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
API_KEY = None

APPS = {
    "productive": ["Code.exe", "msedge.exe", "OUTLOOK.EXE", "WINWORD.EXE", "EXCEL.EXE"],
    "neutral": ["explorer.exe", "Taskmgr.exe", "Teams.exe", "Slack.exe", "chrome.exe"],
    "distracting": ["Spotify.exe", "youtube.exe", "reddit.exe"],
}

BROWSER_URLS = [
    ("github.com", "https://github.com/org/repo/pull/123"),
    ("stackoverflow.com", "https://stackoverflow.com/questions/123"),
    ("docs.python.org", "https://docs.python.org/3/library/"),
    ("youtube.com", "https://youtube.com/watch?v=dQw4w9WgXcQ"),
    ("outlook.com", "https://outlook.office.com/mail/"),
    ("reddit.com", "https://reddit.com/r/programming/"),
]

async def login():
    global API_KEY
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{SERVER}/api/v1/auth/login", json={
            "email": "admin@corp.local", "password": "MyP@ss1"
        })
        if r.status_code == 200:
            data = r.json()
            API_KEY = data["access_token"]
            print(f"Logged in. Token: {API_KEY[:40]}...")
            return True
        print(f"Login failed: {r.status_code} {r.text}")
        return False

async def send_heartbeat():
    if not API_KEY:
        return False
    fg_cat = random.choices(
        ["productive", "neutral", "distracting"],
        weights=[0.5, 0.3, 0.2]
    )[0]
    fg_process = random.choice(APPS[fg_cat])
    now = datetime.now(timezone.utc).isoformat()
    process_count = random.randint(5, 20)

    payload = {
        "timestamp": now,
        "foreground_window": {
            "title": f"{fg_process.replace('.exe', '')} - Work",
            "process": fg_process,
            "pid": random.randint(1000, 99999),
            "cpu": round(random.uniform(0.5, 30), 1),
            "memory_mb": random.randint(50, 2000),
        },
        "active_window": {
            "title": f"{fg_process.replace('.exe', '')} - Work",
            "process": fg_process,
        },
        "afk_seconds": 0.0 if random.random() > 0.1 else round(random.uniform(60, 600), 1),
        "is_afk": random.random() < 0.05,
        "system": {
            "cpu": {"percent": round(random.uniform(10, 90), 1)},
            "memory": {
                "percent": round(random.uniform(30, 85), 1),
                "available_gb": round(random.uniform(2, 12), 2),
            },
            "uptime_seconds": random.randint(3600, 86400),
        },
        "processes": [
            {
                "pid": random.randint(1000, 99999),
                "ppid": random.randint(1, 9999),
                "process_name": fg_process if i == 0 else random.choice(
                    APPS["productive"] + APPS["neutral"] + APPS["distracting"]
                ),
                "process_path": f"C:\\Program Files\\{fg_process if i == 0 else 'app.exe'}",
                "cpu_percent": round(random.uniform(0, 50), 1),
                "memory_percent": round(random.uniform(0, 20), 1),
                "is_foreground": i == 0,
                "window_title": f"Window {i}" if i > 0 else f"{fg_process.replace('.exe', '')} - Work",
                "username": "CORP\\jdoe",
                "cmd_line": f'"{fg_process}" --flag',
                "create_time": int(time.time()) - random.randint(100, 86400),
            }
            for i in range(process_count)
        ],
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SERVER}/api/v1/agent/heartbeat",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        if r.status_code == 200:
            print(f"HB OK: {now[:19]}, processes: {process_count}")
            return True
        print(f"HB FAIL: {r.status_code} {r.text[:200]}")
        return False

async def send_browser_activity():
    cat = random.choices(["productive", "neutral", "distracting"], weights=[0.4, 0.3, 0.3])[0]
    domain, url = random.choice(BROWSER_URLS)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "browser_name": random.choice(["chrome.exe", "msedge.exe", "firefox.exe"]),
        "domain": domain,
        "url": url,
        "page_title": f"{domain.split('.')[0].title()} - {cat}",
        "category": cat,
        "is_productive": cat == "productive",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SERVER}/api/v1/agent/browser",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        if r.status_code == 200:
            print(f"  Browser: {domain} ({cat})")
        else:
            print(f"  Browser FAIL: {r.status_code}")

async def run_simulation(cycles=12, interval=5):
    if not await login():
        return
    print(f"\nStarting heartbeat simulation: {cycles} cycles, {interval}s apart\n")
    for i in range(cycles):
        await send_heartbeat()
        if random.random() > 0.6:
            await send_browser_activity()
        if i < cycles - 1:
            await asyncio.sleep(interval)
    print(f"\nSimulation complete. {cycles} heartbeats sent.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_simulation())
