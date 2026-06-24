export interface User {
  id: string;
  email: string;
  name: string;
  role: "super_admin" | "admin" | "manager" | "employee";
  organization_id: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface DashboardSummary {
  total_devices: number;
  active_devices: number;
  total_users: number;
  active_users: number;
  total_events: number;
  events_today: number;
  avg_productivity: number;
  alerts_active: number;
  total_afk_minutes: number;
  online_devices: number;
  offline_devices: number;
  active_today: number;
  average_productivity: number;
  idle_devices: number;
  total_teams: number;
  total_orgs: number;
}

export interface Device {
  id: string;
  agent_id: string;
  hostname: string;
  platform: string;
  ip_address: string;
  status: "online" | "idle" | "offline";
  last_seen: string;
  user_name: string;
  version: string;
  name: string;
  os: string;
  is_online: boolean;
  last_heartbeat: string | null;
  created_at: string;
}

export interface ActivityEvent {
  id: string;
  agent_id: string;
  timestamp: string;
  app: string;
  title: string;
  category: "productive" | "neutral" | "distracting";
  duration_seconds: number;
  user: string;
  action: string;
  time: string;
  is_afk: boolean;
}

export interface BrowserActivity {
  browser: string;
  title: string;
  url: string;
  duration_seconds: number;
  timestamp: string;
  user: string;
  domain: string;
  page_title: string;
  is_productive: boolean;
}

export interface EditorActivity {
  editor: string;
  file: string;
  project: string;
  language: string;
  duration_seconds: number;
  timestamp: string;
  user: string;
}

export interface ProductivityData {
  agent_id: string;
  date: string;
  score: number;
  productive_seconds: number;
  neutral_seconds: number;
  distracting_seconds: number;
  idle_seconds: number;
  categories: Record<string, number>;
}

export interface ProductivityResponse {
  data: ProductivityData[];
  period_days: number;
}

export interface Alert {
  id: string;
  type: "threshold" | "anomaly" | "offline" | "system";
  severity: "info" | "warning" | "critical";
  message: string;
  agent_id: string;
  created_at: string;
  acknowledged: boolean;
  title: string;
  description: string;
  source: string;
  time: string;
}

export interface Report {
  id: string;
  name: string;
  type: "daily" | "weekly" | "monthly" | "custom";
  format: "csv" | "html" | "json";
  status: "pending" | "generating" | "completed" | "failed";
  created_at: string;
  download_url: string;
  title: string;
  created_by: string;
  date: string;
}

export interface AgentSettings {
  agent_id: string;
  heartbeat_interval: number;
  afk_timeout: number;
  monitored_apps: string[];
  blocked_apps: string[];
  working_hours_start: string;
  working_hours_end: string;
  working_days: number[];
}

export interface Team {
  id: string;
  name: string;
  description: string;
  organization_id: string;
  created_at: string;
  member_count?: number;
  device_count?: number;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  organization_id: string;
  is_active: boolean;
  last_login: string | null;
}

export interface Organization {
  id: string;
  name: string;
  domain: string;
  created_at: string;
  team_count?: number;
  user_count?: number;
  device_count?: number;
}

export interface ProductivityRule {
  id: string;
  organization_id: string;
  pattern: string;
  category: "productive" | "neutral" | "distracting";
  rule_type: "glob" | "regex" | "exact";
  description: string;
  is_active: boolean;
  created_at: string;
}

export type PeriodType = "today" | "week" | "month" | "custom";

export interface SystemInventory {
  agent_id: string;
  hostname: string;
  os: string;
  os_version: string;
  os_build: string;
  cpu_model: string;
  cpu_cores: number;
  cpu_threads: number;
  cpu_architecture: string;
  total_ram_gb: number;
  total_disk_gb: number;
  used_disk_gb: number;
  free_disk_gb: number;
  ip_address: string;
  mac_address: string;
  last_boot: string;
  last_inventory_update: string;
  installed_software: InstalledSoftware[];
  network_interfaces: NetworkInterface[];
  running_services: RunningService[];
}

export interface InstalledSoftware {
  name: string;
  version: string;
  publisher: string;
  install_date: string;
  size_mb: number;
}

export interface NetworkInterface {
  name: string;
  ip_address: string;
  mac_address: string;
  status: "up" | "down";
  type: "ethernet" | "wifi" | "virtual";
  speed_mbps: number;
}

export interface RunningService {
  name: string;
  display_name: string;
  status: "running" | "stopped" | "paused";
  start_type: "auto" | "manual" | "disabled";
}

export interface DeviceHealth {
  agent_id: string;
  hostname: string;
  status: "healthy" | "warning" | "critical" | "offline";
  health_score: number;
  cpu_usage_percent: number;
  memory_usage_percent: number;
  disk_usage_percent: number;
  uptime_seconds: number;
  last_heartbeat: string;
  active_alerts: number;
  temperature?: number;
  cpu_frequency_mhz?: number;
  network_rx_bytes?: number;
  network_tx_bytes?: number;
  process_count: number;
  thread_count: number;
  handle_count: number;
  performance_index: number;
  stability_score: number;
}

export interface HealthAnomaly {
  id: string;
  agent_id: string;
  hostname: string;
  type: "cpu" | "memory" | "disk" | "network" | "process";
  severity: "info" | "warning" | "critical";
  message: string;
  value: number;
  threshold: number;
  detected_at: string;
  acknowledged: boolean;
}

export interface ExecutiveSummary {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  idle_devices: number;
  total_users: number;
  active_users_today: number;
  total_teams: number;
  total_organizations: number;
  overall_health_score: number;
  avg_productivity: number;
  productivity_trend: "improving" | "declining" | "stable";
  alerts_active: number;
  alerts_critical: number;
  total_uptime_hours: number;
  avg_uptime_per_device_hours: number;
  top_performers: { agent_id: string; hostname: string; score: number }[];
  needs_attention: { agent_id: string; hostname: string; issue: string; severity: string }[];
  weekly_comparison: {
    current: { productivity: number; health: number; active_users: number };
    previous: { productivity: number; health: number; active_users: number };
  };
  department_breakdown: { name: string; device_count: number; avg_productivity: number; health_score: number }[];
}

export interface InventorySummary {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  idle_devices: number;
  os_breakdown: { os: string; count: number }[];
  total_cpu_cores: number;
  total_ram_gb: number;
  total_disk_gb: number;
  avg_cpu_cores: number;
  avg_ram_gb: number;
  avg_disk_gb: number;
  software_count: number;
  service_count: number;
  unpatched_count: number;
}
