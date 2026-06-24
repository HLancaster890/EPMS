-- =============================================================
-- EPMS Enterprise Server — Seed Data
-- Version: 1.0.0
-- =============================================================

-- =============================================================
-- DEFAULT PRODUCTIVITY CATEGORIES
-- =============================================================
-- These are installed per-organization at setup time via the
-- admin account creation custom action. This file provides
-- the reference definitions.

-- Category weights:
--   +1.0 = highly productive
--    0.5 = productive
--    0.0 = neutral
--   -0.5 = distracting
--   -1.0 = highly distracting

-- Productive categories
INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Development', '#22c55e', 1.0, true, true,
  '[{"field": "app_name", "operator": "in", "value": ["code.exe","cursor.exe","windsurf.exe","pycharm64.exe","idea64.exe","eclipse.exe","studio64.exe","notepad++.exe","sublime_text.exe","devenv.exe"]}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Communication', '#3b82f6', 0.5, true, true,
  '[{"field": "app_name", "operator": "in", "value": ["outlook.exe","slack.exe","teams.exe","discord.exe","zoom.exe","skype.exe"]}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Research', '#a855f7', 0.5, true, true,
  '[{"field": "domain", "operator": "regex", "value": "(stackoverflow|github|gitlab|bitbucket|docs\\.|learn\\.|wiki|confluence|jira|notion|miro)\\.\\w+"}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

-- Neutral categories
INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Administrative', '#f59e0b', 0.0, true, true,
  '[{"field": "app_name", "operator": "in", "value": ["excel.exe","powerpnt.exe","winword.exe","msaccess.exe"]}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Meetings', '#8b5cf6', 0.0, true, true,
  '[{"field": "app_name", "operator": "in", "value": ["zoom.exe","webex.exe","gotomeeting.exe","teams.exe","meet.exe"]}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

-- Distracting categories
INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Social Media', '#ef4444', -1.0, false, true,
  '[{"field": "domain", "operator": "regex", "value": "(facebook|twitter|x\\.com|instagram|linkedin|reddit|tiktok|snapchat|pinterest)\\.\\w+"}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Entertainment', '#f97316', -1.0, false, true,
  '[{"field": "domain", "operator": "regex", "value": "(youtube|netflix|hulu|twitch|spotify|disney\\+|primevideo|hbomax|crunchyroll)\\.\\w+"}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Shopping', '#ec4899', -0.5, false, true,
  '[{"field": "domain", "operator": "regex", "value": "(amazon|ebay|walmart|etsy|bestbuy|target|aliexpress|shopify)\\.\\w+"}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

INSERT INTO productivity_categories (organization_id, name, color, weight, is_productive, is_system, rules)
SELECT id, 'Idle', '#6b7280', 0.0, false, true,
  '[{"field": "is_afk", "operator": "eq", "value": true}]'::jsonb
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, name) DO NOTHING;

-- =============================================================
-- DEFAULT DOMAIN CATEGORIES
-- =============================================================
INSERT INTO domain_categories (domain, category, sub_category, is_productive, is_blocked, source)
VALUES
  -- Development & Code
  ('github.com', 'Development', 'Code Hosting', true, false, 'system'),
  ('gitlab.com', 'Development', 'Code Hosting', true, false, 'system'),
  ('bitbucket.org', 'Development', 'Code Hosting', true, false, 'system'),
  ('stackoverflow.com', 'Development', 'Q&A', true, false, 'system'),
  ('stackexchange.com', 'Development', 'Q&A', true, false, 'system'),
  ('docs.microsoft.com', 'Development', 'Documentation', true, false, 'system'),
  ('learn.microsoft.com', 'Development', 'Documentation', true, false, 'system'),
  ('developer.mozilla.org', 'Development', 'Documentation', true, false, 'system'),
  ('npmjs.com', 'Development', 'Package Registry', true, false, 'system'),
  ('pypi.org', 'Development', 'Package Registry', true, false, 'system'),
  ('dockerhub.com', 'Development', 'Container Registry', true, false, 'system'),
  ('hub.docker.com', 'Development', 'Container Registry', true, false, 'system'),

  -- Productivity & Collaboration
  ('outlook.com', 'Communication', 'Email', true, false, 'system'),
  ('outlook.office.com', 'Communication', 'Email', true, false, 'system'),
  ('mail.google.com', 'Communication', 'Email', true, false, 'system'),
  ('teams.microsoft.com', 'Communication', 'Chat', true, false, 'system'),
  ('slack.com', 'Communication', 'Chat', true, false, 'system'),
  ('discord.com', 'Communication', 'Chat', true, false, 'system'),
  ('zoom.us', 'Communication', 'Video Conferencing', true, false, 'system'),
  ('meet.google.com', 'Communication', 'Video Conferencing', true, false, 'system'),
  ('webex.com', 'Communication', 'Video Conferencing', true, false, 'system'),
  ('notion.so', 'Productivity', 'Notes', true, false, 'system'),
  ('miro.com', 'Productivity', 'Whiteboard', true, false, 'system'),
  ('confluence.com', 'Productivity', 'Wiki', true, false, 'system'),
  ('atlassian.com', 'Productivity', 'Project Management', true, false, 'system'),
  ('jira.com', 'Productivity', 'Issue Tracking', true, false, 'system'),
  ('trello.com', 'Productivity', 'Project Management', true, false, 'system'),
  ('asana.com', 'Productivity', 'Project Management', true, false, 'system'),
  ('monday.com', 'Productivity', 'Project Management', true, false, 'system'),
  ('clickup.com', 'Productivity', 'Project Management', true, false, 'system'),
  ('linear.app', 'Productivity', 'Issue Tracking', true, false, 'system'),

  -- Social Media
  ('facebook.com', 'Social Media', 'Social Network', false, false, 'system'),
  ('twitter.com', 'Social Media', 'Social Network', false, false, 'system'),
  ('x.com', 'Social Media', 'Social Network', false, false, 'system'),
  ('instagram.com', 'Social Media', 'Photo Sharing', false, false, 'system'),
  ('linkedin.com', 'Social Media', 'Professional Network', true, false, 'system'),
  ('reddit.com', 'Social Media', 'Forum', false, false, 'system'),
  ('tiktok.com', 'Social Media', 'Short Video', false, false, 'system'),
  ('pinterest.com', 'Social Media', 'Inspiration', false, false, 'system'),
  ('snapchat.com', 'Social Media', 'Messaging', false, false, 'system'),

  -- Entertainment
  ('youtube.com', 'Entertainment', 'Video Streaming', false, false, 'system'),
  ('netflix.com', 'Entertainment', 'Video Streaming', false, false, 'system'),
  ('hulu.com', 'Entertainment', 'Video Streaming', false, false, 'system'),
  ('twitch.tv', 'Entertainment', 'Live Streaming', false, false, 'system'),
  ('spotify.com', 'Entertainment', 'Music Streaming', false, false, 'system'),
  ('disneyplus.com', 'Entertainment', 'Video Streaming', false, false, 'system'),
  ('primevideo.com', 'Entertainment', 'Video Streaming', false, false, 'system'),
  ('hbomax.com', 'Entertainment', 'Video Streaming', false, false, 'system'),
  ('crunchyroll.com', 'Entertainment', 'Anime Streaming', false, false, 'system'),

  -- Shopping
  ('amazon.com', 'Shopping', 'Online Retail', false, false, 'system'),
  ('ebay.com', 'Shopping', 'Auction', false, false, 'system'),
  ('walmart.com', 'Shopping', 'Online Retail', false, false, 'system'),
  ('etsy.com', 'Shopping', 'Handmade', false, false, 'system'),
  ('bestbuy.com', 'Shopping', 'Electronics', false, false, 'system'),
  ('target.com', 'Shopping', 'Online Retail', false, false, 'system'),
  ('aliexpress.com', 'Shopping', 'Online Retail', false, false, 'system'),
  ('shopify.com', 'Shopping', 'E-commerce Platform', false, false, 'system'),

  -- News
  ('cnn.com', 'News', 'News Portal', false, false, 'system'),
  ('bbc.com', 'News', 'News Portal', false, false, 'system'),
  ('nytimes.com', 'News', 'News Portal', false, false, 'system'),
  ('reuters.com', 'News', 'News Portal', true, false, 'system'),
  ('bloomberg.com', 'News', 'Financial News', true, false, 'system'),
  ('wsj.com', 'News', 'Financial News', true, false, 'system'),

  -- Search Engines
  ('google.com', 'Search', 'Web Search', true, false, 'system'),
  ('bing.com', 'Search', 'Web Search', true, false, 'system'),
  ('duckduckgo.com', 'Search', 'Web Search', true, false, 'system'),
  ('yahoo.com', 'Search', 'Web Search', true, false, 'system'),

  -- AI & ML
  ('chat.openai.com', 'AI', 'Chat', true, false, 'system'),
  ('claude.ai', 'AI', 'Chat', true, false, 'system'),
  ('copilot.microsoft.com', 'AI', 'Coding Assistant', true, false, 'system'),
  ('github.com/features/copilot', 'AI', 'Coding Assistant', true, false, 'system'),
  ('perplexity.ai', 'AI', 'Research', true, false, 'system'),
  ('gemini.google.com', 'AI', 'Chat', true, false, 'system'),

  -- Cloud Services
  ('aws.amazon.com', 'Cloud', 'AWS Console', true, false, 'system'),
  ('console.aws.amazon.com', 'Cloud', 'AWS Console', true, false, 'system'),
  ('portal.azure.com', 'Cloud', 'Azure Console', true, false, 'system'),
  ('console.cloud.google.com', 'Cloud', 'GCP Console', true, false, 'system'),
  ('digitalocean.com', 'Cloud', 'Cloud Hosting', true, false, 'system'),
  ('vercel.com', 'Cloud', 'Deployment', true, false, 'system'),
  ('netlify.com', 'Cloud', 'Deployment', true, false, 'system'),
  ('heroku.com', 'Cloud', 'Deployment', true, false, 'system')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================
-- DEFAULT ROLES & PERMISSIONS
-- =============================================================
-- Roles are enforced in application code; seed reference data here
INSERT INTO configuration (organization_id, scope, key, value, description)
SELECT id, 'organization', 'default_settings', 
  '{
    "monitoring_enabled": true,
    "heartbeat_interval_seconds": 30,
    "afk_timeout_minutes": 5,
    "browser_monitoring_enabled": true,
    "editor_monitoring_enabled": true,
    "screenshot_interval_minutes": 0,
    "keystroke_logging_enabled": false,
    "data_retention_days": 90,
    "offline_cache_hours": 24,
    "sync_interval_seconds": 60,
    "auto_update_enabled": true,
    "productivity_scoring_enabled": true,
    "dashboard_refresh_seconds": 30,
    "report_auto_generate": true,
    "report_schedule": "weekly"
  }'::jsonb,
  'Default organization-wide monitoring and privacy settings'
FROM organizations
ON CONFLICT (organization_id, scope, key) DO NOTHING;

INSERT INTO configuration (organization_id, scope, key, value, description)
SELECT id, 'organization', 'privacy_settings',
  '{
    "collect_window_titles": true,
    "collect_urls": true,
    "collect_file_names": true,
    "collect_screenshots": false,
    "collect_keystrokes": false,
    "anonymize_data": false,
    "exclude_title_patterns": ["password", "secret", "confidential", "private"],
    "data_encryption_enabled": true,
    "compliance_mode": "gdpr"
  }'::jsonb,
  'Privacy and compliance configuration'
FROM organizations
ON CONFLICT (organization_id, scope, key) DO NOTHING;

-- =============================================================
-- DEFAULT ENROLLMENT TOKEN
-- =============================================================
-- Pre-provisions a SHA-256 hash of "epms_enrollment_token_default"
-- The raw token is: epms_enrollment_token_default
-- In production, generate a unique token per organization.
INSERT INTO configuration (organization_id, scope, key, value, description)
SELECT id, 'organization', 'enrollment_token',
  to_jsonb('2416369cbe866f5ed253d34d714c60b394a4ab93e0cffdf950f17e7f55893ac6'::text),
  'Default enrollment token for agent registration. Hash of "epms_enrollment_token_default"'
FROM organizations WHERE name = 'Default Organization'
ON CONFLICT (organization_id, scope, key) DO NOTHING;

-- Record seed migration
INSERT INTO schema_migrations (version, file_name, executed_by)
VALUES ('002', '002_seed_data.sql', 'installer')
ON CONFLICT (version) DO NOTHING;
