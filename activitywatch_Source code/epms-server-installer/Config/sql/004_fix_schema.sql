-- =============================================================
-- EPMS Enterprise Server — Schema Fix Migration
-- Version: 1.0.0
-- Fixes: FK violations, missing columns, JOIN alignment
-- =============================================================

-- 1. agent_heartbeats: change agent_id from UUID FK to VARCHAR(255)
ALTER TABLE agent_heartbeats DROP CONSTRAINT IF EXISTS agent_heartbeats_agent_id_fkey;
ALTER TABLE agent_heartbearts ALTER COLUMN agent_id TYPE VARCHAR(255);

-- 2. browser_activity: change agent_id from UUID FK to VARCHAR(255), add is_productive
ALTER TABLE browser_activity DROP CONSTRAINT IF EXISTS browser_activity_agent_id_fkey;
ALTER TABLE browser_activity ALTER COLUMN agent_id TYPE VARCHAR(255);
ALTER TABLE browser_activity ADD COLUMN IF NOT EXISTS is_productive BOOLEAN DEFAULT TRUE;

-- 3. editor_activity: change agent_id from UUID FK to VARCHAR(255)
ALTER TABLE editor_activity DROP CONSTRAINT IF EXISTS editor_activity_agent_id_fkey;
ALTER TABLE editor_activity ALTER COLUMN agent_id TYPE VARCHAR(255);

-- 4. activity_events: change agent_id from UUID FK to VARCHAR(255)
ALTER TABLE activity_events DROP CONSTRAINT IF EXISTS activity_events_agent_id_fkey;
ALTER TABLE activity_events ALTER COLUMN agent_id TYPE VARCHAR(255);

-- 5. system_metrics: change agent_id from UUID FK to VARCHAR(255)
ALTER TABLE system_metrics DROP CONSTRAINT IF EXISTS system_metrics_agent_id_fkey;
ALTER TABLE system_metrics ALTER COLUMN agent_id TYPE VARCHAR(255);

-- 6. productivity_scores: change agent_id from UUID FK to VARCHAR(255), add hb_count
ALTER TABLE productivity_scores DROP CONSTRAINT IF EXISTS productivity_scores_agent_id_fkey;
ALTER TABLE productivity_scores ALTER COLUMN agent_id TYPE VARCHAR(255);
ALTER TABLE productivity_scores ADD COLUMN IF NOT EXISTS hb_count INTEGER NOT NULL DEFAULT 0;

-- 7. alerts: change agent_id from UUID FK to VARCHAR(255), add acknowledged
ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_agent_id_fkey;
ALTER TABLE alerts ALTER COLUMN agent_id TYPE VARCHAR(255);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS acknowledged BOOLEAN NOT NULL DEFAULT FALSE;

-- 8. audit_log: change agent_id from UUID FK to VARCHAR(255)
ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_agent_id_fkey;
ALTER TABLE audit_log ALTER COLUMN agent_id TYPE VARCHAR(255);

-- 9. Add unique index on agents.agent_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id);

-- Record this migration
INSERT INTO schema_migrations (version, file_name, executed_by)
VALUES ('004', '004_fix_schema.sql', 'installer')
ON CONFLICT (version) DO NOTHING;
