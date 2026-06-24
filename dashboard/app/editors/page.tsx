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
import { BarChart } from "@/components/charts/BarChart";
import { useTheme } from "@/components/layout/ThemeProvider";

function EditorsContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { theme } = useTheme();

  const { data: editorData, isLoading } = useQuery({
    queryKey: ["editor-activity"],
    queryFn: () => api.dashboard.editorActivity(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const editors = editorData ?? [];
  const editorCounts: Record<string, number> = {};
  editors.forEach((e) => {
    const name = e.editor || "Unknown";
    editorCounts[name] = (editorCounts[name] || 0) + e.duration_seconds;
  });

  const labels = Object.keys(editorCounts);
  const data = Object.values(editorCounts).map((s) => Math.round(s / 60));

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <StatCard label="Editor Events" value={editors.length} icon="⌨" variant="glass" />
            <StatCard label="Unique Editors" value={labels.length} icon="⊞" variant="glass" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Editor Usage (minutes)">
              {labels.length > 0 ? (
                <BarChart
                  horizontal
                  labels={labels}
                  datasets={[{ label: "Minutes", data, color: theme.colors.primary }]}
                />
              ) : (
                <p className="text-muted text-sm text-center py-8">No editor data</p>
              )}
            </Card>

            <Card title="Recent Files">
              {editors.length > 0 ? (
                <div className="overflow-x-auto max-h-80 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                        <th className="text-left py-2 px-2 font-medium">File</th>
                        <th className="text-left py-2 px-2 font-medium">Project</th>
                        <th className="text-left py-2 px-2 font-medium">Language</th>
                      </tr>
                    </thead>
                    <tbody>
                      {editors.slice(0, 20).map((e, i) => (
                        <tr key={i} className="border-b border-border/30 hover:bg-table-row-hover transition-colors">
                          <td className="py-2 px-2 text-foreground truncate max-w-[200px]">{e.file}</td>
                          <td className="py-2 px-2 text-muted text-xs">{e.project}</td>
                          <td className="py-2 px-2 text-muted text-xs">{e.language}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">No editor activity</p>
              )}
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function EditorsPage() {
  return (
    <Providers>
      <EditorsContent />
    </Providers>
  );
}
