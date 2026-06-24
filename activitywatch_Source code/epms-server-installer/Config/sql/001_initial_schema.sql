-- =============================================================
-- EPMS Enterprise Server — Initial Database Schema
-- Version: 1.0.0
-- Target: PostgreSQL 16
-- =============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- =============================================================
-- ORGANIZATIONS
-- =============================================================
CREATE TABLE IF NOT EXISTS organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL UNIQUE,
    display_name    VARCHAR(500),
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    max_agents      INTEGER NOT NULL DEFAULT 100,
    max_users       INTEGER NOT NULL DEFAULT 10,
    settings        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- USERS
-- =============================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(320) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255) NOT NULL DEFAULT '',
    role            VARCHAR(50) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('super_admin', 'admin', 'manager', 'viewer', 'user')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    mfa_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret      VARCHAR(255),
    avatar_url      VARCHAR(1024),
    last_login      TIMESTAMPTZ,
    last_ip         VARCHAR(45),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, email)
);

-- =============================================================
-- USER SESSIONS
-- =============================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token   VARCHAR(512) NOT NULL UNIQUE,
    access_token_jti VARCHAR(255),
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    expires_at      TIMESTAMPTZ NOT NULL,
    is_revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- AGENTS (Client Devices)
-- =============================================================
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id        VARCHAR(255) NOT NULL UNIQUE,
    display_name    VARCHAR(255) NOT NULL DEFAULT '',
    hostname        VARCHAR(255) NOT NULL DEFAULT '',
    os              VARCHAR(100) NOT NULL DEFAULT 'Windows',
    os_version      VARCHAR(100),
    version         VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    api_key_hash    VARCHAR(255),
    public_ip       VARCHAR(45),
    is_online       BOOLEAN NOT NULL DEFAULT FALSE,
    is_enrolled     BOOLEAN NOT NULL DEFAULT FALSE,
    enrolled_at     TIMESTAMPTZ,
    last_heartbeat  TIMESTAMPTZ,
    last_seen_ip    VARCHAR(45),
    metadata        JSONB DEFAULT '{}'::jsonb,
    labels          JSONB DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- AGENT HEARTBEATS
-- =============================================================
CREATE TABLE IF NOT EXISTS agent_heartbeats (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    afk_seconds     DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_afk          BOOLEAN NOT NULL DEFAULT FALSE,
    active_window_title    VARCHAR(1024),
    active_window_process  VARCHAR(255),
    cpu_percent     DOUBLE PRECISION,
    memory_percent  DOUBLE PRECISION,
    memory_available_gb DOUBLE PRECISION,
    uptime_seconds  BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- ACTIVITY EVENTS (Window, Application, Focus)
-- =============================================================
CREATE TABLE IF NOT EXISTS activity_events (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    event_type      VARCHAR(50) NOT NULL DEFAULT 'window'
                    CHECK (event_type IN ('window', 'browser', 'editor', 'app', 'focus', 'idle')),
    app_name        VARCHAR(255),
    window_title    TEXT,
    url             TEXT,
    domain          VARCHAR(1024),
    browser_name    VARCHAR(100),
    editor_name     VARCHAR(100),
    project_name    VARCHAR(500),
    file_name       VARCHAR(1024),
    category        VARCHAR(100),
    is_productivity BOOLEAN,
    data            JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- BROWSER ACTIVITY
-- =============================================================
CREATE TABLE IF NOT EXISTS browser_activity (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    browser_name    VARCHAR(100) NOT NULL,
    browser_version VARCHAR(50),
    url             TEXT,
    domain          VARCHAR(1024),
    page_title      TEXT,
    is_productive   BOOLEAN DEFAULT TRUE,
    tab_id          VARCHAR(255),
    tab_index       INTEGER,
    window_id       VARCHAR(255),
    session_id      VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    category        VARCHAR(100),
    data            JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- EDITOR ACTIVITY
-- =============================================================
CREATE TABLE IF NOT EXISTS editor_activity (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    editor_name     VARCHAR(100) NOT NULL,
    editor_version  VARCHAR(50),
    project_name    VARCHAR(500),
    project_path    TEXT,
    file_name       VARCHAR(1024),
    file_path       TEXT,
    file_extension  VARCHAR(50),
    language        VARCHAR(100),
    line_count      INTEGER,
    is_focused      BOOLEAN NOT NULL DEFAULT TRUE,
    is_debugging    BOOLEAN NOT NULL DEFAULT FALSE,
    data            JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- SYSTEM METRICS
-- =============================================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    cpu_percent     DOUBLE PRECISION,
    cpu_frequency_mhz DOUBLE PRECISION,
    memory_total_gb DOUBLE PRECISION,
    memory_used_gb  DOUBLE PRECISION,
    memory_percent  DOUBLE PRECISION,
    disk_total_gb   DOUBLE PRECISION,
    disk_used_gb    DOUBLE PRECISION,
    disk_percent    DOUBLE PRECISION,
    network_bytes_sent_mb   DOUBLE PRECISION,
    network_bytes_recv_mb   DOUBLE PRECISION,
    uptime_seconds  BIGINT,
    processes_count INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- PRODUCTIVITY SCORES
-- =============================================================
CREATE TABLE IF NOT EXISTS productivity_scores (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    score           DOUBLE PRECISION NOT NULL DEFAULT 0,
    productive_time_seconds    BIGINT NOT NULL DEFAULT 0,
    neutral_time_seconds       BIGINT NOT NULL DEFAULT 0,
    distracting_time_seconds   BIGINT NOT NULL DEFAULT 0,
    idle_time_seconds          BIGINT NOT NULL DEFAULT 0,
    total_time_seconds         BIGINT NOT NULL DEFAULT 0,
    hb_count        INTEGER NOT NULL DEFAULT 0,
    browser_productive_seconds BIGINT NOT NULL DEFAULT 0,
    browser_distracting_seconds BIGINT NOT NULL DEFAULT 0,
    editor_time_seconds        BIGINT NOT NULL DEFAULT 0,
    category_breakdown         JSONB DEFAULT '{}'::jsonb,
    app_breakdown              JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_id, date)
);

-- =============================================================
-- PRODUCTIVITY CATEGORIES
-- =============================================================
CREATE TABLE IF NOT EXISTS productivity_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    color           VARCHAR(7) DEFAULT '#6366f1',
    icon            VARCHAR(50),
    weight          DOUBLE PRECISION NOT NULL DEFAULT 1.0
                    CHECK (weight >= -1.0 AND weight <= 1.0),
    is_productive   BOOLEAN NOT NULL DEFAULT TRUE,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,
    rules           JSONB DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

-- =============================================================
-- DOMAIN CATEGORIES (for website classification)
-- =============================================================
CREATE TABLE IF NOT EXISTS domain_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain          VARCHAR(1024) NOT NULL UNIQUE,
    category        VARCHAR(100) NOT NULL,
    sub_category    VARCHAR(100),
    is_productive   BOOLEAN NOT NULL DEFAULT TRUE,
    is_blocked      BOOLEAN NOT NULL DEFAULT FALSE,
    source          VARCHAR(50) DEFAULT 'auto',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- REPORTS
-- =============================================================
CREATE TABLE IF NOT EXISTS reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by      UUID NOT NULL REFERENCES users(id),
    title           VARCHAR(500) NOT NULL,
    report_type     VARCHAR(50) NOT NULL
                    CHECK (report_type IN ('daily', 'weekly', 'monthly', 'custom', 'export')),
    format          VARCHAR(20) NOT NULL DEFAULT 'pdf'
                    CHECK (format IN ('pdf', 'csv', 'xlsx', 'html', 'json')),
    date_from       DATE NOT NULL,
    date_to         DATE NOT NULL,
    filters         JSONB DEFAULT '{}'::jsonb,
    data            JSONB,
    file_path       TEXT,
    file_size_bytes BIGINT,
    is_generated    BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- ALERTS & NOTIFICATIONS
-- =============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    alert_type      VARCHAR(50) NOT NULL
                    CHECK (alert_type IN ('agent_offline', 'high_idle', 'low_productivity',
                           'threshold_breach', 'system_health', 'security', 'info')),
    severity        VARCHAR(20) NOT NULL DEFAULT 'info'
                    CHECK (severity IN ('critical', 'warning', 'info')),
    title           VARCHAR(500) NOT NULL,
    message         TEXT,
    agent_id        VARCHAR(255),
    acknowledged    BOOLEAN NOT NULL DEFAULT FALSE,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    is_resolved     BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    resolved_by     UUID REFERENCES users(id),
    data            JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- NOTIFICATIONS
-- =============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(500) NOT NULL,
    body            TEXT,
    notification_type VARCHAR(50) NOT NULL DEFAULT 'info',
    channel         VARCHAR(50) NOT NULL DEFAULT 'in_app'
                    CHECK (channel IN ('in_app', 'email', 'push', 'webhook')),
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    is_sent         BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at         TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    data            JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- APP SESSIONS (Aggregated from process_events)
-- =============================================================
CREATE TABLE IF NOT EXISTS app_sessions (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    app_name        VARCHAR(512) NOT NULL,
    process_name    VARCHAR(512) NOT NULL DEFAULT '',
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    duration_seconds INTEGER DEFAULT 0,
    category        VARCHAR(64) DEFAULT 'uncategorized',
    is_productive   BOOLEAN DEFAULT NULL,
    window_title    TEXT DEFAULT '',
    is_foreground   BOOLEAN DEFAULT TRUE
);

-- =============================================================
-- POLICIES (Agent configuration pushed from server)
-- =============================================================
CREATE TABLE IF NOT EXISTS policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    policy_type     VARCHAR(50) NOT NULL DEFAULT 'monitoring'
                    CHECK (policy_type IN ('monitoring', 'browser', 'editor', 'privacy',
                           'schedule', 'network', 'compliance')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    priority        INTEGER NOT NULL DEFAULT 0,
    rules           JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_agents   JSONB DEFAULT '{}'::jsonb,
    version         INTEGER NOT NULL DEFAULT 1,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- AUDIT LOG
-- =============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    agent_id        VARCHAR(255),
    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(100),
    entity_id       VARCHAR(255),
    details         JSONB DEFAULT '{}'::jsonb,
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- CONFIGURATION (Key-Value store for org settings)
-- =============================================================
CREATE TABLE IF NOT EXISTS configuration (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    scope           VARCHAR(50) NOT NULL DEFAULT 'organization'
                    CHECK (scope IN ('organization', 'user', 'agent', 'global')),
    scope_id        UUID,
    key             VARCHAR(255) NOT NULL,
    value           JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_encrypted    BOOLEAN NOT NULL DEFAULT FALSE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, scope, key)
);

-- =============================================================
-- SCHEMA MIGRATIONS TRACKING
-- =============================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    id              SERIAL PRIMARY KEY,
    version         VARCHAR(50) NOT NULL UNIQUE,
    file_name       VARCHAR(255) NOT NULL,
    checksum        VARCHAR(64),
    executed_by     VARCHAR(255),
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms     INTEGER
);

-- Record this migration
INSERT INTO schema_migrations (version, file_name, executed_by)
VALUES ('001', '001_initial_schema.sql', 'installer');
