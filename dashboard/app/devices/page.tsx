"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Providers } from "@/lib/providers";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { GlassCard } from "@/components/ui/GlassCard";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Badge } from "@/components/ui/Badge";

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const d = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}

function DevicesContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const [search, setSearch] = useState("");

  const { data: devices, isLoading } = useQuery({
    queryKey: ["devices"],
    queryFn: () => api.devices.list(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const activeCount = devices?.filter((d) => d.status === "online").length ?? 0;
  const idleCount = devices?.filter((d) => d.status === "idle").length ?? 0;
  const offlineCount = devices?.filter((d) => d.status === "offline").length ?? 0;

  const filtered = devices?.filter((d) =>
    !search || d.hostname?.toLowerCase().includes(search.toLowerCase()) ||
    d.name?.toLowerCase().includes(search.toLowerCase()) ||
    d.ip_address?.includes(search) ||
    d.os?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard label="Total" value={devices?.length ?? 0} icon="⊞" variant="glass" />
            <StatCard label="Online" value={activeCount} icon="●" color="text-success" variant="glass" />
            <StatCard label="Idle" value={idleCount} icon="○" color="text-warning" variant="glass" />
            <StatCard label="Offline" value={offlineCount} icon="✗" color="text-danger" variant="glass" />
          </div>

          <Card
            title={`All Devices (${filtered?.length ?? 0})`}
            action={
              <input
                type="text"
                placeholder="Search devices..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="px-3 py-1.5 text-xs rounded-lg bg-input-bg border border-input-border text-foreground placeholder:text-muted focus:outline-none focus:border-primary"
              />
            }
          >
            {filtered && filtered.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-3 px-2 font-medium">Hostname</th>
                      <th className="text-left py-3 px-2 font-medium">OS</th>
                      <th className="text-left py-3 px-2 font-medium">IP</th>
                      <th className="text-center py-3 px-2 font-medium">Status</th>
                      <th className="text-left py-3 px-2 font-medium">Last Seen</th>
                      <th className="text-right py-3 px-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((device) => (
                      <tr key={device.id} className="border-b border-border/50 hover:bg-table-row-hover transition-colors">
                        <td className="py-3 px-2">
                          <div>
                            <p className="font-medium text-foreground">{device.hostname || device.name}</p>
                            <p className="text-[10px] text-muted">{device.user_name}</p>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-muted">{device.os || device.platform}</td>
                        <td className="py-3 px-2 text-muted font-mono text-xs">{device.ip_address}</td>
                        <td className="py-3 px-2 text-center">
                          <Badge variant={device.status}>{device.status}</Badge>
                        </td>
                        <td className="py-3 px-2 text-muted text-xs">{formatTimeAgo(device.last_seen)}</td>
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
              <p className="text-muted text-sm text-center py-8">
                {search ? "No devices match your search" : "No devices registered"}
              </p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function DevicesPage() {
  return (
    <Providers>
      <DevicesContent />
    </Providers>
  );
}
