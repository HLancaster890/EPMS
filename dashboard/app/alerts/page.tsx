"use client";

import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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

function AlertsContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => api.alerts.list(),
    enabled: isAuthenticated,
  });

  const ackMutation = useMutation({
    mutationFn: (id: string) => api.alerts.acknowledge(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const alerts = data ?? [];
  const critical = alerts.filter((a) => a.severity === "critical").length;
  const warning = alerts.filter((a) => a.severity === "warning").length;
  const unacknowledged = alerts.filter((a) => !a.acknowledged).length;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard label="Total Alerts" value={alerts.length} icon="⚠" variant="glass" />
            <StatCard label="Critical" value={critical} icon="!!" color="text-danger" variant="glass" />
            <StatCard label="Warning" value={warning} icon="!" color="text-warning" variant="glass" />
            <StatCard label="Unacknowledged" value={unacknowledged} icon="○" color="text-primary" variant="glass" />
          </div>

          <Card title={`Alerts (${alerts.length})`}>
            {alerts.length > 0 ? (
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {alerts.map((alert) => (
                  <GlassCard key={alert.id}>
                    <div className="flex items-start gap-3">
                      <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-1.5 ${
                        alert.severity === "critical" ? "bg-danger" :
                        alert.severity === "warning" ? "bg-warning" : "bg-primary"
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-medium text-foreground">{alert.title || "Alert"}</span>
                          <Badge variant={alert.severity}>{alert.severity}</Badge>
                          <Badge variant={alert.type === "anomaly" ? "warning" : "info"}>{alert.type}</Badge>
                        </div>
                        <p className="text-xs text-muted">{alert.description || alert.message}</p>
                        <p className="text-[10px] text-muted mt-1">
                          {alert.agent_id && <span className="font-mono">{alert.agent_id}</span>}
                          {alert.time && <> · {new Date(alert.time).toLocaleString()}</>}
                        </p>
                      </div>
                      {!alert.acknowledged && (
                        <button
                          onClick={() => ackMutation.mutate(alert.id)}
                          className="text-xs text-primary hover:text-primary-hover px-2 py-1 rounded-lg border border-card-border hover:bg-table-row-hover transition-colors flex-shrink-0"
                        >
                          Acknowledge
                        </button>
                      )}
                    </div>
                  </GlassCard>
                ))}
              </div>
            ) : (
              <p className="text-muted text-sm text-center py-8">No alerts</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function AlertsPage() {
  return (
    <Providers>
      <AlertsContent />
    </Providers>
  );
}
