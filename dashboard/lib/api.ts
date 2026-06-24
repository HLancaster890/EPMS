import type {
  AuthResponse, User, DashboardSummary, Device, ActivityEvent,
  BrowserActivity, EditorActivity, ProductivityResponse, Alert,
  Report, Team, AdminUser, Organization, ProductivityRule, PeriodType,
  SystemInventory, DeviceHealth, HealthAnomaly, ExecutiveSummary, InventorySummary,
} from "./types";

const API_BASE = "/api/v1";

function getPeriodParams(period?: PeriodType, startDate?: string, endDate?: string): string {
  const q = new URLSearchParams();
  if (period) q.set("period", period);
  if (startDate) q.set("start_date", startDate);
  if (endDate) q.set("end_date", endDate);
  return q.toString();
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem("epms_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("epms_token");
    window.location.href = "/dashboard/login/";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    me: () => request<{ id: string; email: string; role: string; organization_id: string; display_name: string }>("/auth/me"),
  },
  dashboard: {
    summary: (period?: PeriodType, startDate?: string, endDate?: string) => {
      const q = getPeriodParams(period, startDate, endDate);
      return request<DashboardSummary>(`/dashboard/summary${q ? `?${q}` : ""}`);
    },
    browserActivity: async () => {
      const raw = await request<{ events: any[] }>("/dashboard/browser-activity");
      return (raw.events || []).map((b: any) => ({
        browser: b.browser || b.browser_name || "",
        browser_name: b.browser_name || "",
        title: b.title || b.page_title || "",
        page_title: b.page_title || "",
        domain: b.domain || "",
        url: b.url || "",
        is_productive: b.is_productive,
        duration_seconds: b.duration_seconds || 0,
        timestamp: b.timestamp || "",
        user: b.user || "",
      })) as BrowserActivity[];
    },
    editorActivity: async () => {
      const raw = await request<{ events: any[] }>("/dashboard/editor-activity");
      return (raw.events || []).map((e: any) => ({
        editor: e.editor || e.editor_name || "",
        editor_name: e.editor_name || "",
        file: e.file || e.file_name || "",
        file_name: e.file_name || "",
        project: e.project || e.project_name || "",
        project_name: e.project_name || "",
        language: e.language || "",
        duration_seconds: e.duration_seconds || 0,
        timestamp: e.timestamp || "",
        user: e.user || "",
      })) as EditorActivity[];
    },
    devices: async () => {
      const raw = await request<{ devices: any[] }>("/dashboard/devices");
      return {
        devices: (raw.devices || []).map((d: any) => ({
          id: d.id || d.agent_id || "",
          agent_id: d.agent_id || "",
          hostname: d.hostname || d.name || "",
          name: d.name || d.hostname || "",
          platform: d.os || d.platform || "",
          os: d.os || "",
          ip_address: d.ip_address || "",
          status: d.is_online ? "online" : "offline",
          is_online: d.is_online || false,
          last_seen: d.last_heartbeat || d.last_seen,
          last_heartbeat: d.last_heartbeat || null,
          user_name: d.user_name || "",
          version: d.version || "",
          created_at: d.created_at || "",
        })),
      };
    },
    activity: async (params?: { agent_id?: string; limit?: number; period?: PeriodType; startDate?: string; endDate?: string }) => {
      const q = new URLSearchParams();
      if (params?.agent_id) q.set("agent_id", params.agent_id);
      if (params?.limit) q.set("limit", String(params.limit));
      if (params?.period) q.set("period", params.period);
      if (params?.startDate) q.set("start_date", params.startDate);
      if (params?.endDate) q.set("end_date", params.endDate);
      const query = q.toString();
      const raw = await request<{ events: any[] }>(`/dashboard/activity${query ? `?${query}` : ""}`);
      return {
        events: (raw.events || []).map((ev: any) => ({
          id: ev.id || "",
          agent_id: ev.agent_id || "",
          timestamp: ev.time || ev.timestamp,
          app: ev.app || "",
          title: ev.action || ev.title || "",
          category: ev.is_afk ? "neutral" : (ev.category || "neutral"),
          duration_seconds: ev.duration_seconds || 300,
          user: ev.user || "",
          action: ev.action || "",
          time: ev.time || ev.timestamp,
          is_afk: ev.is_afk || false,
        })),
      };
    },
    alerts: async () => {
      const raw = await request<{ alerts: any[] }>("/dashboard/alerts");
      return {
        alerts: (raw.alerts || []).map((a: any) => ({
          id: a.id || "",
          type: a.type || "info",
          severity: a.severity || "info",
          message: a.title || a.message || "",
          agent_id: a.agent_id || "",
          created_at: a.time || a.created_at,
          acknowledged: a.acknowledged || false,
          title: a.title || "",
          description: a.description || "",
          source: a.source || "",
          time: a.time || a.created_at,
        })),
      };
    },
    reports: async () => {
      const raw = await request<{ reports: any[] }>("/dashboard/reports");
      return {
        reports: (raw.reports || []).map((r: any) => ({
          id: r.id || "",
          name: r.title || r.name || "",
          type: r.type || "daily",
          format: r.format || "csv",
          status: r.status || "completed",
          created_at: r.date || r.created_at,
          download_url: r.download_url || "",
          title: r.title || "",
          created_by: r.created_by || "",
          date: r.date || r.created_at,
        })),
      };
    },
  },
  devices: {
    list: async () => {
      const raw = await request<{ devices: any[] }>("/dashboard/devices");
      return (raw.devices || []).map((d: any) => ({
        id: d.id || d.agent_id || "",
        agent_id: d.agent_id || "",
        hostname: d.hostname || d.name || "",
        name: d.name || d.hostname || "",
        platform: d.os || d.platform || "",
        os: d.os || "",
        ip_address: d.ip_address || "",
        status: d.is_online ? "online" : "offline",
        is_online: d.is_online || false,
        last_seen: d.last_heartbeat || d.last_seen,
        last_heartbeat: d.last_heartbeat || null,
        user_name: d.user_name || "",
        version: d.version || "",
        created_at: d.created_at || "",
      })) as Device[];
    },
  },
  activity: {
    list: (params?: { agent_id?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.agent_id) q.set("agent_id", params.agent_id);
      if (params?.limit) q.set("limit", String(params.limit));
      const query = q.toString();
      return request<ActivityEvent[]>(
        `/activity${query ? `?${query}` : ""}`
      );
    },
  },
  analytics: {
    productivity: (params?: { agent_id?: string; days?: number; period?: PeriodType }) => {
      const q = new URLSearchParams();
      if (params?.agent_id) q.set("agent_id", params.agent_id);
      if (params?.days) q.set("days", String(params.days));
      if (params?.period) q.set("period", params.period);
      const query = q.toString();
      return request<ProductivityResponse>(
        `/analytics/productivity${query ? `?${query}` : ""}`
      );
    },
  },
  alerts: {
    list: async () => {
      const raw = await request<{ alerts: any[] }>("/dashboard/alerts");
      return (raw.alerts || []).map((a: any) => ({
        id: a.id || "",
        type: a.type || "info",
        severity: a.severity || "info",
        message: a.message || a.title || "",
        agent_id: a.agent_id || "",
        created_at: a.created_at || a.time,
        acknowledged: a.acknowledged || false,
        title: a.title || "",
        description: a.description || "",
        source: a.source || "",
        time: a.time || a.created_at,
      })) as Alert[];
    },
    acknowledge: (id: string) =>
      request<void>(`/dashboard/alerts/${id}/acknowledge`, { method: "POST" }),
  },
  reports: {
    list: async () => {
      const raw = await request<{ reports: any[] }>("/dashboard/reports");
      return (raw.reports || []).map((r: any) => ({
        id: r.id || "",
        name: r.name || r.title || "",
        title: r.title || "",
        type: r.type || "daily",
        format: r.format || "csv",
        status: r.status || "completed",
        created_at: r.created_at || r.date,
        created_by: r.created_by || "",
        download_url: r.download_url || "",
        date: r.date || r.created_at,
      })) as Report[];
    },
    generate: (type: string, format: string) =>
      request<Report>("/reports/generate", {
        method: "POST",
        body: JSON.stringify({ type, format }),
      }),
  },
  teams: {
    list: () => request<{ teams: Team[] }>("/teams"),
  },
  users: {
    list: () => request<{ users: AdminUser[] }>("/users"),
  },
  organizations: {
    list: () => request<{ organizations: Organization[] }>("/organizations"),
  },
  rules: {
    list: () => request<{ rules: ProductivityRule[] }>("/productivity-rules"),
    create: (data: { pattern: string; category: string; rule_type: string; description: string }) =>
      request<{ id: string; status: string }>("/productivity-rules", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: { pattern: string; category: string; rule_type: string; description: string }) =>
      request<{ status: string }>(`/productivity-rules/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<{ status: string }>(`/productivity-rules/${id}`, { method: "DELETE" }),
  },
  inventory: {
    summary: () => request<InventorySummary>("/inventory/summary"),
    detail: (agentId: string) => request<SystemInventory>(`/inventory/detail/${agentId}`),
  },
  health: {
    devices: () => request<{ devices: DeviceHealth[] }>("/health/devices"),
    detail: (agentId: string) => request<DeviceHealth>(`/health/detail/${agentId}`),
    anomalies: () => request<{ anomalies: HealthAnomaly[] }>("/health/anomalies"),
  },
  executive: {
    summary: () => request<ExecutiveSummary>("/executive/summary"),
  },
};
