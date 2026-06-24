# EPMS Enterprise — Technology Stack Evaluation

## 1. Current Stack

| Layer | Technology | Status |
|-------|-----------|--------|
| **Agent language** | Python 3.10+ | ✅ Bundled via PyInstaller |
| **Server language** | Python 3.10+ | ✅ 6 FastAPI/uvicorn services |
| **Web framework** | FastAPI | ✅ Mature, async-native |
| **DB** | PostgreSQL 16 | ✅ Best choice for transactional + analytical |
| **Cache** | Redis | ✅ Rate limiting, session cache |
| **Message bus** | NATS | ✅ Lightweight, persistent, JetStream |
| **Web UI** | Vanilla HTML/CSS/JS | ⚠️ Upgrade candidate |
| **Deployment** | PyInstaller .exe + WiX MSI | ✅ Windows-native |
| **Auth** | JWT + API Key | ⚠️ Fixes needed (see review) |

## 2. Stack Evaluation

### Backend: Python/FastAPI — KEEP

| For | Against |
|-----|---------|
| Team is Python-skilled | GIL limits CPU-bound processing |
| asyncpg is best-in-class async PG driver | PyInstaller frozen exe has quirks |
| Rich ecosystem (passlib, aioredis, nats-py) | Cannot use multiprocessing/workers>1 |
| FastAPI + Pydantic = strong input validation | |
| NATS client library is Pythonic | |

**Verdict**: Keep. The productivity logic is I/O-bound (DB reads + formulas). Python async is appropriate. If agent-count exceeds 5,000 per server, consider rewriting the analytics service in Go for the scoring hot path.

### Message Bus: NATS — KEEP

| For | Against |
|-----|---------|
| 10x lighter than Kafka (~10MB binary) | Smaller community |
| JetStream provides persistence + replay | No built-in DLQ consumer UI |
| Pub/sub matches event pipeline perfectly | |
| Windows-native server binary available | |

### Database: PostgreSQL — KEEP

Current schema has 21 tables. The relational model fits time-series + dimensional data well.

**Suggested additions**: TimescaleDB extension for automatic partitioning on `timestamp` column in event tables. This would be transparent to application code (same SQL syntax, same asyncpg driver).

### Web UI: Vanilla → Upgrade Recommended

Current dashboard is a single `index.html` with inline JS (Chart.js + fetch). This works but:

- No build step, no TypeScript, no component isolation
- JS grows linearly with feature count
- No server-side rendering for SEO (irrelevant for dashboard)

**Recommendation**: Two options:

| Option | Stack | Effort | Benefit |
|--------|-------|--------|---------|
| A. Keep vanilla, add Webpack | Current + build step | 2 days | TypeScript, bundling, minification |
| B. React SPA | Vite + React + React Router + Chart.js | 2 weeks | Component reusability, state management, ecosystem |

**Verdict**: Option A for MVP. If the dashboard grows beyond 5 pages, migrate to Option B.

### Deployment: PyInstaller + WiX — KEEP

The on-prem Windows requirement forces this choice. The issues are in *how* the spec files and WiX sources are configured, not the technology itself.

### Infrastructure: Redis — KEEP

Redis is used for rate limiting and session cache. Both are appropriate use cases. No alternative needed.

## 3. Alternative Evaluations

### Agent Language: Python vs Go vs Rust

| Dimension | Python (current) | Go | Rust |
|-----------|-----------------|----|------|
| Window API access | ✅ win32api via pywin32 | ⚠️ syscall/ffi | ⚠️ unsafe/ffi |
| PyInstaller/ASAR bundle | ✅ Mature | ⚠️ Go binary is standalone | ✅ Single binary |
| Dev speed | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Memory usage | ~80MB | ~15MB | ~10MB |
| Talent pool | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| CPU profiling / AFK detection libs | ✅ psutil | ✅ gopsutil | ⚠️ sysinfo |

**Verdict**: Keep Python for the agent. Rewriting in Go or Rust would add months with no measurable benefit for window-title parsing (the core agent function). The agent is I/O-bound on user-idle timers, not CPU-bound.

### DB Migration: TimescaleDB or pg_partman

| Feature | Vanilla PG | TimescaleDB | pg_partman |
|---------|-----------|-------------|------------|
| Auto partitioning | ❌ Manual | ✅ Hypertables | ✅ Declarative |
| Data retention policy | ❌ Custom function | ✅ `add_retention_policy()` | ✅ Custom |
| Compression | ❌ | ✅ Native columns | ❌ |
| Complexity | None | Low (extension) | Low (extension) |

**Verdict**: Add TimescaleDB extension for `activity_events`, `agent_heartbeats`, `browser_activity`, `editor_activity`, `system_metrics` hypertables. The `add_retention_policy()` alone eliminates the need for a custom purge function.

## 4. Comparison Matrix

| Capability | Current Stack | Option A (Keep + Harden) | Option B (Full Upgrade) |
|-----------|--------------|--------------------------|------------------------|
| Backend | FastAPI/Python | FastAPI/Python | FastAPI + Go scoring engine |
| Frontend | Vanilla JS | Vanilla + Webpack | React SPA |
| DB | PostgreSQL | PostgreSQL + indexes | + TimescaleDB extension |
| Cache | Redis | Redis | Redis |
| Bus | NATS | NATS | NATS + JetStream |
| Deploy | PyInstaller + WiX | Same + fixes | Same + authenticode |
| Security | ⚠️ 15 critical/high issues found | ✅ All fixed | ✅ All fixed |
| Dev cost | 6 weeks (current) | +5 weeks hardening | +3 months |
| OpEx/month (on-prem) | ~$200 (server + power) | ~$200 | ~$250 (more RAM) |
| Max agents/server | ~2,000 (estimated) | ~5,000 (with indexes) | ~10,000 (TimescaleDB) |

## 5. Recommendation

**Stay on current stack. Harden, don't rewrite.**

1. Fix the 15 critical security issues (Week 1-2)
2. Add missing DB indexes and retention (Week 3)
3. Fix WiX/PyInstaller pipeline (Week 4)
4. Re-evaluate frontend upgrade only when dashboard complexity justifies it
