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
import { LineChart } from "@/components/charts/LineChart";
import { BarChart } from "@/components/charts/BarChart";
import { DoughnutChart } from "@/components/charts/DoughnutChart";
import { GaugeChart } from "@/components/ui/GaugeChart";
import { TimePeriodSelector } from "@/components/ui/TimePeriodSelector";
import { useTheme } from "@/components/layout/ThemeProvider";
import type { PeriodType } from "@/lib/types";

function ProductivityContent() {
  const router = useRouter();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { theme } = useTheme();
  const [period, setPeriod] = useState<PeriodType>("month");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const days = period === "today" ? 1 : period === "week" ? 7 : 30;
  const { data, isLoading } = useQuery({
    queryKey: ["productivity-analytics", days, period],
    queryFn: () => api.analytics.productivity({ days, period }),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    router.push("/login/");
    return null;
  }

  if (isLoading) return <LoadingSpinner />;

  const prodData = data?.data ?? [];
  const avgScore = prodData.length > 0
    ? prodData.reduce((s, p) => s + p.score, 0) / prodData.length
    : 0;
  const totalProd = prodData.reduce((s, p) => s + p.productive_seconds, 0);
  const totalNeutral = prodData.reduce((s, p) => s + p.neutral_seconds, 0);
  const totalDistract = prodData.reduce((s, p) => s + p.distracting_seconds, 0);
  const totalIdle = prodData.reduce((s, p) => s + (p.idle_seconds || 0), 0);

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">Productivity Analytics</h3>
              <p className="text-sm text-muted mt-0.5">Track and analyze workforce productivity trends</p>
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

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard label="Avg Score" value={avgScore > 0 ? `${avgScore.toFixed(0)}%` : "N/A"} icon="▲" variant="gradient" />
            <StatCard label="Productive" value={formatTime(totalProd)} icon="✓" color="text-success" variant="glass" />
            <StatCard label="Neutral" value={formatTime(totalNeutral)} icon="−" color="text-muted" variant="glass" />
            <StatCard label="Distracting" value={formatTime(totalDistract)} icon="✗" color="text-danger" variant="glass" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card title="30-Day Trend" className="lg:col-span-2">
              {prodData.length > 0 ? (
                <LineChart
                  labels={prodData.map((p) => new Date(p.date).toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" }))}
                  datasets={[{
                    label: "Productivity Score",
                    data: prodData.map((p) => p.score),
                    color: theme.colors.chartLine,
                    pointColor: theme.colors.chartPoint,
                  }]}
                />
              ) : (
                <p className="text-muted text-sm text-center py-8">No data</p>
              )}
            </Card>

            <Card title="Category Breakdown">
              {totalProd > 0 || totalNeutral > 0 || totalDistract > 0 || totalIdle > 0 ? (
                <DoughnutChart
                  labels={["Productive", "Neutral", "Distracting", "Idle"]}
                  data={[totalProd, totalNeutral, totalDistract, totalIdle]}
                  colors={["#22c55e", "#94a3b8", "#ef4444", "#eab308"]}
                />
              ) : (
                <p className="text-muted text-sm text-center py-8">No data</p>
              )}
            </Card>
          </div>

          <Card title="Daily Breakdown">
            {prodData.length > 0 ? (
              <BarChart
                labels={prodData.map((p) => new Date(p.date).toLocaleDateString("en", { weekday: "short", day: "numeric" }))}
                datasets={[
                  { label: "Productive", data: prodData.map((p) => Math.round(p.productive_seconds / 60)), color: "#22c55e" },
                  { label: "Neutral", data: prodData.map((p) => Math.round(p.neutral_seconds / 60)), color: "#94a3b8" },
                  { label: "Distracting", data: prodData.map((p) => Math.round(p.distracting_seconds / 60)), color: "#ef4444" },
                ]}
              />
            ) : (
              <p className="text-muted text-sm text-center py-8">No data</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  );
}

function formatTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function ProductivityPage() {
  return (
    <Providers>
      <ProductivityContent />
    </Providers>
  );
}
