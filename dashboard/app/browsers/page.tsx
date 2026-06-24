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
import { Badge } from "@/components/ui/Badge";
import { useTheme } from "@/components/layout/ThemeProvider";

function BrowsersContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { theme } = useTheme();

  const { data: browserData, isLoading } = useQuery({
    queryKey: ["browser-activity"],
    queryFn: () => api.dashboard.browserActivity(),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const browsers = browserData ?? [];
  const browserCounts: Record<string, number> = {};
  browsers.forEach((b) => {
    const name = b.browser || "Unknown";
    browserCounts[name] = (browserCounts[name] || 0) + b.duration_seconds;
  });

  const labels = Object.keys(browserCounts);
  const data = Object.values(browserCounts).map((s) => Math.round(s / 60));

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <StatCard label="Browser Events" value={browsers.length} icon="◎" variant="glass" />
            <StatCard label="Unique Browsers" value={labels.length} icon="⊞" variant="glass" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Browser Usage (minutes)">
              {labels.length > 0 ? (
                <BarChart
                  horizontal
                  labels={labels}
                  datasets={[{ label: "Minutes", data, color: theme.colors.primary }]}
                />
              ) : (
                <p className="text-muted text-sm text-center py-8">No browser data</p>
              )}
            </Card>

            <Card title="Recent Pages">
              {browsers.length > 0 ? (
                <div className="overflow-x-auto max-h-80 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                        <th className="text-left py-2 px-2 font-medium">Page</th>
                        <th className="text-left py-2 px-2 font-medium">Domain</th>
                        <th className="text-center py-2 px-2 font-medium">Productive</th>
                      </tr>
                    </thead>
                    <tbody>
                      {browsers.slice(0, 20).map((b, i) => (
                        <tr key={i} className="border-b border-border/30 hover:bg-table-row-hover transition-colors">
                          <td className="py-2 px-2 text-foreground truncate max-w-[200px]">{b.title || b.page_title || b.url}</td>
                          <td className="py-2 px-2 text-muted text-xs">{b.domain}</td>
                          <td className="py-2 px-2 text-center">
                            {b.is_productive !== undefined && (
                              <Badge variant={b.is_productive ? "productive" : "distracting"}>
                                {b.is_productive ? "Yes" : "No"}
                              </Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-muted text-sm text-center py-8">No browser activity</p>
              )}
            </Card>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function BrowsersPage() {
  return (
    <Providers>
      <BrowsersContent />
    </Providers>
  );
}
