-- =============================================================
-- EPMS Enterprise Server — Performance Indexes
-- Version: 1.0.0
-- =============================================================

-- =============================================================
-- USERS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login DESC);

-- =============================================================
-- USER SESSIONS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at) WHERE is_revoked = FALSE;
CREATE INDEX IF NOT EXISTS idx_user_sessions_refresh ON user_sessions(refresh_token);

-- =============================================================
-- AGENTS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_agents_org_id ON agents(organization_id);
CREATE INDEX IF NOT EXISTS idx_agents_online ON agents(is_online) WHERE is_online = TRUE;
CREATE INDEX IF NOT EXISTS idx_agents_enrolled ON agents(is_enrolled) WHERE is_enrolled = TRUE;
CREATE INDEX IF NOT EXISTS idx_agents_last_heartbeat ON agents(last_heartbeat DESC);
CREATE INDEX IF NOT EXISTS idx_agents_hostname ON agents(hostname);
CREATE INDEX IF NOT EXISTS idx_agents_agent_id ON agents(agent_id);

-- =============================================================
-- AGENT HEARTBEATS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_agent_id ON agent_heartbeats(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_timestamp ON agent_heartbeats(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_agent_time ON agent_heartbeats(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_afk ON agent_heartbeats(is_afk) WHERE is_afk = TRUE;

-- =============================================================
-- ACTIVITY EVENTS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_activity_events_agent_id ON activity_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_activity_events_timestamp ON activity_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_activity_events_agent_time ON activity_events(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_activity_events_type ON activity_events(event_type);
CREATE INDEX IF NOT EXISTS idx_activity_events_app ON activity_events(app_name);
CREATE INDEX IF NOT EXISTS idx_activity_events_domain ON activity_events(domain);
CREATE INDEX IF NOT EXISTS idx_activity_events_date ON activity_events((timestamp::date)) WHERE event_type = 'window';
CREATE INDEX IF NOT EXISTS idx_activity_events_category ON activity_events(category);

-- =============================================================
-- BROWSER ACTIVITY
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_browser_activity_agent_id ON browser_activity(agent_id);
CREATE INDEX IF NOT EXISTS idx_browser_activity_timestamp ON browser_activity(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_browser_activity_agent_time ON browser_activity(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_browser_activity_browser ON browser_activity(browser_name);
CREATE INDEX IF NOT EXISTS idx_browser_activity_domain ON browser_activity(domain);
CREATE INDEX IF NOT EXISTS idx_browser_activity_category ON browser_activity(category);
CREATE INDEX IF NOT EXISTS idx_browser_activity_domain_date ON browser_activity(domain, (timestamp::date));

-- =============================================================
-- EDITOR ACTIVITY
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_editor_activity_agent_id ON editor_activity(agent_id);
CREATE INDEX IF NOT EXISTS idx_editor_activity_timestamp ON editor_activity(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_editor_activity_agent_time ON editor_activity(agent_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_editor_activity_editor ON editor_activity(editor_name);
CREATE INDEX IF NOT EXISTS idx_editor_activity_project ON editor_activity(project_name);
CREATE INDEX IF NOT EXISTS idx_editor_activity_language ON editor_activity(language);

-- =============================================================
-- SYSTEM METRICS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_system_metrics_agent_id ON system_metrics(agent_id);
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_system_metrics_agent_time ON system_metrics(agent_id, timestamp DESC);

-- =============================================================
-- PRODUCTIVITY SCORES
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_productivity_scores_org ON productivity_scores(organization_id);
CREATE INDEX IF NOT EXISTS idx_productivity_scores_agent ON productivity_scores(agent_id);
CREATE INDEX IF NOT EXISTS idx_productivity_scores_date ON productivity_scores(date DESC);
CREATE INDEX IF NOT EXISTS idx_productivity_scores_org_date ON productivity_scores(organization_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_productivity_scores_agent_date ON productivity_scores(agent_id, date DESC);

-- =============================================================
-- PRODUCTIVITY CATEGORIES
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_prod_categories_org ON productivity_categories(organization_id);
CREATE INDEX IF NOT EXISTS idx_prod_categories_productive ON productivity_categories(is_productive);

-- =============================================================
-- DOMAIN CATEGORIES
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_domain_categories_domain ON domain_categories(domain);
CREATE INDEX IF NOT EXISTS idx_domain_categories_category ON domain_categories(category);
CREATE INDEX IF NOT EXISTS idx_domain_categories_productive ON domain_categories(is_productive);

-- =============================================================
-- REPORTS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_reports_org_id ON reports(organization_id);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_date_range ON reports(organization_id, date_from, date_to);

-- =============================================================
-- ALERTS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_alerts_org_id ON alerts(organization_id);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON alerts(is_resolved) WHERE is_resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_alerts_org_unresolved ON alerts(organization_id, is_resolved) WHERE is_resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);

-- =============================================================
-- NOTIFICATIONS
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);

-- =============================================================
-- POLICIES
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_policies_org ON policies(organization_id);
CREATE INDEX IF NOT EXISTS idx_policies_active ON policies(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_policies_type ON policies(policy_type);

-- =============================================================
-- AUDIT LOG
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_audit_log_org ON audit_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_agent ON audit_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);

-- =============================================================
-- CONFIGURATION
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_config_org ON configuration(organization_id);
CREATE INDEX IF NOT EXISTS idx_config_scope ON configuration(scope);
CREATE INDEX IF NOT EXISTS idx_config_key ON configuration(key);
CREATE INDEX IF NOT EXISTS idx_config_org_key ON configuration(organization_id, key);

-- =============================================================
-- PARTITIONING HINTS (for production deployment)
-- =============================================================
-- For high-volume tables, consider partitioning by time:
--
-- activity_events     → partition by month on timestamp
-- browser_activity    → partition by month on timestamp
-- editor_activity     → partition by month on timestamp
-- system_metrics      → partition by month on timestamp
-- agent_heartbeats    → partition by month on timestamp
-- audit_log           → partition by month on created_at
--
-- Example:
-- CREATE TABLE activity_events_y2025m01 PARTITION OF activity_events
--   FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Record this migration
INSERT INTO schema_migrations (version, file_name, executed_by)
VALUES ('003', '003_indexes.sql', 'installer')
ON CONFLICT (version) DO NOTHING;
