"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Providers } from "@/lib/providers";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { GlassCard } from "@/components/ui/GlassCard";
import { GaugeChart } from "@/components/ui/GaugeChart";
import { Badge } from "@/components/ui/Badge";
import { useTheme } from "@/components/layout/ThemeProvider";

function HealthContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { theme } = useTheme();

  const { data: healthData, isLoading } = useQuery({
    queryKey: ["health-devices"],
    queryFn: () => api.health.devices(),
    enabled: isAuthenticated,
  });

  const { data: anomalyData } = useQuery({
    queryKey: ["health-anomalies"],
    queryFn: () => api.health.anomalies(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const devices = healthData?.devices ?? [];
  const anomalies = anomalyData?.anomalies ?? [];

  const healthyCount = devices.filter((d) => d.status === "healthy").length;
  const warningCount = devices.filter((d) => d.status === "warning").length;
  const criticalCount = devices.filter((d) => d.status === "critical" || d.status === "offline").length;
  const avgHealth = devices.length > 0
    ? devices.reduce((s, d) => s + d.health_score, 0) / devices.length
    : 0;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Device Health Overview</h3>
              <p className="text-sm text-muted mt-1">Real-time health metrics, anomaly detection, and system status</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard label="Total" value={devices.length} icon="⊞" variant="glass" />
            <StatCard label="Healthy" value={healthyCount} icon="✓" color="text-success" variant="glass" />
            <StatCard label="Warning" value={warningCount} icon="⚠" color="text-warning" variant="glass" />
            <StatCard label="Critical" value={criticalCount} icon="✗" color="text-danger" variant="glass" />
            <StatCard label="Avg Health" value={`${avgHealth.toFixed(0)}%`} icon="♡" variant="gradient" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card title="Recent Anomalies" className="lg:col-span-2">
              {anomalies.length > 0 ? (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {anomalies.slice(0, 10).map((a) => (
                    <div key={a.id} className="flex items-center gap-3 p-3 rounded-xl bg-card-border/30 border border-card-border/50">
                      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        a.severity === "critical" ? "bg-danger" :
                        a.severity === "warning" ? "bg-warning" : "bg-primary"
                      }`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{a.hostname}: {a.message}</p>
                        <p className="text-[10px] text-muted">{a.type} — {a.value.toFixed(1)} / {a.threshold}</p>
                      </div>
                      <Badge variant={a.severity === "critical" ? "critical" : a.severity === "warning" ? "warning" : "info"}>
                        {a.severity}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">No anomalies detected</p>
              )}
            </Card>

            <Card title="Health Distribution">
              <div className="space-y-4">
                <GlassCard>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Healthy</span>
                    <span className="text-sm font-bold text-success">{healthyCount}</span>
                  </div>
                  <div className="h-1.5 bg-card-border rounded-full mt-2 overflow-hidden">
                    <div className="h-full bg-success rounded-full" style={{ width: `${devices.length > 0 ? (healthyCount / devices.length) * 100 : 0}%` }} />
                  </div>
                </GlassCard>
                <GlassCard>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Warning</span>
                    <span className="text-sm font-bold text-warning">{warningCount}</span>
                  </div>
                  <div className="h-1.5 bg-card-border rounded-full mt-2 overflow-hidden">
                    <div className="h-full bg-warning rounded-full" style={{ width: `${devices.length > 0 ? (warningCount / devices.length) * 100 : 0}%` }} />
                  </div>
                </GlassCard>
                <GlassCard>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Critical/Offline</span>
                    <span className="text-sm font-bold text-danger">{criticalCount}</span>
                  </div>
                  <div className="h-1.5 bg-card-border rounded-full mt-2 overflow-hidden">
                    <div className="h-full bg-danger rounded-full" style={{ width: `${devices.length > 0 ? (criticalCount / devices.length) * 100 : 0}%` }} />
                  </div>
                </GlassCard>
              </div>
            </Card>
          </div>

          <Card title="Device Health Details">
            {devices.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-3 px-2 font-medium">Hostname</th>
                      <th className="text-center py-3 px-2 font-medium">Health</th>
                      <th className="text-center py-3 px-2 font-medium">Score</th>
                      <th className="text-center py-3 px-2 font-medium">CPU</th>
                      <th className="text-center py-3 px-2 font-medium">Memory</th>
                      <th className="text-center py-3 px-2 font-medium">Disk</th>
                      <th className="text-center py-3 px-2 font-medium">Alerts</th>
                      <th className="text-right py-3 px-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devices.map((d) => (
                      <tr key={d.agent_id} className="border-b border-border/50 hover:bg-table-row-hover transition-colors">
                        <td className="py-3 px-2 font-medium text-foreground">{d.hostname}</td>
                        <td className="py-3 px-2 text-center">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${
                            d.status === "healthy" ? "bg-success/10 text-success" :
                            d.status === "warning" ? "bg-warning/10 text-warning" :
                            "bg-danger/10 text-danger"
                          }`}>
                            {d.status}
                          </span>
                        </td>
                        <td className="py-3 px-2 text-center">
                          <span className={`text-sm font-bold ${
                            d.health_score >= 70 ? "text-success" : d.health_score >= 40 ? "text-warning" : "text-danger"
                          }`}>
                            {d.health_score.toFixed(0)}%
                          </span>
                        </td>
                        <td className="py-3 px-2 text-center">
                          <div className="flex items-center gap-2 justify-center">
                            <div className="w-16 h-1.5 bg-card-border rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${
                                d.cpu_usage_percent < 70 ? "bg-success" : d.cpu_usage_percent < 90 ? "bg-warning" : "bg-danger"
                              }`} style={{ width: `${d.cpu_usage_percent}%` }} />
                            </div>
                            <span className="text-xs text-muted">{d.cpu_usage_percent.toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-center">
                          <div className="flex items-center gap-2 justify-center">
                            <div className="w-16 h-1.5 bg-card-border rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${
                                d.memory_usage_percent < 70 ? "bg-success" : d.memory_usage_percent < 90 ? "bg-warning" : "bg-danger"
                              }`} style={{ width: `${d.memory_usage_percent}%` }} />
                            </div>
                            <span className="text-xs text-muted">{d.memory_usage_percent.toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-center">
                          <div className="flex items-center gap-2 justify-center">
                            <div className="w-16 h-1.5 bg-card-border rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${
                                d.disk_usage_percent < 70 ? "bg-success" : d.disk_usage_percent < 90 ? "bg-warning" : "bg-danger"
                              }`} style={{ width: `${d.disk_usage_percent}%` }} />
                            </div>
                            <span className="text-xs text-muted">{d.disk_usage_percent.toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-center">
                          <span className={`text-xs font-medium ${
                            d.active_alerts > 0 ? "text-danger" : "text-muted"
                          }`}>
                            {d.active_alerts}
                          </span>
                        </td>
                        <td className="py-3 px-2 text-right">
                          <button
                            onClick={() => router.push(`/dashboard/nodes/?agent_id=${d.agent_id}`)}
                            className="text-xs text-primary hover:text-primary-hover transition-colors"
                          >
                            Details →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-muted text-sm text-center py-8">No health data available</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function HealthPage() {
  return (
    <Providers>
      <HealthContent />
    </Providers>
  );
}
