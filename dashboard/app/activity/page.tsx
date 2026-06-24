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
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { DoughnutChart } from "@/components/charts/DoughnutChart";
import { TimelineChart } from "@/components/charts/TimelineChart";
import { Badge } from "@/components/ui/Badge";
import { TimePeriodSelector } from "@/components/ui/TimePeriodSelector";
import type { PeriodType } from "@/lib/types";

function ActivityContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const [period, setPeriod] = useState<PeriodType>("today");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const { data: activityData, isLoading } = useQuery({
    queryKey: ["activity", period, startDate, endDate],
    queryFn: () => api.dashboard.activity({ limit: 50, period, startDate, endDate }),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const events = activityData?.events ?? [];
  const activeCount = events.filter((e) => !e.is_afk).length;
  const afkCount = events.filter((e) => e.is_afk).length;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Activity Timeline</h3>
              <p className="text-sm text-muted mt-0.5">Track user activity and application usage</p>
            </div>
            <TimePeriodSelector
              value={period}
              onChange={setPeriod}
              startDate={startDate}
              endDate={endDate}
              onStartDateChange={setStartDate}
              onEndDateChange={setEndDate}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard label="Total Events" value={events.length} icon="↻" variant="glass" />
            <StatCard label="Active" value={activeCount} icon="●" color="text-success" variant="glass" />
            <StatCard label="AFK Periods" value={afkCount} icon="○" color="text-warning" variant="glass" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card title="Active vs AFK">
              <DoughnutChart
                labels={["Active", "AFK"]}
                data={[activeCount, afkCount]}
                colors={["#22c55e", "#eab308"]}
              />
            </Card>

            <Card title="Timeline (24h)" className="lg:col-span-2">
              <TimelineChart events={events.slice(0, 24)} />
            </Card>
          </div>

          <Card title="Activity Events">
            {events.length > 0 ? (
              <div className="overflow-x-auto max-h-96 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted uppercase tracking-wider border-b border-border">
                      <th className="text-left py-3 px-2 font-medium">Time</th>
                      <th className="text-left py-3 px-2 font-medium">User</th>
                      <th className="text-left py-3 px-2 font-medium">Application</th>
                      <th className="text-left py-3 px-2 font-medium">Category</th>
                      <th className="text-center py-3 px-2 font-medium">AFK</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((ev, i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-table-row-hover transition-colors">
                        <td className="py-2.5 px-2 text-muted text-xs font-mono">
                          {new Date(ev.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td className="py-2.5 px-2 font-medium text-foreground">{ev.user}</td>
                        <td className="py-2.5 px-2 text-muted">{ev.app}</td>
                        <td className="py-2.5 px-2">
                          <Badge variant={ev.category}>{ev.category}</Badge>
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          {ev.is_afk && <span className="text-warning text-xs">AFK</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-muted text-sm text-center py-8">No activity events</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

export default function ActivityPage() {
  return (
    <Providers>
      <ActivityContent />
    </Providers>
  );
}
