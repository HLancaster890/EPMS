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
import { BarChart } from "@/components/charts/BarChart";
import { useTheme } from "@/components/layout/ThemeProvider";

function formatUptime(hours: number): string {
  const d = Math.floor(hours / 24);
  if (d > 0) return `${d}d ${(hours % 24).toFixed(0)}h`;
  return `${hours.toFixed(0)}h`;
}

function ExecutiveContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { theme } = useTheme();

  const { data: exec, isLoading } = useQuery({
    queryKey: ["executive-summary"],
    queryFn: () => api.executive.summary(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Executive Overview</h3>
              <p className="text-sm text-muted mt-1">High-level organizational health, productivity, and performance summary</p>
            </div>
            <GlassCard>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted">Trend:</span>
                <span className={`font-semibold ${
                  exec?.productivity_trend === "improving" ? "text-success" :
                  exec?.productivity_trend === "declining" ? "text-danger" : "text-warning"
                }`}>
                  {exec?.productivity_trend === "improving" ? "↑ Improving" :
                   exec?.productivity_trend === "declining" ? "↓ Declining" : "→ Stable"}
                </span>
              </div>
            </GlassCard>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total Devices" value={exec?.total_devices ?? 0} icon="⊞" variant="glass" />
            <StatCard label="Active Users Today" value={exec?.active_users_today ?? 0} icon="👤" color="text-success" variant="glass" />
            <StatCard
              label="Overall Health"
              value={exec?.overall_health_score ? `${exec.overall_health_score.toFixed(0)}%` : "N/A"}
              icon="♡"
              variant="gradient"
            />
            <StatCard
              label="Avg Productivity"
              value={exec?.avg_productivity ? `${exec.avg_productivity.toFixed(0)}%` : "N/A"}
              icon="▲"
              color={(exec?.avg_productivity ?? 0) >= 70 ? "text-success" : (exec?.avg_productivity ?? 0) >= 40 ? "text-warning" : "text-danger"}
              variant="glass"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Weekly Comparison">
              {exec?.weekly_comparison ? (
                <div className="grid grid-cols-3 gap-4">
                  <GlassCard>
                    <p className="text-[10px] text-muted uppercase mb-1">Productivity</p>
                    <p className="text-lg font-bold text-foreground">{exec.weekly_comparison.current.productivity.toFixed(0)}%</p>
                    <p className={`text-xs ${exec.weekly_comparison.current.productivity >= exec.weekly_comparison.previous.productivity ? "text-success" : "text-danger"}`}>
                      {exec.weekly_comparison.current.productivity >= exec.weekly_comparison.previous.productivity ? "↑" : "↓"} prev {exec.weekly_comparison.previous.productivity.toFixed(0)}%
                    </p>
                  </GlassCard>
                  <GlassCard>
                    <p className="text-[10px] text-muted uppercase mb-1">Health</p>
                    <p className="text-lg font-bold text-foreground">{exec.weekly_comparison.current.health.toFixed(0)}%</p>
                    <p className={`text-xs ${exec.weekly_comparison.current.health >= exec.weekly_comparison.previous.health ? "text-success" : "text-danger"}`}>
                      {exec.weekly_comparison.current.health >= exec.weekly_comparison.previous.health ? "↑" : "↓"} prev {exec.weekly_comparison.previous.health.toFixed(0)}%
                    </p>
                  </GlassCard>
                  <GlassCard>
                    <p className="text-[10px] text-muted uppercase mb-1">Active Users</p>
                    <p className="text-lg font-bold text-foreground">{exec.weekly_comparison.current.active_users}</p>
                    <p className={`text-xs ${exec.weekly_comparison.current.active_users >= exec.weekly_comparison.previous.active_users ? "text-success" : "text-danger"}`}>
                      {exec.weekly_comparison.current.active_users >= exec.weekly_comparison.previous.active_users ? "↑" : "↓"} prev {exec.weekly_comparison.previous.active_users}
                    </p>
                  </GlassCard>
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">No comparison data</p>
              )}
            </Card>

            <Card title="Needs Attention">
              {exec?.needs_attention && exec.needs_attention.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {exec.needs_attention.map((item, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-card-border/30 border border-card-border/50">
                      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        item.severity === "critical" ? "bg-danger" :
                        item.severity === "warning" ? "bg-warning" : "bg-primary"
                      }`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{item.hostname}</p>
                        <p className="text-[10px] text-muted">{item.issue}</p>
                      </div>
                      <Badge variant={item.severity === "critical" ? "critical" : item.severity === "warning" ? "warning" : "info"}>
                        {item.severity}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">All systems nominal</p>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Top Performing Nodes">
              {exec?.top_performers && exec.top_performers.length > 0 ? (
                <div className="space-y-2">
                  {exec.top_performers.slice(0, 5).map((p, i) => (
                    <div key={p.agent_id} className="flex items-center gap-3 p-3 rounded-xl bg-card-border/30 border border-card-border/50">
                      <span className="w-6 h-6 rounded-full gradient-bg flex items-center justify-center text-white text-xs font-bold">
                        {i + 1}
                      </span>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">{p.hostname}</p>
                        <p className="text-[10px] text-muted">{p.agent_id}</p>
                      </div>
                      <span className="text-sm font-bold text-success">{p.score.toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">No data</p>
              )}
            </Card>

            <Card title="Department Breakdown">
              {exec?.department_breakdown && exec.department_breakdown.length > 0 ? (
                <div className="space-y-3">
                  {exec.department_breakdown.map((dept, i) => (
                    <GlassCard key={i}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-foreground">{dept.name}</span>
                        <span className="text-xs text-muted">{dept.device_count} devices</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="flex-1">
                          <div className="flex justify-between text-[10px] text-muted mb-0.5">
                            <span>Productivity</span>
                            <span>{dept.avg_productivity.toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 bg-card-border rounded-full overflow-hidden">
                            <div className="h-full rounded-full bg-primary" style={{ width: `${dept.avg_productivity}%` }} />
                          </div>
                        </div>
                        <div className="flex-1">
                          <div className="flex justify-between text-[10px] text-muted mb-0.5">
                            <span>Health</span>
                            <span>{dept.health_score.toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 bg-card-border rounded-full overflow-hidden">
                            <div className="h-full rounded-full bg-success" style={{ width: `${dept.health_score}%` }} />
                          </div>
                        </div>
                      </div>
                    </GlassCard>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">No department data</p>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard label="Total Teams" value={exec?.total_teams ?? 0} icon="👥" variant="glass" />
            <StatCard label="Total Orgs" value={exec?.total_organizations ?? 0} icon="🏢" variant="glass" />
            <StatCard label="Active Alerts" value={exec?.alerts_active ?? 0} icon="⚠" color={exec?.alerts_critical && exec.alerts_critical > 0 ? "text-danger" : "text-warning"} variant="glass" />
            <StatCard label="Total Uptime" value={formatUptime(exec?.total_uptime_hours ?? 0)} icon="↑" variant="glass" />
          </div>
        </main>
      </div>
    </div>
  );
}

export default function ExecutivePage() {
  return (
    <Providers>
      <ExecutiveContent />
    </Providers>
  );
}
