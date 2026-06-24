-- =============================================================
-- EPMS Enterprise Server — Migration 002
-- Performance indexes + data retention purge function
-- Version: 1.0.0
-- Target: PostgreSQL 16
-- =============================================================

-- =============================================================
-- 1. PERFORMANCE INDEXES
-- =============================================================
-- Each index is created CONCURRENTLY to avoid blocking writes.
-- Note: CONCURRENTLY cannot run inside a transaction block.

-- Agents: org_id lookups (used by all dashboard endpoints)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agents_org_id
    ON agents (organization_id);

-- Users: org_id lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_org_id
    ON users (organization_id);

-- Heartbeats: agent + timestamp for activity queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_heartbeats_agent_ts
    ON agent_heartbeats (agent_id, timestamp DESC);

-- Heartbeats: date-range filtering (active today, etc.)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_heartbeats_ts
    ON agent_heartbeats (timestamp DESC);

-- Activity events: agent + timestamp
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_events_agent_ts
    ON activity_events (agent_id, timestamp DESC);

-- Activity events: org lookup via agents join
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_events_ts
    ON activity_events (timestamp DESC);

-- Browser activity: agent + timestamp + org filtering via join
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_browser_activity_agent_ts
    ON browser_activity (agent_id, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_browser_activity_ts
    ON browser_activity (timestamp DESC);

-- Editor activity: agent + timestamp
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_editor_activity_agent_ts
    ON editor_activity (agent_id, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_editor_activity_ts
    ON editor_activity (timestamp DESC);

-- System metrics: agent + timestamp (purge old data)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_metrics_agent_ts
    ON system_metrics (agent_id, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_metrics_ts
    ON system_metrics (timestamp DESC);

-- Productivity scores: org + date (dashboard org-filtered queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_productivity_scores_org_date
    ON productivity_scores (organization_id, date DESC);

-- Productivity scores: agent + date (per-agent queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_productivity_scores_agent_date
    ON productivity_scores (agent_id, date DESC);

-- Alerts: org + created_at (dashboard queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_org_created
    ON alerts (organization_id, created_at DESC);

-- Reports: org + created_at
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_org_created
    ON reports (organization_id, created_at DESC);

-- Audit log: org + timestamp (compliance queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_org_ts
    ON audit_log (organization_id, created_at DESC);

-- Notifications: user + read status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_user_read
    ON notifications (user_id, is_read, created_at DESC);

-- User sessions: user + revoked + expires
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_user_revoked
    ON user_sessions (user_id, is_revoked, expires_at DESC);


-- =============================================================
-- 2. DATA RETENTION PURGE FUNCTION
-- =============================================================
-- Deletes data older than the specified retention period.
-- Default retention: 90 days.
-- Configurable per table, with staggered execution to avoid
-- transaction ID wraparound and massive DELETE bloat.
-- Deletes in batches of 5000 rows to keep locks short.

CREATE OR REPLACE FUNCTION epms_purge_old_data(
    p_retention_days INTEGER DEFAULT 90,
    p_dry_run BOOLEAN DEFAULT FALSE,
    p_batch_size INTEGER DEFAULT 5000
) RETURNS TABLE(
    table_name TEXT,
    rows_deleted BIGINT,
    duration_ms BIGINT
) LANGUAGE plpgsql AS $$
DECLARE
    v_cutoff TIMESTAMPTZ;
    v_start TIMESTAMPTZ;
    v_rows BIGINT;
    v_total_rows BIGINT;
    v_table TEXT;
    v_where TEXT;
    v_sql TEXT;
    v_tables TEXT[] := ARRAY[
        'agent_heartbeats',
        'activity_events',
        'browser_activity',
        'editor_activity',
        'system_metrics'
    ];
BEGIN
    -- Tables with retention but no org_id:
    --   agent_heartbeats, activity_events, browser_activity,
    --   editor_activity, system_metrics (high-volume, time-series)
    v_cutoff := NOW() - (p_retention_days || ' days')::INTERVAL;

    FOREACH v_table IN ARRAY v_tables
    LOOP
        v_start := clock_timestamp();
        v_total_rows := 0;
        v_where := format('WHERE timestamp < $1');

        -- Count rows to be purged
        EXECUTE format('SELECT COUNT(*) FROM %I %s', v_table, v_where)
            INTO v_rows
            USING v_cutoff;

        IF v_rows = 0 THEN
            table_name := v_table;
            rows_deleted := 0;
            duration_ms := 0;
            RETURN NEXT;
            CONTINUE;
        END IF;

        IF p_dry_run THEN
            table_name := v_table;
            rows_deleted := v_rows;
            duration_ms := 0;
            RETURN NEXT;
            CONTINUE;
        END IF;

        -- Batch delete to avoid long locks
        LOOP
            v_sql := format(
                'DELETE FROM %I WHERE ctid IN (
                    SELECT ctid FROM %I %s LIMIT $1
                )',
                v_table, v_table, v_where
            );
            EXECUTE v_sql USING p_batch_size, v_cutoff;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            v_total_rows := v_total_rows + v_rows;
            EXIT WHEN v_rows < p_batch_size;
        END LOOP;

        table_name := v_table;
        rows_deleted := v_total_rows;
        duration_ms := EXTRACT(EPOCH FROM (clock_timestamp() - v_start)) * 1000;
        RETURN NEXT;
    END LOOP;
END;
$$;

-- Also purge old user_sessions (expired + revoked, keep 7 days beyond expiry)
CREATE OR REPLACE FUNCTION epms_purge_old_sessions(
    p_extra_days INTEGER DEFAULT 7,
    p_dry_run BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    table_name TEXT,
    rows_deleted BIGINT
) LANGUAGE plpgsql AS $$
DECLARE
    v_cutoff TIMESTAMPTZ;
    v_rows BIGINT;
BEGIN
    v_cutoff := NOW() - (p_extra_days || ' days')::INTERVAL;

    SELECT COUNT(*) INTO v_rows
    FROM user_sessions
    WHERE (expires_at < v_cutoff OR is_revoked)
    AND created_at < v_cutoff;

    IF p_dry_run THEN
        table_name := 'user_sessions';
        rows_deleted := v_rows;
        RETURN NEXT;
        RETURN;
    END IF;

    DELETE FROM user_sessions
    WHERE (expires_at < v_cutoff OR is_revoked)
    AND created_at < v_cutoff;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    table_name := 'user_sessions';
    rows_deleted := v_rows;
    RETURN NEXT;
END;
$$;

-- Scheduled purge wrapper: call this from a cron job or pg_timetable
CREATE OR REPLACE FUNCTION epms_scheduled_purge(
    p_retention_days INTEGER DEFAULT 90
) RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE
    v_result TEXT;
    v_rec RECORD;
    v_parts TEXT[];
BEGIN
    v_result := 'Purge run at ' || NOW()::TEXT || E'\n';

    FOR v_rec IN SELECT * FROM epms_purge_old_data(p_retention_days, FALSE, 5000)
    LOOP
        IF v_rec.rows_deleted > 0 THEN
            v_result := v_result || format(
                '  %s: %s rows in %s ms' || E'\n',
                v_rec.table_name, v_rec.rows_deleted, v_rec.duration_ms
            );
        END IF;
    END LOOP;

    FOR v_rec IN SELECT * FROM epms_purge_old_sessions(7, FALSE)
    LOOP
        IF v_rec.rows_deleted > 0 THEN
            v_result := v_result || format(
                '  %s: %s rows' || E'\n',
                v_rec.table_name, v_rec.rows_deleted
            );
        END IF;
    END LOOP;

    RETURN v_result;
END;
$$;

-- Record this migration
INSERT INTO schema_migrations (version, file_name, executed_by)
VALUES ('002', '002_indexes_and_retention.sql', 'migration')
ON CONFLICT (version) DO NOTHING;
