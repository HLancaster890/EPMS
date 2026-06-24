"""Seed realistic test data into EPMS for sandbox testing."""
import asyncio, uuid, random, json, os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DB_CONFIG = dict(
    host=os.environ.get("EPMS_DB_HOST", "localhost"),
    port=int(os.environ.get("EPMS_DB_PORT", "5432")),
    user=os.environ.get("EPMS_DB_USER", "postgres"),
    database=os.environ.get("EPMS_DB_NAME", "epms"),
    password=os.environ.get("EPMS_DB_PASSWORD", ""),
)

APPS = {
    "productive": [
        ("Code.exe", "VS Code"), ("msedge.exe", "Edge"),
        ("OUTLOOK.EXE", "Outlook"), ("WINWORD.EXE", "Word"),
        ("EXCEL.EXE", "Excel"), ("chrome.exe", "Chrome"),
    ],
    "neutral": [
        ("explorer.exe", "File Explorer"), ("Taskmgr.exe", "Task Manager"),
        ("Teams.exe", "Microsoft Teams"), ("Slack.exe", "Slack"),
    ],
    "distracting": [
        ("Spotify.exe", "Spotify"), ("youtube.exe", "YouTube"),
        ("reddit.exe", "Reddit"), ("twitter.exe", "Twitter"),
    ],
}

BROWSER_DOMAINS = {
    "productive": ["github.com", "stackoverflow.com", "docs.python.org",
                    "gitlab.com", "atlassian.net", "notion.so"],
    "neutral": ["outlook.com", "teams.microsoft.com", "calendar.google.com"],
    "distracting": ["youtube.com", "reddit.com", "twitter.com", "instagram.com",
                     "netflix.com", "twitch.tv"],
}

async def seed():
    import asyncpg
    conn = await asyncpg.connect(**DB_CONFIG)

    now = datetime.now(timezone.utc)
    agent_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    org_id = "00000000-0000-0000-0000-000000000000"
    user_id = "00000000-0000-0000-0000-000000000001"

    await conn.execute("DELETE FROM agent_heartbeats WHERE agent_id != 'seed'")
    await conn.execute("DELETE FROM process_events WHERE agent_id = $1", agent_id)
    await conn.execute("DELETE FROM browser_activity WHERE agent_id = $1", agent_id)
    await conn.execute("DELETE FROM editor_activity WHERE agent_id = $1", agent_id)
    await conn.execute("DELETE FROM activity_events WHERE agent_id = $1::uuid", agent_id)
    await conn.execute("DELETE FROM productivity_scores WHERE agent_id = $1", agent_id)
    await conn.execute("DELETE FROM app_sessions WHERE agent_id = $1", agent_id)

    print(f"Seeding data for agent {agent_id}...")

    for hour_offset in range(72, 0, -1):
        ts = now - timedelta(hours=hour_offset)
        afk = random.random() < 0.15

        foreground_app = random.choice(
            APPS["productive"] + APPS["neutral"] + APPS["distracting"]
        )
        fg_proc, fg_title = foreground_app
        window_title = f"{fg_title} - Work" if random.random() > 0.3 else fg_title

        await conn.execute("""
            INSERT INTO agent_heartbeats
            (agent_id, timestamp, afk_seconds, is_afk,
             active_window_title, active_window_process,
             cpu_percent, memory_percent, memory_available_gb, uptime_seconds)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """, agent_id, ts, round(random.uniform(0, 600), 1), afk,
            window_title, fg_proc,
            round(random.uniform(5, 95), 1), round(random.uniform(30, 85), 1),
            round(random.uniform(2, 12), 2), random.randint(3600, 86400))

        for _ in range(random.randint(3, 10)):
            cat = random.choices(
                ["productive", "neutral", "distracting"],
                weights=[0.5, 0.3, 0.2]
            )[0]
            proc_name, proc_title = random.choice(APPS[cat])
            is_fg = proc_name == fg_proc
            await conn.execute("""
                INSERT INTO process_events
                (agent_id, timestamp, process_name, process_path,
                 pid, parent_pid, cpu_percent, memory_percent,
                 is_foreground, window_title, username, cmd_line)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """, agent_id, ts, proc_name, f"C:\\Program Files\\{proc_name}",
                random.randint(1000, 99999), random.randint(1, 9999),
                round(random.uniform(0, 50), 1), round(random.uniform(0, 30), 1),
                is_fg, window_title if is_fg else "",
                "CORP\\jdoe",
                f'"{proc_name}" --some-flag' if random.random() > 0.5 else f'"{proc_name}"')

    # Browser activity
    for hour_offset in range(48, 0, -1):
        ts = now - timedelta(hours=hour_offset)
        if random.random() > 0.3:
            cat = random.choices(
                ["productive", "neutral", "distracting"],
                weights=[0.4, 0.3, 0.3]
            )[0]
            domain = random.choice(BROWSER_DOMAINS[cat])
            url = f"https://{domain}/page-{random.randint(1, 100)}"
            await conn.execute("""
                INSERT INTO browser_activity
                (agent_id, timestamp, browser_name, domain, url, page_title,
                 category, is_productive, is_active)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,true)
            """, agent_id, ts,
                random.choice(["chrome.exe", "msedge.exe", "firefox.exe"]),
                domain, url,
                f"{domain.split('.')[0].title()} Page",
                cat, cat == "productive")

    # Editor activity
    for hour_offset in range(48, 0, -1):
        ts = now - timedelta(hours=hour_offset)
        if random.random() > 0.6:
            await conn.execute("""
                INSERT INTO editor_activity
                (agent_id, timestamp, editor_name, project_name,
                 file_name, language)
                VALUES ($1,$2,$3,$4,$5,$6)
            """, agent_id, ts,
                random.choice(["Code.exe", "WebStorm.exe", "vim.exe"]),
                random.choice(["epms-server", "dashboard", "api-client"]),
                random.choice(["main.py", "app.tsx", "index.html", "test.js"]),
                random.choice(["python", "typescript", "javascript", "go"]))

    # Productivity scores
    for day_offset in range(14, -1, -1):
        day = (now - timedelta(days=day_offset)).date()
        score = random.randint(30, 95)
        await conn.execute("""
            INSERT INTO productivity_scores
            (agent_id, organization_id, date, score,
             productive_time_seconds, neutral_time_seconds,
             distracting_time_seconds, idle_time_seconds, hb_count)
            VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (agent_id, date) DO UPDATE SET score=$4
        """, agent_id, org_id, day, score,
            random.randint(10000, 30000), random.randint(5000, 15000),
            random.randint(1000, 8000), random.randint(2000, 10000),
            random.randint(50, 200))

    # App sessions
    for hour_offset in range(24, 0, -1):
        start = now - timedelta(hours=hour_offset)
        dur = random.randint(300, 3600)
        end = start + timedelta(seconds=dur)
        cat = random.choices(
            ["productive", "neutral", "distracting"],
            weights=[0.5, 0.3, 0.2]
        )[0]
        app = random.choice(APPS[cat])
        await conn.execute("""
            INSERT INTO app_sessions
            (agent_id, organization_id, app_name, process_name,
             started_at, ended_at, duration_seconds, category,
             is_productive, is_foreground)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,true)
        """, agent_id, org_id, app[0], app[0],
            start, end, dur, cat, cat == "productive")

    # Activity events
    for hour_offset in range(24, 0, -1):
        ts = now - timedelta(hours=hour_offset)
        if random.random() > 0.2:
            app = random.choice(
                APPS["productive"] + APPS["neutral"] + APPS["distracting"]
            )
            await conn.execute("""
                INSERT INTO activity_events
                (agent_id, timestamp, duration_seconds, event_type,
                 app_name, window_title, category, is_productivity)
                VALUES ($1::uuid,$2,$3,$4,$5,$6,$7,$8)
            """, agent_id,
                ts, random.randint(60, 1800),
                random.choice(["window", "app", "focus"]),
                app[0], f"{app[1]} - Active", "neutral", None)

    # Alerts
    for day_offset in range(7, -1, -1):
        ts = now - timedelta(days=day_offset)
        await conn.execute("""
            INSERT INTO alerts
            (organization_id, alert_type, severity, title, message,
             created_at)
            VALUES ($1::uuid, $2, $3, $4, $5, $6)
        """, org_id,
            random.choice(["system_health", "info", "low_productivity"]),
            random.choice(["info", "warning", "critical"]),
            f"Alert #{day_offset + 1}",
            f"This is a test alert number {day_offset + 1}",
            ts)

    await conn.close()
    print("Seed complete! 72h of data populated.")

if __name__ == "__main__":
    import os
    import asyncpg
    asyncio.run(seed())
