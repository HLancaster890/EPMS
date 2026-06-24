"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Providers } from "@/lib/providers";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { StatCard } from "@/components/ui/StatCard";
import { Card } from "@/components/ui/Card";
import { GlassCard } from "@/components/ui/GlassCard";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { LineChart } from "@/components/charts/LineChart";
import { DoughnutChart } from "@/components/charts/DoughnutChart";
import { GaugeChart } from "@/components/ui/GaugeChart";
import { TimePeriodSelector } from "@/components/ui/TimePeriodSelector";
import { useTheme } from "@/components/layout/ThemeProvider";
import type { PeriodType } from "@/lib/types";

function formatDuration(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function DashboardContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const user = useAuth((s) => s.user);
  const { theme, isDark } = useTheme();
  const [period, setPeriod] = useState<PeriodType>("today");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const { data: summary, isLoading } = useQuery({
    queryKey: ["dashboard-summary", period, startDate, endDate],
    queryFn: () => api.dashboard.summary(period, startDate || undefined, endDate || undefined),
    enabled: isAuthenticated,
  });

  const { data: productivity } = useQuery({
    queryKey: ["productivity", period === "today" ? 1 : period === "week" ? 7 : 30],
    queryFn: () => api.analytics.productivity({ days: period === "today" ? 1 : period === "week" ? 7 : 30, period }),
    enabled: isAuthenticated,
  });

  const { data: activityData } = useQuery({
    queryKey: ["activity-feed", period, startDate, endDate],
    queryFn: () => api.dashboard.activity({ limit: 10, period, startDate, endDate }),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const isAdmin = user?.role === "admin" || user?.role === "super_admin";
  const isManager = isAdmin || user?.role === "manager";
  const prodData = productivity?.data ?? [];
  const events = activityData?.events ?? [];
  const totalProdSec = prodData.reduce((s, p) => s + p.productive_seconds, 0);
  const totalNeutralSec = prodData.reduce((s, p) => s + p.neutral_seconds, 0);
  const totalDistractSec = prodData.reduce((s, p) => s + p.distracting_seconds, 0);
  const totalIdleSec = prodData.reduce((s, p) => s + (p.idle_seconds || 0), 0);
  const avgScore = prodData.length > 0
    ? prodData.reduce((s, p) => s + p.score, 0) / prodData.length
    : 0;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Welcome back{user?.name ? `, ${user.name}` : ""}</h3>
              <p className="text-sm text-muted mt-0.5">Here&apos;s what&apos;s happening across your organization</p>
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

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard label="Total Devices" value={summary?.total_devices ?? 0} icon="⊞" variant="glass" />
            <StatCard label="Active Now" value={summary?.active_devices ?? summary?.online_devices ?? 0} icon="●" color="text-success" variant="glass" />
            <StatCard label="Events Today" value={summary?.events_today?.toLocaleString() ?? 0} icon="↻" variant="glass" />
            <StatCard label="Active Alerts" value={summary?.alerts_active ?? 0} icon="⚠" color={(summary?.alerts_active ?? 0) > 0 ? "text-warning" : "text-muted"} variant="glass" />
            <StatCard
              label="Avg Productivity"
              value={avgScore > 0 ? `${avgScore.toFixed(0)}%` : "N/A"}
              icon="▲"
              variant="gradient"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card title="Productivity Trend" className="lg:col-span-2">
              {prodData.length > 0 ? (
                <LineChart
                  labels={prodData.map((p) => new Date(p.date).toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" }))}
                  datasets={[{
                    label: "Score",
                    data: prodData.map((p) => p.score),
                    color: theme.colors.chartLine,
                    pointColor: theme.colors.chartPoint,
                  }]}
                />
              ) : (
                <p className="text-muted text-sm text-center py-8">No productivity data yet</p>
              )}
            </Card>

            <div className="space-y-6">
              <Card title="Activity Breakdown">
                {totalProdSec > 0 || totalNeutralSec > 0 || totalDistractSec > 0 ? (
                  <DoughnutChart
                    labels={["Productive", "Neutral", "Distracting"]}
                    data={[totalProdSec, totalNeutralSec, totalDistractSec]}
                    colors={["#22c55e", "#94a3b8", "#ef4444"]}
                  />
                ) : (
                  <p className="text-muted text-sm text-center py-8">No activity data</p>
                )}
              </Card>

              {totalIdleSec > 0 && (
                <GlassCard>
                  <p className="text-xs text-muted mb-1">Idle Time</p>
                  <p className="text-lg font-semibold text-warning">
                    {formatDuration(totalIdleSec)}
                  </p>
                </GlassCard>
              )}
            </div>
          </div>

          {events.length > 0 && (
            <Card title="Recent Activity Feed">
              <div className="space-y-1 max-h-72 overflow-y-auto">
                {events.map((ev, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-table-row-hover transition-colors text-sm border-b border-border/30 last:border-0"
                  >
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${ev.is_afk ? "bg-warning" : "bg-success"}`} />
                    <span className="text-muted text-xs w-16 flex-shrink-0 font-mono">
                      {new Date(ev.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <span className="font-medium text-foreground flex-shrink-0">{ev.user}</span>
                    <span className="text-muted truncate">{ev.app}</span>
                    {ev.is_afk && <span className="text-[10px] text-warning font-medium px-1.5 py-0.5 rounded-full bg-warning/10">AFK</span>}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <Providers>
      <DashboardContent />
    </Providers>
  );
}
