-- =============================================================
-- EPMS Enterprise Server — Process Events Schema
-- Version: 1.0.0
-- =============================================================
-- Adds process-level monitoring tables and aggregation pipeline.
-- Tracks ALL running processes (not just foreground window),
-- then aggregates into app sessions for dashboard queries.

-- =============================================================
-- PROCESS_EVENTS: Raw per-process snapshot every heartbeat
-- =============================================================
-- High-volume table; partition by month in production.
-- Short retention (7 days default), purged by epms_purge_old_data.

CREATE TABLE IF NOT EXISTS process_events (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(255) NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    process_name    VARCHAR(512) NOT NULL,
    process_path    TEXT DEFAULT '',
    pid             INTEGER NOT NULL,
    parent_pid      INTEGER DEFAULT 0,
    cpu_percent     REAL DEFAULT 0,
    memory_percent  REAL DEFAULT 0,
    is_foreground   BOOLEAN DEFAULT FALSE,
    window_title    TEXT DEFAULT '',
    username        VARCHAR(255) DEFAULT '',
    cmd_line        TEXT DEFAULT '',
    session_id      INTEGER DEFAULT 0
);

-- Indexes for process_events: query, purge, aggregation
CREATE INDEX IF NOT EXISTS idx_process_events_agent_id ON process_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_process_events_timestamp ON process_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_process_events_agent_time ON process_events(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_process_events_name ON process_events(process_name);
CREATE INDEX IF NOT EXISTS idx_process_events_foreground ON process_events(agent_id, timestamp DESC)
    WHERE is_foreground = TRUE;

-- =============================================================
-- APP_SESSIONS: Aggregated application usage sessions
-- =============================================================
-- Built by background worker every 5 minutes from process_events.
-- Longer retention (90 days) for dashboard timeline queries.
-- Each row = continuous usage of one app by one user.

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

CREATE INDEX IF NOT EXISTS idx_app_sessions_org ON app_sessions(organization_id);
CREATE INDEX IF NOT EXISTS idx_app_sessions_agent ON app_sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_app_sessions_started ON app_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_sessions_agent_started ON app_sessions(agent_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_sessions_app ON app_sessions(app_name);
CREATE INDEX IF NOT EXISTS idx_app_sessions_category ON app_sessions(category);
CREATE INDEX IF NOT EXISTS idx_app_sessions_org_date ON app_sessions(organization_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_sessions_active ON app_sessions(ended_at)
    WHERE ended_at IS NULL;

-- =============================================================
-- Retention policy for process_events (shorter than app_sessions)
-- =============================================================
CREATE OR REPLACE FUNCTION epms_purge_process_events(
    retention_days INTEGER DEFAULT 7,
    batch_size INTEGER DEFAULT 5000
) RETURNS TABLE(deleted_count BIGINT) AS $$
DECLARE
    v_deleted BIGINT := 0;
    v_batch BIGINT := 1;
BEGIN
    LOOP
        WITH batch AS (
            DELETE FROM process_events
            WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL
            AND ctid IN (
                SELECT ctid FROM process_events
                WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL
                LIMIT batch_size
            )
            RETURNING 1 AS deleted
        )
        SELECT COUNT(*) INTO v_batch FROM batch;
        v_deleted := v_deleted + v_batch;
        EXIT WHEN v_batch = 0;
    END LOOP;
    RETURN QUERY SELECT v_deleted AS deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================
-- App session aggregation function (called by background worker)
-- =============================================================
CREATE OR REPLACE FUNCTION epms_aggregate_app_sessions(
    since_minutes INTEGER DEFAULT 5
) RETURNS TABLE(sessions_created INTEGER) AS $$
DECLARE
    v_cutoff TIMESTAMPTZ;
    v_created INTEGER := 0;
    v_rec RECORD;
BEGIN
    v_cutoff := NOW() - (since_minutes || ' minutes')::INTERVAL;

    -- For each agent+process combination with foreground activity,
    -- create or extend an app session
    FOR v_rec IN (
        SELECT DISTINCT pe.agent_id, pe.process_name, pe.window_title,
               a.organization_id
        FROM process_events pe
        JOIN agents a ON pe.agent_id = a.agent_id
        WHERE pe.timestamp >= v_cutoff
          AND pe.is_foreground = TRUE
          AND a.organization_id IS NOT NULL
    ) LOOP
        -- Check if there's an open session for this agent+process
        PERFORM 1 FROM app_sessions
        WHERE agent_id = v_rec.agent_id
          AND process_name = v_rec.process_name
          AND ended_at IS NULL;

        IF NOT FOUND THEN
            -- Create new session
            INSERT INTO app_sessions
                (agent_id, organization_id, app_name, process_name,
                 started_at, window_title)
            VALUES
                (v_rec.agent_id, v_rec.organization_id,
                 v_rec.process_name, v_rec.process_name,
                 v_cutoff, v_rec.window_title);
            v_created := v_created + 1;
        END IF;
    END LOOP;

    -- Close sessions for processes that stopped appearing
    UPDATE app_sessions s
    SET ended_at = v_cutoff,
        duration_seconds = EXTRACT(EPOCH FROM (v_cutoff - started_at))::INTEGER
    WHERE s.ended_at IS NULL
      AND NOT EXISTS (
        SELECT 1 FROM process_events pe
        WHERE pe.agent_id = s.agent_id
          AND pe.process_name = s.process_name
          AND pe.timestamp >= v_cutoff
          AND pe.is_foreground = TRUE
    );

    RETURN QUERY SELECT v_created AS sessions_created;
END;
$$ LANGUAGE plpgsql;

-- Record this migration
INSERT INTO schema_migrations (version, file_name, executed_by)
VALUES ('003', '003_process_events.sql', 'installer')
ON CONFLICT (version) DO NOTHING;
