"use client";

import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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

function ReportsContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const queryClient = useQueryClient();
  const [type, setType] = useState<"daily" | "weekly" | "monthly">("daily");
  const [format, setFormat] = useState<"csv" | "html" | "json">("csv");

  const { data, isLoading } = useQuery({
    queryKey: ["reports"],
    queryFn: () => api.reports.list(),
    enabled: isAuthenticated,
  });

  const genMutation = useMutation({
    mutationFn: () => api.reports.generate(type, format),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports"] }),
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const reports = data ?? [];

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard label="Total Reports" value={reports.length} icon="▤" variant="glass" />
            <StatCard label="Completed" value={reports.filter((r) => r.status === "completed").length} icon="✓" color="text-success" variant="glass" />
            <StatCard label="Pending" value={reports.filter((r) => r.status === "pending" || r.status === "generating").length} icon="○" color="text-warning" variant="glass" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Generate Report">
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-muted mb-2 font-medium">Report Type</p>
                  <div className="flex gap-2">
                    {(["daily", "weekly", "monthly"] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setType(t)}
                        className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                          type === t
                            ? "bg-primary text-white"
                            : "bg-card-border/50 text-muted hover:bg-table-row-hover"
                        }`}
                      >
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted mb-2 font-medium">Format</p>
                  <div className="flex gap-2">
                    {(["csv", "html", "json"] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setFormat(f)}
                        className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                          format === f
                            ? "bg-primary text-white"
                            : "bg-card-border/50 text-muted hover:bg-table-row-hover"
                        }`}
                      >
                        {f.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => genMutation.mutate()}
                  disabled={genMutation.isPending}
                  className="w-full py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover disabled:opacity-50 transition-colors"
                >
                  {genMutation.isPending ? "Generating..." : "Generate Report"}
                </button>
              </div>
            </Card>

            <Card title={`Reports (${reports.length})`}>
              {reports.length > 0 ? (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {reports.map((r) => (
                    <GlassCard key={r.id}>
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-foreground">{r.title || r.name}</p>
                          <p className="text-[10px] text-muted mt-0.5">
                            {r.type} · {r.format?.toUpperCase()} · {new Date(r.date || r.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={r.status}>{r.status}</Badge>
                          {r.status === "completed" && r.download_url && (
                            <a
                              href={r.download_url}
                              className="text-xs text-primary hover:text-primary-hover px-2 py-1 rounded border border-card-border hover:bg-table-row-hover transition-colors"
                              download
                            >
                              Download
                            </a>
                          )}
                        </div>
                      </div>
                    </GlassCard>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">No reports generated yet</p>
              )}
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <Providers>
      <ReportsContent />
    </Providers>
  );
}
