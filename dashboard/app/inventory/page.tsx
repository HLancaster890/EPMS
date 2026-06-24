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
import { BarChart } from "@/components/charts/BarChart";
import { useTheme } from "@/components/layout/ThemeProvider";

function formatBytes(gb: number): string {
  if (gb >= 1024) return `${(gb / 1024).toFixed(1)} TB`;
  return `${gb.toFixed(0)} GB`;
}

function InventoryContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { theme } = useTheme();

  const { data: summary, isLoading } = useQuery({
    queryKey: ["inventory-summary"],
    queryFn: () => api.inventory.summary(),
    enabled: isAuthenticated,
  });

  const { data: inventoryList } = useQuery({
    queryKey: ["inventory-list"],
    queryFn: () => api.devices.list(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const osData = summary?.os_breakdown?.map((o) => o.os) ?? [];
  const osCounts = summary?.os_breakdown?.map((o) => o.count) ?? [];

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Node Discovery & System Inventory</h3>
              <p className="text-sm text-muted mt-1">Hardware, software, and configuration across all managed nodes</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              Auto-discovery active
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total Devices" value={summary?.total_devices ?? 0} icon="⊞" variant="glass" />
            <StatCard label="Online" value={summary?.online_devices ?? 0} icon="●" color="text-success" variant="glass" />
            <StatCard label="Total CPU Cores" value={summary?.total_cpu_cores ?? 0} icon="⚡" variant="glass" />
            <StatCard label="Total RAM" value={formatBytes(summary?.total_ram_gb ?? 0)} icon="▮" variant="glass" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card title="OS Distribution">
              {osData.length > 0 ? (
                <BarChart
                  labels={osData}
                  datasets={[{
                    label: "Devices",
                    data: osCounts,
                    color: theme.colors.primary,
                  }]}
                />
              ) : (
                <p className="text-muted text-sm text-center py-8">No data</p>
              )}
            </Card>

            <Card title="Resource Summary">
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs text-muted mb-1">
                    <span>Avg CPU Cores</span>
                    <span>{summary?.avg_cpu_cores?.toFixed(1) ?? "-"}</span>
                  </div>
                  <div className="h-2 bg-card-border rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min((summary?.avg_cpu_cores ?? 0) / 16 * 100, 100)}%` }} />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs text-muted mb-1">
                    <span>Avg RAM</span>
                    <span>{formatBytes(summary?.avg_ram_gb ?? 0)}</span>
                  </div>
                  <div className="h-2 bg-card-border rounded-full overflow-hidden">
                    <div className="h-full bg-success rounded-full" style={{ width: `${Math.min((summary?.avg_ram_gb ?? 0) / 64 * 100, 100)}%` }} />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs text-muted mb-1">
                    <span>Avg Disk</span>
                    <span>{formatBytes(summary?.avg_disk_gb ?? 0)}</span>
                  </div>
                  <div className="h-2 bg-card-border rounded-full overflow-hidden">
                    <div className="h-full bg-warning rounded-full" style={{ width: `${Math.min((summary?.avg_disk_gb ?? 0) / 1024 * 100, 100)}%` }} />
                  </div>
                </div>
              </div>
            </Card>

            <Card title="Asset Counts">
              <div className="space-y-3">
                <GlassCard>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Software Packages</span>
                    <span className="text-lg font-bold text-foreground">{summary?.software_count ?? 0}</span>
                  </div>
                </GlassCard>
                <GlassCard>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Running Services</span>
                    <span className="text-lg font-bold text-foreground">{summary?.service_count ?? 0}</span>
                  </div>
                </GlassCard>
                <GlassCard>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Unpatched</span>
                    <span className="text-lg font-bold text-danger">{summary?.unpatched_count ?? 0}</span>
                  </div>
                </GlassCard>
              </div>
            </Card>
          </div>

          <Card title="Discovered Nodes">
            {inventoryList && inventoryList.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-3 px-2 font-medium">Hostname</th>
                      <th className="text-left py-3 px-2 font-medium">OS</th>
                      <th className="text-left py-3 px-2 font-medium">IP Address</th>
                      <th className="text-left py-3 px-2 font-medium">Status</th>
                      <th className="text-left py-3 px-2 font-medium">Last Seen</th>
                      <th className="text-right py-3 px-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventoryList.map((device) => (
                      <tr key={device.id} className="border-b border-border/50 hover:bg-table-row-hover transition-colors">
                        <td className="py-3 px-2 font-medium text-foreground">{device.hostname || device.name}</td>
                        <td className="py-3 px-2 text-muted">{device.os || device.platform}</td>
                        <td className="py-3 px-2 text-muted">{device.ip_address}</td>
                        <td className="py-3 px-2">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${
                            device.status === "online" ? "bg-success/10 text-success" :
                            device.status === "idle" ? "bg-warning/10 text-warning" :
                            "bg-danger/10 text-danger"
                          }`}>
                            {device.status}
                          </span>
                        </td>
                        <td className="py-3 px-2 text-muted text-xs">
                          {device.last_seen ? new Date(device.last_seen).toLocaleDateString() : "-"}
                        </td>
                        <td className="py-3 px-2 text-right">
                          <button
                            onClick={() => router.push(`/dashboard/nodes/?agent_id=${device.agent_id}`)}
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
              <p className="text-muted text-sm text-center py-8">No nodes discovered yet</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function InventoryPage() {
  return (
    <Providers>
      <InventoryContent />
    </Providers>
  );
}
