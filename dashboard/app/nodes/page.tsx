"use client";

import { useRouter, useSearchParams } from "next/navigation";
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

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function NodeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const agentId = searchParams.get("agent_id") || "";
  const isAuthenticated = useAuth((s) => s.isAuthenticated);

  const { data: inventory, isLoading: invLoading } = useQuery({
    queryKey: ["inventory-detail", agentId],
    queryFn: () => api.inventory.detail(agentId),
    enabled: isAuthenticated && !!agentId,
  });

  const { data: health } = useQuery({
    queryKey: ["health-detail", agentId],
    queryFn: () => api.health.detail(agentId),
    enabled: isAuthenticated && !!agentId,
  });

  const { data: deviceData } = useQuery({
    queryKey: ["device-detail", agentId],
    queryFn: () => api.devices.list().then((list) => list.find((d) => d.agent_id === agentId)),
    enabled: isAuthenticated && !!agentId,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (!agentId) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header />
          <main className="flex-1 flex items-center justify-center">
            <p className="text-muted text-lg">Select a node to view details</p>
          </main>
        </div>
      </div>
    );
  }

  if (invLoading) return <LoadingSpinner />;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.back()}
              className="text-sm text-muted hover:text-foreground transition-colors"
            >
              ← Back
            </button>
            <div>
              <h3 className="text-lg font-semibold text-foreground">{inventory?.hostname || deviceData?.hostname || agentId}</h3>
              <p className="text-sm text-muted">Node ID: {agentId}</p>
            </div>
            {health && (
              <Badge variant={health.status === "healthy" ? "online" : health.status === "warning" ? "warning" : "critical"}>
                {health.status}
              </Badge>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {health && (
              <>
                <StatCard label="Health Score" value={`${health.health_score.toFixed(0)}%`} icon="♡" variant="glass" />
                <StatCard label="CPU" value={`${health.cpu_usage_percent.toFixed(1)}%`} icon="⚡" color={
                  health.cpu_usage_percent < 70 ? "text-success" : health.cpu_usage_percent < 90 ? "text-warning" : "text-danger"
                } variant="glass" />
                <StatCard label="Memory" value={`${health.memory_usage_percent.toFixed(1)}%`} icon="▮" color={
                  health.memory_usage_percent < 70 ? "text-success" : health.memory_usage_percent < 90 ? "text-warning" : "text-danger"
                } variant="glass" />
                <StatCard label="Disk" value={`${health.disk_usage_percent.toFixed(1)}%`} icon="▤" color={
                  health.disk_usage_percent < 70 ? "text-success" : health.disk_usage_percent < 90 ? "text-warning" : "text-danger"
                } variant="glass" />
                <StatCard label="Uptime" value={formatUptime(health.uptime_seconds)} icon="↑" variant="glass" />
              </>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {inventory && (
              <Card title="System Information">
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">OS</p>
                      <p className="text-sm font-medium text-foreground mt-1">{inventory.os} {inventory.os_version}</p>
                      <p className="text-[10px] text-muted">Build {inventory.os_build}</p>
                    </GlassCard>
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">CPU</p>
                      <p className="text-sm font-medium text-foreground mt-1">{inventory.cpu_model}</p>
                      <p className="text-[10px] text-muted">{inventory.cpu_cores}C / {inventory.cpu_threads}T · {inventory.cpu_architecture}</p>
                    </GlassCard>
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Memory</p>
                      <p className="text-sm font-medium text-foreground mt-1">{inventory.total_ram_gb.toFixed(0)} GB</p>
                      <p className="text-[10px] text-muted">Total RAM</p>
                    </GlassCard>
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Storage</p>
                      <p className="text-sm font-medium text-foreground mt-1">{inventory.total_disk_gb.toFixed(0)} GB</p>
                      <p className="text-[10px] text-muted">{inventory.free_disk_gb.toFixed(0)} GB free</p>
                    </GlassCard>
                  </div>
                  <GlassCard>
                    <p className="text-[10px] text-muted uppercase tracking-wider">Network</p>
                    <p className="text-sm font-medium text-foreground mt-1">{inventory.ip_address}</p>
                    <p className="text-[10px] text-muted">{inventory.mac_address}</p>
                  </GlassCard>
                  {inventory.last_boot && (
                    <GlassCard>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Last Boot</p>
                      <p className="text-sm text-foreground mt-1">{new Date(inventory.last_boot).toLocaleString()}</p>
                    </GlassCard>
                  )}
                </div>
              </Card>
            )}

            {health && (
              <Card title="Performance Metrics">
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <GlassCard>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-2">Health Gauge</p>
                    <div className="flex justify-center relative">
                      <GaugeChart value={health.health_score} max={100} label="Overall Health" size={140} />
                    </div>
                  </GlassCard>
                  <GlassCard>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-2">Performance Index</p>
                    <div className="flex justify-center relative">
                      <GaugeChart value={health.performance_index * 100} max={100} label="Performance" size={140} />
                    </div>
                  </GlassCard>
                </div>
                <div className="space-y-3">
                  <GlassCard>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-[10px] text-muted uppercase tracking-wider">Processes</p>
                        <p className="text-sm font-bold text-foreground mt-0.5">{health.process_count}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] text-muted uppercase tracking-wider">Threads</p>
                        <p className="text-sm font-bold text-foreground mt-0.5">{health.thread_count}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] text-muted uppercase tracking-wider">Handles</p>
                        <p className="text-sm font-bold text-foreground mt-0.5">{health.handle_count}</p>
                      </div>
                    </div>
                  </GlassCard>
                  <GlassCard>
                    <p className="text-[10px] text-muted uppercase tracking-wider">Stability Score</p>
                    <div className="flex items-center gap-3 mt-1">
                      <div className="flex-1 h-2 bg-card-border rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${health.stability_score * 100}%` }} />
                      </div>
                      <span className="text-sm font-bold text-foreground">{(health.stability_score * 100).toFixed(0)}%</span>
                    </div>
                  </GlassCard>
                </div>
              </Card>
            )}
          </div>

          {inventory && inventory.installed_software && inventory.installed_software.length > 0 && (
            <Card title={`Installed Software (${inventory.installed_software.length})`}>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-2 px-2 font-medium">Name</th>
                      <th className="text-left py-2 px-2 font-medium">Version</th>
                      <th className="text-left py-2 px-2 font-medium">Publisher</th>
                      <th className="text-right py-2 px-2 font-medium">Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.installed_software.map((sw, i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-table-row-hover transition-colors">
                        <td className="py-2 px-2 text-foreground">{sw.name}</td>
                        <td className="py-2 px-2 text-muted text-xs">{sw.version}</td>
                        <td className="py-2 px-2 text-muted text-xs">{sw.publisher}</td>
                        <td className="py-2 px-2 text-right text-muted text-xs">{sw.size_mb > 0 ? `${sw.size_mb.toFixed(0)} MB` : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {inventory && inventory.running_services && inventory.running_services.length > 0 && (
            <Card title={`Running Services (${inventory.running_services.length})`}>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-2 px-2 font-medium">Service</th>
                      <th className="text-left py-2 px-2 font-medium">Display Name</th>
                      <th className="text-center py-2 px-2 font-medium">Status</th>
                      <th className="text-center py-2 px-2 font-medium">Start Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.running_services.map((svc, i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-table-row-hover transition-colors">
                        <td className="py-2 px-2 text-foreground font-mono text-xs">{svc.name}</td>
                        <td className="py-2 px-2 text-muted text-xs">{svc.display_name}</td>
                        <td className="py-2 px-2 text-center">
                          <Badge variant={svc.status === "running" ? "online" : "offline"}>{svc.status}</Badge>
                        </td>
                        <td className="py-2 px-2 text-center text-xs text-muted">{svc.start_type}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {inventory && inventory.network_interfaces && inventory.network_interfaces.length > 0 && (
            <Card title="Network Interfaces">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-2 px-2 font-medium">Interface</th>
                      <th className="text-left py-2 px-2 font-medium">IP Address</th>
                      <th className="text-left py-2 px-2 font-medium">MAC</th>
                      <th className="text-center py-2 px-2 font-medium">Type</th>
                      <th className="text-center py-2 px-2 font-medium">Status</th>
                      <th className="text-right py-2 px-2 font-medium">Speed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.network_interfaces.map((ni, i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-table-row-hover transition-colors">
                        <td className="py-2 px-2 font-medium text-foreground text-xs">{ni.name}</td>
                        <td className="py-2 px-2 text-muted font-mono text-xs">{ni.ip_address}</td>
                        <td className="py-2 px-2 text-muted font-mono text-xs">{ni.mac_address}</td>
                        <td className="py-2 px-2 text-center text-xs text-muted capitalize">{ni.type}</td>
                        <td className="py-2 px-2 text-center">
                          <Badge variant={ni.status === "up" ? "online" : "offline"}>{ni.status}</Badge>
                        </td>
                        <td className="py-2 px-2 text-right text-xs text-muted">{ni.speed_mbps} Mbps</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
}

export default function NodePage() {
  return (
    <Providers>
      <NodeContent />
    </Providers>
  );
}
